import json
from pathlib import Path

import pytest

from app import create_app
from database import db
from models import AIAction, DiagramRevision, SampleDataset, SampleRowDefinition, SandboxBuild, SQLExecution, SystemProject
from services.er_language import parse_er_source
from services.revisions import create_revision
from services.sandbox import build_sandbox
from services.sql_safety import SQLValidationError, execute_readonly, validate_readonly_sql

SOURCE = '''erModel Procurement {
 dialect "sqlite"
 direction LR
 subjectArea Core {
  table SUPPLIER {
   integer supplier_id PK
   string supplier_name length=100 not_null
  }
  table PURCHASE_ORDER {
   integer purchase_order_id PK
   integer supplier_id FK not_null
   decimal order_value precision=18 scale=2
  }
  relationship PURCHASE_ORDER.supplier_id -> SUPPLIER.supplier_id {
   cardinality many-to-one
  }
 }
}'''


def make_app(tmp_path):
    return create_app({"TESTING": True, "SECRET_KEY": "test", "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path/'sandbox.db'}", "DATA_DIR": tmp_path/"data", "WTF_CSRF_ENABLED": False, "ADMIN_PASSWORD": "test-password"})


def prepare(app):
    with app.app_context():
        project = SystemProject(name="Procurement", slug="procurement", dialect="sqlite")
        db.session.add(project); db.session.flush()
        revision = create_revision(project, SOURCE, parse_er_source(SOURCE), "approved")
        revision.status = "approved"; project.active_revision_id = revision.id
        dataset = SampleDataset(project_id=project.id, name="Demo", provenance="synthetic", classification="non-sensitive")
        db.session.add(dataset); db.session.flush()
        db.session.add_all([
            SampleRowDefinition(dataset_id=dataset.id, table_name="SUPPLIER", position=1, values_json=json.dumps({"supplier_id": 1, "supplier_name": "Acme"})),
            SampleRowDefinition(dataset_id=dataset.id, table_name="PURCHASE_ORDER", position=1, values_json=json.dumps({"purchase_order_id": 10, "supplier_id": 1, "order_value": 125.5})),
        ])
        db.session.commit()
        return project.id, revision.id, dataset.id


def test_deterministic_sandbox_and_readonly_execution(tmp_path):
    app = make_app(tmp_path); project_id, revision_id, dataset_id = prepare(app)
    with app.app_context():
        project = db.session.get(SystemProject, project_id); revision = db.session.get(DiagramRevision, revision_id); dataset = db.session.get(SampleDataset, dataset_id)
        build = build_sandbox(project, revision, dataset, app.config["DATA_DIR"])
        db.session.add(build); db.session.commit()
        assert build.status == "completed" and build.row_count == 2
        assert Path(build.managed_path).is_file()
        assert Path(build.managed_path).is_relative_to(Path(app.config["DATA_DIR"]).resolve())
        validated = validate_readonly_sql("SELECT s.supplier_name, SUM(p.order_value) AS total FROM SUPPLIER s JOIN PURCHASE_ORDER p ON p.supplier_id = s.supplier_id GROUP BY s.supplier_name", parse_er_source(SOURCE))
        result = execute_readonly(validated, Path(build.managed_path))
        assert result.columns == ["supplier_name", "total"] and result.rows == [["Acme", 125.5]]


@pytest.mark.parametrize("statement", [
    "DELETE FROM SUPPLIER",
    "PRAGMA table_info(SUPPLIER)",
    "ATTACH DATABASE '/tmp/other.db' AS other",
    "SELECT * FROM MISSING",
    "SELECT missing_field FROM SUPPLIER",
    "SELECT * FROM SUPPLIER; SELECT * FROM PURCHASE_ORDER",
])
def test_sql_validator_rejects_unsafe_or_unknown_sql(statement):
    with pytest.raises(SQLValidationError): validate_readonly_sql(statement, parse_er_source(SOURCE))


def test_complete_browser_sample_to_sql_workflow(tmp_path):
    app = make_app(tmp_path); client = app.test_client(); client.post("/login", data={"username": "admin", "password": "test-password"})
    project_id, revision_id, dataset_id = prepare(app)
    build = client.post(f"/projects/{project_id}/datasets/{dataset_id}/build")
    assert build.status_code == 302
    with app.app_context(): assert SandboxBuild.query.one().status == "completed"
    query = client.post(f"/projects/{project_id}/sql", data={"statement": "SELECT supplier_name FROM SUPPLIER", "action": "execute"})
    assert query.status_code == 200 and b"Acme" in query.data and b"Validation passed" in query.data


