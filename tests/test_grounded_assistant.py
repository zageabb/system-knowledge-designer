import json
from io import BytesIO

import pytest

import app as app_module
from app import create_app
from database import db
from models import AIAction, AssistantContextLink, AssistantExchange, AssistantToolCall, ChunkKnowledgeLink, DiagramRevision, DocumentChunk, KnowledgeDocument, KnowledgeLink, SampleDataset, SQLExecution, SystemProject
from services.assistant_actions import AssistantActionError, KnowledgeLinkProposal, MutationPlan, plan_mutation_actions
from services.grounded_assistant import AnswerCitation, GroundedAnswer, GroundedAnswerError, PlannedTool, ToolPlan, generate_grounded_answer, plan_read_tools
from services.ai_sql import SQLProposal
from services.sandbox import build_sandbox
from tests.test_sandbox_sql import prepare


class FakeOllama:
    def __init__(self, payload): self.payload = payload; self.prompt = ""
    def generate_json(self, model, prompt): self.prompt = prompt; return self.payload


def make_app(tmp_path):
    return create_app({"TESTING": True, "SECRET_KEY": "test", "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path/'assistant.db'}", "DATA_DIR": tmp_path/"data", "WTF_CSRF_ENABLED": False, "ADMIN_PASSWORD": "test-password", "OLLAMA_MODEL": "test-model"})


def test_grounded_answer_accepts_only_supplied_citations():
    evidence = [{"evidence_id": "schema:0", "source": "schema", "title": "SUPPLIER", "locator": "Core", "excerpt": "supplier_id"}]
    fake = FakeOllama({"answer": "Supplier uses supplier_id.", "citations": [{"evidence_id": "schema:0", "label": "SUPPLIER schema"}], "limitations": []})
    answer = generate_grounded_answer(question="How is supplier identified?", evidence=evidence, ollama_url="http://unused", ollama_model="test", client=fake)
    assert answer.citations[0].evidence_id == "schema:0"
    assert "untrusted evidence" in fake.prompt and "Do not invent" in fake.prompt


def test_grounded_answer_rejects_unknown_or_missing_citations():
    evidence = [{"evidence_id": "schema:0", "source": "schema", "title": "SUPPLIER", "locator": "Core", "excerpt": "supplier_id"}]
    with pytest.raises(GroundedAnswerError, match="unknown evidence"):
        generate_grounded_answer(question="Question", evidence=evidence, ollama_url="http://unused", ollama_model="test", client=FakeOllama({"answer": "Claim", "citations": [{"evidence_id": "made-up", "label": "Fake"}]}))
    with pytest.raises(GroundedAnswerError, match="uncited"):
        generate_grounded_answer(question="Question", evidence=evidence, ollama_url="http://unused", ollama_model="test", client=FakeOllama({"answer": "Claim", "citations": []}))


def test_browser_assistant_persists_grounded_exchange(tmp_path, monkeypatch):
    app = make_app(tmp_path); project_id, revision_id, dataset_id = prepare(app); client = app.test_client(); client.post("/login", data={"username": "admin", "password": "test-password"})
    monkeypatch.setattr(app_module, "generate_grounded_answer", lambda **kwargs: GroundedAnswer(answer="Supplier records connect to purchase orders.", citations=[AnswerCitation(evidence_id="schema:0", label="Supplier schema")], limitations=[]))
    response = client.post(f"/projects/{project_id}/assistant", data={"question": "supplier"}, follow_redirects=True)
    assert response.status_code == 200 and b"Supplier records connect" in response.data and b"Supplier schema" in response.data
    with app.app_context():
        exchange = AssistantExchange.query.one(); evidence = json.loads(exchange.evidence_json)
        assert exchange.model_name == "test-model" and exchange.requested_by == "admin"
        assert evidence and evidence[0]["evidence_id"].startswith("schema:")


