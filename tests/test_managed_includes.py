import json

from app import create_app
from database import db
from models import DiagramRevision, ERInclude, TableDefinition
from services.revisions import revision_model


def make_app(tmp_path):
    return create_app({"TESTING": True, "SECRET_KEY": "test", "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path/'includes.db'}", "DATA_DIR": tmp_path/"data", "WTF_CSRF_ENABLED": False, "ADMIN_PASSWORD": "test-password"})


INCLUDE_SOURCE = '''erModel Shared_Core {
 subjectArea Shared {
  table TENANT {
   integer tenant_id PK
  }
 }
}'''

ROOT_SOURCE = '''erModel Consumer {
 include "shared core"
 subjectArea Local {
  table ORDER_HEADER {
   integer order_id PK
   integer tenant_id FK
  }
  relationship ORDER_HEADER.tenant_id -> TENANT.tenant_id {
   cardinality many-to-one
  }
 }
}'''


def test_browser_managed_include_creates_resolved_immutable_revision(tmp_path):
    app = make_app(tmp_path); client = app.test_client(); client.post("/login", data={"username": "admin", "password": "test-password"})
    created = client.post("/projects", data={"name": "Include Lab", "dialect": "sqlite"}); project_id = int(created.location.split("/")[2])
    added = client.post(f"/projects/{project_id}/includes", data={"name": "Shared Core", "source": INCLUDE_SOURCE}, follow_redirects=True)
    assert b"Managed include &#39;Shared Core&#39; created" in added.data
    saved = client.post(f"/projects/{project_id}/workbench", data={"source": ROOT_SOURCE, "action": "save", "base_revision_number": "0", "revision_note": "resolved include"})
    assert b"Draft revision 1 created" in saved.data
    with app.app_context():
        record = ERInclude.query.one(); include_id = record.id
        revision = DiagramRevision.query.one()
        assert [table.name for table in revision_model(revision).tables] == ["TENANT", "ORDER_HEADER"]
        assert TableDefinition.query.filter_by(revision_id=revision.id).count() == 2
        assert json.loads(revision.model_json)["includes"] == ["shared core"]
    deleted = client.post(f"/projects/{project_id}/includes/{include_id}/delete", follow_redirects=True)
    assert b"Existing revisions retain their resolved model snapshots" in deleted.data
    with app.app_context():
        assert ERInclude.query.count() == 0
        assert [table.name for table in revision_model(DiagramRevision.query.one()).tables] == ["TENANT", "ORDER_HEADER"]


def test_managed_include_names_are_project_scoped_and_missing_include_is_actionable(tmp_path):
    app = make_app(tmp_path); client = app.test_client(); client.post("/login", data={"username": "admin", "password": "test-password"})
    first = client.post("/projects", data={"name": "First"}); first_id = int(first.location.split("/")[2])
    second = client.post("/projects", data={"name": "Second"}); second_id = int(second.location.split("/")[2])
    client.post(f"/projects/{first_id}/includes", data={"name": "Shared Core", "source": INCLUDE_SOURCE})
    missing = client.post(f"/projects/{second_id}/workbench", data={"source": ROOT_SOURCE, "action": "validate"})
    assert b"does not exist in this project" in missing.data
    same_name = client.post(f"/projects/{second_id}/includes", data={"name": "shared   core", "source": INCLUDE_SOURCE}, follow_redirects=True)
    assert b"created" in same_name.data
    with app.app_context(): assert ERInclude.query.count() == 2
