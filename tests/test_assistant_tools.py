import json
from io import BytesIO

import pytest

from app import create_app
from database import db
from models import AssistantToolCall, DiagramRevision, DocumentChunk, KnowledgeDocument, SampleDataset, SQLExecution, SystemProject
from services.assistant_tools import AssistantToolError, execute_read_tool
from services.er_language import parse_er_source
from services.sandbox import build_sandbox
from services.revisions import create_revision
from tests.test_sandbox_sql import SOURCE, prepare


def make_app(tmp_path):
    return create_app({"TESTING": True, "SECRET_KEY": "test", "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path/'tools.db'}", "DATA_DIR": tmp_path/"data", "WTF_CSRF_ENABLED": False, "ADMIN_PASSWORD": "test-password"})


def test_typed_read_tools_inspect_schema_and_validate_without_execution(tmp_path):
    app = make_app(tmp_path); project_id, revision_id, dataset_id = prepare(app)
    with app.app_context():
        project = db.session.get(SystemProject, project_id); model = parse_er_source(SOURCE)
        schema = execute_read_tool(tool_name="schema.inspect", argument="SUPPLIER", project=project, model=model)
        assert schema["table"]["name"] == "SUPPLIER" and schema["relationships"]
        validation = execute_read_tool(tool_name="sql.validate", argument="SELECT supplier_name FROM SUPPLIER", project=project, model=model)
        assert validation["tables"] == ["SUPPLIER"] and validation["executable"] is False
        with pytest.raises(AssistantToolError, match="Unknown or non-permitted"):
            execute_read_tool(tool_name="shell.run", argument="whoami", project=project, model=model)


def test_document_read_tool_is_project_scoped(tmp_path):
    app = make_app(tmp_path); first_id, revision_id, dataset_id = prepare(app)
    client = app.test_client(); client.post("/login", data={"username": "admin", "password": "test-password"})
    client.post(f"/projects/{first_id}/knowledge", data={"document": (BytesIO(b"Project-only evidence"), "evidence.txt")}, content_type="multipart/form-data")
    with app.app_context():
        chunk_id = DocumentChunk.query.one().id; first = db.session.get(SystemProject, first_id); model = parse_er_source(SOURCE)
        result = execute_read_tool(tool_name="documents.read_chunk", argument=str(chunk_id), project=first, model=model)
        assert result["text"] == "Project-only evidence"
        second = SystemProject(name="Other", slug="other", dialect="sqlite"); db.session.add(second); db.session.commit()
        with pytest.raises(AssistantToolError, match="not found in this project"):
            execute_read_tool(tool_name="documents.read_chunk", argument=str(chunk_id), project=second, model=None)


def test_browser_records_completed_and_rejected_tool_activity(tmp_path):
    app = make_app(tmp_path); project_id, revision_id, dataset_id = prepare(app); client = app.test_client(); client.post("/login", data={"username": "admin", "password": "test-password"})
    completed = client.post(f"/projects/{project_id}/assistant/tools", data={"tool_name": "schema.inspect", "argument": "SUPPLIER"}, follow_redirects=True)
    assert completed.status_code == 200 and b"completed" in completed.data and b"SUPPLIER" in completed.data
    rejected = client.post(f"/projects/{project_id}/assistant/tools", data={"tool_name": "shell.run", "argument": "whoami"}, follow_redirects=True)
    assert rejected.status_code == 200 and b"rejected" in rejected.data and b"non-permitted" in rejected.data
    with app.app_context():
        calls = AssistantToolCall.query.order_by(AssistantToolCall.id).all()
        assert [call.status for call in calls] == ["completed", "rejected"]
        assert json.loads(calls[0].result_json)["table"]["name"] == "SUPPLIER"


def test_sql_query_and_typed_aggregation_execute_only_current_managed_sandbox(tmp_path):
    app = make_app(tmp_path); project_id, revision_id, dataset_id = prepare(app)
    with app.app_context():
        project = db.session.get(SystemProject, project_id); revision = db.session.get(DiagramRevision, revision_id); dataset = db.session.get(SampleDataset, dataset_id)
        build = build_sandbox(project, revision, dataset, app.config["DATA_DIR"]); db.session.add(build); db.session.commit()
        model = parse_er_source(SOURCE)
        count = execute_read_tool(tool_name="samples.aggregate", argument=json.dumps({"operation": "count", "table": "PURCHASE_ORDER", "column": "*"}), project=project, model=model, allowed_root=app.config["DATA_DIR"])
        assert count["rows"] == [[1]] and count["sandbox_build_id"] == build.id
        query = execute_read_tool(tool_name="sql.query", argument="SELECT COUNT(*) AS purchase_order_count FROM PURCHASE_ORDER", project=project, model=model, allowed_root=app.config["DATA_DIR"])
        assert query["result_columns"] == ["purchase_order_count"] and query["rows"] == [[1]]
        with pytest.raises(AssistantToolError, match="Only SELECT"):
            execute_read_tool(tool_name="sql.query", argument="DELETE FROM PURCHASE_ORDER", project=project, model=model, allowed_root=app.config["DATA_DIR"])


def test_assistant_data_query_rejects_missing_or_stale_sandbox(tmp_path):
    app = make_app(tmp_path); project_id, revision_id, dataset_id = prepare(app)
    with app.app_context():
        project = db.session.get(SystemProject, project_id); model = parse_er_source(SOURCE)
        with pytest.raises(AssistantToolError, match="completed sandbox"):
            execute_read_tool(tool_name="sql.query", argument="SELECT COUNT(*) FROM PURCHASE_ORDER", project=project, model=model, allowed_root=app.config["DATA_DIR"])
        revision = db.session.get(DiagramRevision, revision_id); dataset = db.session.get(SampleDataset, dataset_id)
        db.session.add(build_sandbox(project, revision, dataset, app.config["DATA_DIR"])); db.session.flush()
        replacement = create_revision(project, SOURCE, model, "replacement"); replacement.status = "approved"; project.active_revision_id = replacement.id; db.session.commit()
        with pytest.raises(AssistantToolError, match="current active revision"):
            execute_read_tool(tool_name="sql.query", argument="SELECT COUNT(*) FROM PURCHASE_ORDER", project=project, model=model, allowed_root=app.config["DATA_DIR"])