def test_tool_planner_allows_only_bounded_allow_list():
    allowed = {"schema.inspect": "Inspect a table"}
    plan = plan_read_tools(question="Inspect supplier", evidence=[], allowed_tools=allowed, ollama_url="http://unused", ollama_model="test", client=FakeOllama({"tool_requests": [{"tool_name": "schema.inspect", "argument": "SUPPLIER", "reason": "Need fields"}]}))
    assert len(plan.tool_requests) == 1 and plan.tool_requests[0].argument == "SUPPLIER"
    with pytest.raises(GroundedAnswerError, match="non-permitted"):
        plan_read_tools(question="Run shell", evidence=[], allowed_tools=allowed, ollama_url="http://unused", ollama_model="test", client=FakeOllama({"tool_requests": [{"tool_name": "shell.run", "argument": "whoami"}]}))


def test_browser_opt_in_model_selected_read_tool_is_audited_and_grounded(tmp_path, monkeypatch):
    app = make_app(tmp_path); project_id, revision_id, dataset_id = prepare(app); client = app.test_client(); client.post("/login", data={"username": "admin", "password": "test-password"})
    monkeypatch.setattr(app_module, "plan_read_tools", lambda **kwargs: ToolPlan(tool_requests=[PlannedTool(tool_name="schema.inspect", argument="SUPPLIER", reason="Inspect supplier fields")]))
    monkeypatch.setattr(app_module, "generate_grounded_answer", lambda **kwargs: GroundedAnswer(answer="The supplier table has an identifier.", citations=[AnswerCitation(evidence_id="tool:1", label="Schema inspection")]))
    response = client.post(f"/projects/{project_id}/assistant", data={"question": "Inspect supplier", "use_tools": "on"}, follow_redirects=True)
    assert response.status_code == 200 and b"supplier table has an identifier" in response.data
    with app.app_context():
        call = AssistantToolCall.query.one(); exchange = AssistantExchange.query.one(); evidence = json.loads(exchange.evidence_json)
        assert call.tool_name == "schema.inspect" and call.status == "completed" and call.requested_by == "ollama:admin"
        assert any(item["evidence_id"] == f"tool:{call.id}" for item in evidence)


def test_browser_opt_in_sql_builds_validates_executes_and_cites_count(tmp_path, monkeypatch):
    app = make_app(tmp_path); project_id, revision_id, dataset_id = prepare(app); client = app.test_client(); client.post("/login", data={"username": "admin", "password": "test-password"})
    with app.app_context():
        project = db.session.get(SystemProject, project_id); revision = db.session.get(DiagramRevision, revision_id); dataset = db.session.get(SampleDataset, dataset_id)
        db.session.add(build_sandbox(project, revision, dataset, app.config["DATA_DIR"])); db.session.commit()
    monkeypatch.setattr(app_module, "generate_sql_proposal", lambda **kwargs: SQLProposal(statement="SELECT COUNT(*) AS purchase_order_count FROM PURCHASE_ORDER", explanation="Count purchase orders"))
    monkeypatch.setattr(app_module, "generate_grounded_answer", lambda **kwargs: GroundedAnswer(answer="There is 1 purchase order.", citations=[AnswerCitation(evidence_id="tool:1", label="Validated purchase order count")]))
    response = client.post(f"/projects/{project_id}/assistant", data={"question": "How many purchase orders are there?", "use_sql": "on"}, follow_redirects=True)
    assert response.status_code == 200 and b"There is 1 purchase order" in response.data
    with app.app_context():
        call = AssistantToolCall.query.one(); execution = SQLExecution.query.one(); exchange = AssistantExchange.query.one(); evidence = json.loads(exchange.evidence_json)
        result = json.loads(call.result_json)
        assert call.tool_name == "sql.query" and result["rows"] == [[1]] and result["sql_execution_id"] == execution.id
        assert any(item["evidence_id"] == f"tool:{call.id}" for item in evidence)