def test_executor_rejects_paths_outside_managed_root(tmp_path):
    validated = validate_readonly_sql("SELECT * FROM SUPPLIER", parse_er_source(SOURCE))
    with pytest.raises(SQLValidationError, match="outside the managed"):
        execute_readonly(validated, tmp_path / "outside.sqlite", allowed_root=tmp_path / "managed")


def test_browser_can_edit_sample_row(tmp_path):
    app = make_app(tmp_path); client = app.test_client(); client.post("/login", data={"username": "admin", "password": "test-password"})
    project_id, revision_id, dataset_id = prepare(app)
    with app.app_context():
        row_id = SampleRowDefinition.query.filter_by(dataset_id=dataset_id, table_name="PURCHASE_ORDER").one().id
    response = client.post(
        f"/projects/{project_id}/datasets/{dataset_id}/rows/{row_id}/edit",
        data={"values_json": json.dumps({"purchase_order_id": 10, "supplier_id": 1, "order_value": 250.0})},
        follow_redirects=True,
    )
    assert response.status_code == 200 and b"updated" in response.data
    with app.app_context(): assert json.loads(db.session.get(SampleRowDefinition, row_id).values_json)["order_value"] == 250.0


def test_edit_cannot_break_existing_foreign_key(tmp_path):
    app = make_app(tmp_path); client = app.test_client(); client.post("/login", data={"username": "admin", "password": "test-password"})
    project_id, revision_id, dataset_id = prepare(app)
    with app.app_context():
        row_id = SampleRowDefinition.query.filter_by(dataset_id=dataset_id, table_name="SUPPLIER").one().id
    response = client.post(
        f"/projects/{project_id}/datasets/{dataset_id}/rows/{row_id}/edit",
        data={"values_json": json.dumps({"supplier_id": 2, "supplier_name": "Acme"})},
        follow_redirects=True,
    )
    assert b"update rejected" in response.data and b"no SUPPLIER.supplier_id" in response.data
    with app.app_context(): assert json.loads(db.session.get(SampleRowDefinition, row_id).values_json)["supplier_id"] == 1


def test_delete_is_guarded_then_allows_unreferenced_row(tmp_path):
    app = make_app(tmp_path); client = app.test_client(); client.post("/login", data={"username": "admin", "password": "test-password"})
    project_id, revision_id, dataset_id = prepare(app)
    with app.app_context():
        supplier_id = SampleRowDefinition.query.filter_by(dataset_id=dataset_id, table_name="SUPPLIER").one().id
        order_id = SampleRowDefinition.query.filter_by(dataset_id=dataset_id, table_name="PURCHASE_ORDER").one().id
    rejected = client.post(f"/projects/{project_id}/datasets/{dataset_id}/rows/{supplier_id}/delete", follow_redirects=True)
    assert b"deletion rejected" in rejected.data
    deleted_order = client.post(f"/projects/{project_id}/datasets/{dataset_id}/rows/{order_id}/delete", follow_redirects=True)
    assert b"deleted" in deleted_order.data
    deleted_supplier = client.post(f"/projects/{project_id}/datasets/{dataset_id}/rows/{supplier_id}/delete", follow_redirects=True)
    assert b"deleted" in deleted_supplier.data
    with app.app_context(): assert SampleRowDefinition.query.filter_by(dataset_id=dataset_id).count() == 0


def test_delete_dataset_removes_dependent_history_and_managed_file(tmp_path):
    app = make_app(tmp_path); client = app.test_client(); client.post("/login", data={"username": "admin", "password": "test-password"})
    project_id, revision_id, dataset_id = prepare(app)
    client.post(f"/projects/{project_id}/datasets/{dataset_id}/build")
    with app.app_context():
        build = SandboxBuild.query.filter_by(dataset_id=dataset_id).one(); managed_path = Path(build.managed_path)
        db.session.add(SQLExecution(project_id=project_id, sandbox_build_id=build.id, statement="SELECT 1", status="completed"))
        db.session.add(AIAction(project_id=project_id, dataset_id=dataset_id, action_type="propose_sample_rows", status="rejected", payload_json="{}"))
        db.session.commit()
        assert managed_path.is_file()
    response = client.post(f"/projects/{project_id}/datasets/{dataset_id}/delete", follow_redirects=True)
    assert response.status_code == 200 and b"related records deleted" in response.data
    with app.app_context():
        assert db.session.get(SampleDataset, dataset_id) is None
        assert SampleRowDefinition.query.filter_by(dataset_id=dataset_id).count() == 0
        assert SandboxBuild.query.filter_by(dataset_id=dataset_id).count() == 0
        assert SQLExecution.query.count() == 0
        assert AIAction.query.filter_by(dataset_id=dataset_id).count() == 0
        assert db.session.get(SystemProject, project_id) is not None
    assert not managed_path.exists()
