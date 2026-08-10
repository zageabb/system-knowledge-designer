import json

import pytest

import app as app_module
from app import create_app
from database import db
from models import AIAction, SQLExecution
from services.ai_sql import SQLProposal, SQLProposalError, generate_sql_proposal
from services.er_language import parse_er_source
from tests.test_sandbox_sql import SOURCE, prepare


class FakeOllama:
    def __init__(self, payload): self.payload = payload; self.prompt = ""
    def generate_json(self, model, prompt): self.prompt = prompt; return self.payload


def make_app(tmp_path):
    return create_app({"TESTING": True, "SECRET_KEY": "test", "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path/'ai-sql.db'}", "DATA_DIR": tmp_path/"data", "WTF_CSRF_ENABLED": False, "ADMIN_PASSWORD": "test-password"})


def test_sql_proposal_is_schema_grounded_and_deterministically_validated():
    fake = FakeOllama({"statement": "SELECT supplier_name FROM SUPPLIER", "explanation": "Lists suppliers", "assumptions": []})
    proposal = generate_sql_proposal(question="List suppliers", model=parse_er_source(SOURCE), ollama_url="http://unused", ollama_model="test", client=fake)
    assert proposal.statement == "SELECT supplier_name FROM SUPPLIER"
    assert "authoritative schema" in fake.prompt and "Never emit" in fake.prompt


def test_sql_proposal_rejects_unsafe_generated_statement():
    fake = FakeOllama({"statement": "DELETE FROM SUPPLIER", "explanation": "unsafe"})
    with pytest.raises(SQLProposalError, match="deterministic validation"):
        generate_sql_proposal(question="Delete suppliers", model=parse_er_source(SOURCE), ollama_url="http://unused", ollama_model="test", client=fake)


def test_browser_sql_proposal_requires_confirmation_and_never_auto_executes(tmp_path, monkeypatch):
    app = make_app(tmp_path); project_id, revision_id, dataset_id = prepare(app); client = app.test_client(); client.post("/login", data={"username": "admin", "password": "test-password"})
    monkeypatch.setattr(app_module, "generate_sql_proposal", lambda **kwargs: SQLProposal(statement="SELECT supplier_name FROM SUPPLIER", explanation="Lists supplier names", assumptions=["Active sandbox data"] ))
    proposed = client.post(f"/projects/{project_id}/sql/proposals", data={"question": "List suppliers"}, follow_redirects=True)
    assert proposed.status_code == 200 and b"Confirm and load" in proposed.data
    with app.app_context():
        action = AIAction.query.one(); action_id = action.id
        assert action.status == "proposed" and SQLExecution.query.count() == 0
    confirmed = client.post(f"/projects/{project_id}/sql/proposals/{action_id}/confirm", follow_redirects=True)
    assert confirmed.status_code == 200 and b"SELECT supplier_name FROM SUPPLIER" in confirmed.data and b"Review it before choosing execute" in confirmed.data
    assert b"Query impact diagram" in confirmed.data and b"#fef3c7" in confirmed.data and b"#fde68a" in confirmed.data
    with app.app_context():
        assert db.session.get(AIAction, action_id).status == "applied"
        assert SQLExecution.query.count() == 0