def test_mutation_planner_rejects_unlisted_actions(tmp_path):
    app = make_app(tmp_path); project_id, revision_id, dataset_id = prepare(app)
    with app.app_context():
        document = KnowledgeDocument(project_id=project_id, title="Policy", original_filename="policy.txt", media_type="text/plain", managed_path=str(tmp_path / "policy.txt"), content_hash="x")
        db.session.add(document); db.session.commit()
        project = db.session.get(app_module.SystemProject, project_id)
        model = app_module.parse_er_source(db.session.get(app_module.DiagramRevision, revision_id).source)
        with pytest.raises(AssistantActionError, match="non-permitted"):
            plan_mutation_actions(question="Delete it", evidence=[], model=model, documents=[document], ollama_url="http://unused", ollama_model="test", client=FakeOllama({"action_requests": [{"action_name": "documents.delete", "document_id": document.id, "target_type": "table", "target_key": "SUPPLIER"}]}))


def test_assistant_document_link_requires_explicit_confirmation(tmp_path, monkeypatch):
    app = make_app(tmp_path); project_id, revision_id, dataset_id = prepare(app); client = app.test_client(); client.post("/login", data={"username": "admin", "password": "test-password"})
    client.post(f"/projects/{project_id}/knowledge", data={"document": (BytesIO(b"Supplier onboarding policy"), "policy.txt"), "title": "Supplier policy"}, content_type="multipart/form-data")
    with app.app_context(): document_id = KnowledgeDocument.query.one().id
    monkeypatch.setattr(app_module, "generate_grounded_answer", lambda **kwargs: GroundedAnswer(answer="The policy concerns suppliers.", citations=[AnswerCitation(evidence_id="schema:0", label="Supplier schema")]))
    monkeypatch.setattr(app_module, "plan_mutation_actions", lambda **kwargs: MutationPlan(action_requests=[KnowledgeLinkProposal(action_name="knowledge.link_document", document_id=document_id, target_type="table", target_key="SUPPLIER", reason="Policy describes suppliers")]))
    proposed = client.post(f"/projects/{project_id}/assistant", data={"question": "supplier", "propose_actions": "on"}, follow_redirects=True)
    assert proposed.status_code == 200 and b"Confirm link" in proposed.data
    with app.app_context():
        action = AIAction.query.filter_by(action_type="knowledge.link_document").one(); action_id = action.id
        assert action.status == "proposed" and KnowledgeLink.query.count() == 0
    confirmed = client.post(f"/projects/{project_id}/assistant/actions/{action_id}/confirm", follow_redirects=True)
    assert confirmed.status_code == 200 and b"document link applied" in confirmed.data
    with app.app_context():
        assert db.session.get(AIAction, action_id).status == "applied"
        link = KnowledgeLink.query.one(); assert link.document_id == document_id and link.target_key == "SUPPLIER"


def test_assistant_chunk_link_requires_explicit_confirmation(tmp_path, monkeypatch):
    app = make_app(tmp_path); project_id, revision_id, dataset_id = prepare(app); client = app.test_client(); client.post("/login", data={"username": "admin", "password": "test-password"})
    client.post(f"/projects/{project_id}/knowledge", data={"document": (BytesIO(b"Supplier onboarding policy"), "policy.txt"), "title": "Supplier policy"}, content_type="multipart/form-data")
    with app.app_context(): chunk_id = DocumentChunk.query.one().id
    monkeypatch.setattr(app_module, "generate_grounded_answer", lambda **kwargs: GroundedAnswer(answer="The cited passage concerns suppliers.", citations=[AnswerCitation(evidence_id="schema:0", label="Supplier schema")]))
    monkeypatch.setattr(app_module, "plan_mutation_actions", lambda **kwargs: MutationPlan(action_requests=[KnowledgeLinkProposal(action_name="knowledge.link_chunk", chunk_id=chunk_id, target_type="column", target_key="SUPPLIER.supplier_id", reason="Passage defines the identifier")]))
    proposed = client.post(f"/projects/{project_id}/assistant", data={"question": "supplier identifier", "propose_actions": "on"}, follow_redirects=True)
    assert proposed.status_code == 200 and b"document chunk" in proposed.data and b"Confirm link" in proposed.data
    with app.app_context():
        action = AIAction.query.filter_by(action_type="knowledge.link_chunk").one(); action_id = action.id
        assert action.status == "proposed" and ChunkKnowledgeLink.query.count() == 0
    confirmed = client.post(f"/projects/{project_id}/assistant/actions/{action_id}/confirm", follow_redirects=True)
    assert confirmed.status_code == 200 and b"document chunk link applied" in confirmed.data
    with app.app_context():
        assert db.session.get(AIAction, action_id).status == "applied"
        link = ChunkKnowledgeLink.query.one(); assert link.chunk_id == chunk_id and link.target_key == "SUPPLIER.supplier_id"


