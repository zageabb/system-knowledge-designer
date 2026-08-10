from app import create_app
from database import db
from models import AuditEvent, DiagramRevision
from services.settings import CODEX_CONTROL_ENABLED, get_text, set_bool

TOKEN = "a-test-token-that-is-long-enough"
HEADERS = {"Authorization": f"Bearer {TOKEN}"}


def make_app(tmp_path):
    return create_app({"TESTING": True, "SECRET_KEY": "test", "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path/'api.db'}", "DATA_DIR": tmp_path/"data", "WTF_CSRF_ENABLED": False, "ADMIN_PASSWORD": "test-password", "CODEX_CONTROL_TOKEN": TOKEN})


def enable(app):
    with app.app_context():
        set_bool(CODEX_CONTROL_ENABLED, True); db.session.commit()


def source():
    return '''erModel Controlled {\n dialect "sqlite"\n direction LR\n subjectArea Core {\n  table ITEM {\n   integer item_id PK\n  }\n }\n}'''


def test_api_is_disabled_by_default(tmp_path):
    client = make_app(tmp_path).test_client()
    response = client.get("/api/codex/v1/status", headers=HEADERS)
    assert response.status_code == 403
    assert response.json["error"]["code"] == "codex_control_disabled"


def test_api_requires_bearer_token(tmp_path):
    app = make_app(tmp_path); enable(app); client = app.test_client()
    response = client.get("/api/codex/v1/status")
    assert response.status_code == 401
    assert response.json["error"]["code"] == "unauthorised"


def test_admin_can_turn_control_on_and_off_immediately(tmp_path):
    app = make_app(tmp_path); client = app.test_client()
    client.post("/login", data={"username": "admin", "password": "test-password"})
    enabled = client.post("/settings/control", data={"codex_control_enabled": "on"})
    assert enabled.status_code == 302
    assert client.get("/api/codex/v1/status", headers=HEADERS).status_code == 200
    disabled = client.post("/settings/control", data={})
    assert disabled.status_code == 302
    assert client.get("/api/codex/v1/status", headers=HEADERS).status_code == 403


def test_admin_can_save_llm_settings_and_invalid_url_is_rejected(tmp_path):
    app = make_app(tmp_path); client = app.test_client()
    client.post("/login", data={"username": "admin", "password": "test-password"})
    saved = client.post("/settings/control", data={"section": "llm", "ollama_url": "http://192.168.1.20:11434/", "ollama_model": "qwen3:8b"})
    assert saved.status_code == 302
    page = client.get(saved.location)
    assert b"http://192.168.1.20:11434" in page.data and b"qwen3:8b" in page.data
    with app.app_context():
        assert get_text("ollama_url") == "http://192.168.1.20:11434"
        assert get_text("ollama_model") == "qwen3:8b"
    rejected = client.post("/settings/control", data={"section": "llm", "ollama_url": "file:///tmp/ollama", "ollama_model": "unsafe"})
    assert rejected.status_code == 302
    with app.app_context(): assert get_text("ollama_model") == "qwen3:8b"


def test_codex_can_inspect_validate_and_create_draft_but_not_approve(tmp_path):
    app = make_app(tmp_path); enable(app); client = app.test_client()
    status = client.get("/api/codex/v1/status", headers=HEADERS)
    assert status.status_code == 200
    assert status.json["material_changes_require_ui_confirmation"] is True
    validation = client.post("/api/codex/v1/validate", headers=HEADERS, json={"source": source()})
    assert validation.status_code == 200 and validation.json["summary"]["tables"] == 1
    created = client.post("/api/codex/v1/projects", headers=HEADERS, json={"name": "API Project", "dialect": "sqlite"})
    assert created.status_code == 201
    project_id = created.json["project"]["id"]
    revision = client.post(f"/api/codex/v1/projects/{project_id}/revisions", headers=HEADERS, json={"source": source(), "note": "Codex proposal"})
    assert revision.status_code == 201
    assert revision.json["revision"]["status"] == "draft"
    assert revision.json["confirmation_required_for_approval"] is True
    detail = client.get(f"/api/codex/v1/projects/{project_id}", headers=HEADERS)
    assert detail.status_code == 200 and detail.json["project"]["revisions"][0]["status"] == "draft"
    assert client.post(f"/api/codex/v1/projects/{project_id}/revisions/{revision.json['revision']['id']}/approve", headers=HEADERS).status_code == 404
    with app.app_context():
        assert DiagramRevision.query.one().status == "draft"
        assert AuditEvent.query.filter(AuditEvent.detail.like("Codex API:%")).count() == 2


def test_invalid_source_is_structured_and_not_persisted(tmp_path):
    app = make_app(tmp_path); enable(app); client = app.test_client()
    project = client.post("/api/codex/v1/projects", headers=HEADERS, json={"name": "Invalid Test"}).json["project"]
    response = client.post(f"/api/codex/v1/projects/{project['id']}/revisions", headers=HEADERS, json={"source": "not an er model"})
    assert response.status_code == 422 and response.json["error"]["code"] == "invalid_er_source"
    with app.app_context(): assert DiagramRevision.query.count() == 0
