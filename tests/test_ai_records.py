import json

import pytest

import app as app_module
from app import create_app
from database import db
from models import AIAction, SampleDataset, SampleRowDefinition
from services.ai_sample_rows import AIRecordGenerationError, GeneratedRows, generate_record_proposal
from services.er_language import parse_er_source
from tests.test_sandbox_sql import SOURCE, prepare


class FakeOllama:
    def __init__(self, payload): self.payload = payload; self.prompt = ""
    def generate_json(self, model, prompt): self.prompt = prompt; return self.payload


def make_app(tmp_path):
    return create_app({"TESTING": True, "SECRET_KEY": "test", "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path/'ai.db'}", "DATA_DIR": tmp_path/"data", "WTF_CSRF_ENABLED": False, "ADMIN_PASSWORD": "test-password", "OLLAMA_MODEL": "test-model"})


def test_generation_is_schema_grounded_and_validated():
    fake = FakeOllama({"rows": [{"supplier_id": 2, "supplier_name": "Synthetic Supply Co"}], "notes": "Synthetic fixture"})
    proposal = generate_record_proposal(model=parse_er_source(SOURCE), table_name="SUPPLIER", count=1, instructions="Use a fictional supplier", ollama_url="http://unused", ollama_model="test", client=fake)
    assert proposal.rows[0]["supplier_id"] == 2
    assert "supplier_name" in fake.prompt and "non-sensitive" in fake.prompt


def test_invalid_generated_rows_are_rejected():
    fake = FakeOllama({"rows": [{"supplier_id": "not-an-integer", "supplier_name": "Example"}]})
    with pytest.raises(AIRecordGenerationError, match="failed validation"):
        generate_record_proposal(model=parse_er_source(SOURCE), table_name="SUPPLIER", count=1, instructions="", ollama_url="http://unused", ollama_model="test", client=fake)


def test_generation_uses_and_enforces_related_table_keys():
    fake = FakeOllama({"rows": [{"purchase_order_id": 11, "supplier_id": 101, "order_value": 42.5}]})
    proposal = generate_record_proposal(
        model=parse_er_source(SOURCE), table_name="PURCHASE_ORDER", count=1, instructions="",
        ollama_url="http://unused", ollama_model="test", client=fake,
        related_rows_by_table={"SUPPLIER": [{"supplier_id": 101, "supplier_name": "Synthetic Supplier"}]},
    )
    assert proposal.rows[0]["supplier_id"] == 101
    assert '"allowed_values": [101]' in fake.prompt
    assert '"references": "SUPPLIER.supplier_id"' in fake.prompt


def test_generation_rejects_invented_foreign_key():
    fake = FakeOllama({"rows": [{"purchase_order_id": 11, "supplier_id": 2, "order_value": 42.5}]})
    with pytest.raises(AIRecordGenerationError, match=r"invalid foreign key.*Allowed values.*101"):
        generate_record_proposal(
            model=parse_er_source(SOURCE), table_name="PURCHASE_ORDER", count=1, instructions="",
            ollama_url="http://unused", ollama_model="test", client=fake,
            related_rows_by_table={"SUPPLIER": [{"supplier_id": 101, "supplier_name": "Synthetic Supplier"}]},
        )


def test_generation_rejects_reference_when_parent_table_is_empty():
    fake = FakeOllama({"rows": [{"purchase_order_id": 11, "supplier_id": 2, "order_value": 42.5}]})
    with pytest.raises(AIRecordGenerationError, match=r"add referenced rows first"):
        generate_record_proposal(
            model=parse_er_source(SOURCE), table_name="PURCHASE_ORDER", count=1, instructions="",
            ollama_url="http://unused", ollama_model="test", client=fake,
            related_rows_by_table={},
        )


def test_browser_proposes_then_requires_confirmation(tmp_path, monkeypatch):
    app = make_app(tmp_path); client = app.test_client(); client.post("/login", data={"username": "admin", "password": "test-password"})
    project_id, revision_id, dataset_id = prepare(app)
    monkeypatch.setattr(app_module, "generate_record_proposal", lambda **kwargs: GeneratedRows(rows=[{"supplier_id": 2, "supplier_name": "Generated Example"}], notes="Review me"))
    proposed = client.post(f"/projects/{project_id}/ai-records", data={"table": "SUPPLIER", "dataset_id": str(dataset_id), "count": "1", "instructions": "one fictional supplier"})
    assert proposed.status_code == 302
    with app.app_context():
        action = AIAction.query.one()
        assert action.status == "proposed"
        assert SampleRowDefinition.query.filter_by(dataset_id=dataset_id, table_name="SUPPLIER").count() == 1
        action_id = action.id
    page = client.get(f"/projects/{project_id}/ai-records?table=SUPPLIER&dataset_id={dataset_id}")
    assert page.status_code == 200 and b"Generated Example" in page.data and b"Confirm and add" in page.data
    confirmed = client.post(f"/projects/{project_id}/ai-records/{action_id}/confirm")
    assert confirmed.status_code == 302
    with app.app_context():
        assert db.session.get(AIAction, action_id).status == "applied"
        rows = SampleRowDefinition.query.filter_by(dataset_id=dataset_id, table_name="SUPPLIER").order_by(SampleRowDefinition.position).all()
        assert len(rows) == 2 and json.loads(rows[-1].values_json)["supplier_name"] == "Generated Example"


def test_reject_does_not_create_rows(tmp_path, monkeypatch):
    app = make_app(tmp_path); client = app.test_client(); client.post("/login", data={"username": "admin", "password": "test-password"})
    project_id, revision_id, dataset_id = prepare(app)
    monkeypatch.setattr(app_module, "generate_record_proposal", lambda **kwargs: GeneratedRows(rows=[{"supplier_id": 3, "supplier_name": "Rejected Example"}]))
    client.post(f"/projects/{project_id}/ai-records", data={"table": "SUPPLIER", "dataset_id": str(dataset_id), "count": "1"})
    with app.app_context(): action_id = AIAction.query.one().id
    client.post(f"/projects/{project_id}/ai-records/{action_id}/reject")
    with app.app_context():
        assert db.session.get(AIAction, action_id).status == "rejected"
        assert SampleRowDefinition.query.filter_by(dataset_id=dataset_id, table_name="SUPPLIER").count() == 1


def test_ai_route_passes_all_dataset_rows_as_relationship_context(tmp_path, monkeypatch):
    app = make_app(tmp_path); client = app.test_client(); client.post("/login", data={"username": "admin", "password": "test-password"})
    project_id, revision_id, dataset_id = prepare(app)
    captured = {}
    def generate(**kwargs):
        captured.update(kwargs)
        return GeneratedRows(rows=[{"purchase_order_id": 12, "supplier_id": 1, "order_value": 80.0}])
    monkeypatch.setattr(app_module, "generate_record_proposal", generate)
    response = client.post(f"/projects/{project_id}/ai-records", data={"table": "PURCHASE_ORDER", "dataset_id": str(dataset_id), "count": "1"})
    assert response.status_code == 302
    assert captured["related_rows_by_table"]["SUPPLIER"][0]["supplier_id"] == 1