def test_follow_up_uses_only_selected_project_exchange_and_persists_lineage(tmp_path, monkeypatch):
    app = make_app(tmp_path); project_id, revision_id, dataset_id = prepare(app); client = app.test_client(); client.post("/login", data={"username": "admin", "password": "test-password"})
    answers = iter([
        GroundedAnswer(answer="Suppliers have identifiers.", citations=[AnswerCitation(evidence_id="schema:0", label="Supplier schema")]),
        GroundedAnswer(answer="That identifier is supplier_id.", citations=[AnswerCitation(evidence_id="context:1", label="Prior grounded answer")]),
    ])
    monkeypatch.setattr(app_module, "generate_grounded_answer", lambda **kwargs: next(answers))
    client.post(f"/projects/{project_id}/assistant", data={"question": "supplier"})
    response = client.post(f"/projects/{project_id}/assistant", data={"question": "What is that identifier?", "context_exchange_id": "1"}, follow_redirects=True)
    assert response.status_code == 200 and b"Follow-up to" in response.data and b"That identifier is supplier_id" in response.data
    with app.app_context():
        link = AssistantContextLink.query.one(); second = db.session.get(AssistantExchange, link.exchange_id); evidence = json.loads(second.evidence_json)
        assert link.parent_exchange_id == 1 and link.project_id == project_id
        assert sum(item["source"] == "conversation" for item in evidence) == 1
        other = SystemProject(name="Other", slug="other"); db.session.add(other); db.session.commit(); other_id = other.id
    rejected = client.post(f"/projects/{other_id}/assistant", data={"question": "Leak context", "context_exchange_id": "1"}, follow_redirects=True)
    assert b"does not belong to this project" in rejected.data


def test_follow_up_accepts_three_explicit_exchanges_and_rejects_more(tmp_path, monkeypatch):
    app = make_app(tmp_path); project_id, revision_id, dataset_id = prepare(app); client = app.test_client(); client.post("/login", data={"username": "admin", "password": "test-password"})
    with app.app_context():
        for number in range(1, 5):
            db.session.add(AssistantExchange(project_id=project_id, question=f"Prior {number}", answer_json=GroundedAnswer(answer=f"Answer {number}", citations=[]).model_dump_json(), evidence_json="[]", model_name="test-model", requested_by="admin"))
        db.session.commit()
    monkeypatch.setattr(app_module, "generate_grounded_answer", lambda **kwargs: GroundedAnswer(answer="Combined answer.", citations=[AnswerCitation(evidence_id="context:1", label="First prior answer")]))
    response = client.post(f"/projects/{project_id}/assistant", data={"question": "Combine these", "context_exchange_ids": ["1", "2", "3"]}, follow_redirects=True)
    assert response.status_code == 200 and b"Follow-up to" in response.data and b"#1" in response.data and b"#2" in response.data and b"#3" in response.data
    with app.app_context():
        latest = AssistantExchange.query.order_by(AssistantExchange.id.desc()).first()
        links = AssistantContextLink.query.filter_by(exchange_id=latest.id).order_by(AssistantContextLink.parent_exchange_id).all()
        evidence = json.loads(latest.evidence_json)
        assert [link.parent_exchange_id for link in links] == [1, 2, 3]
        assert [item["evidence_id"] for item in evidence if item["source"] == "conversation"] == ["context:1", "context:2", "context:3"]
    rejected = client.post(f"/projects/{project_id}/assistant", data={"question": "Too much context", "context_exchange_ids": ["1", "2", "3", "4"]}, follow_redirects=True)
    assert b"no more than three" in rejected.data
