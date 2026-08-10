from app import create_app
from database import db
from models import DiagramRevision, SystemProject, TableDefinition

def make_app(tmp_path):
    return create_app({"TESTING": True, "SECRET_KEY": "test", "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path/'test.db'}", "DATA_DIR": tmp_path/"data", "WTF_CSRF_ENABLED": False, "ADMIN_PASSWORD": "test-password"})

def login(client): return client.post("/login", data={"username":"admin", "password":"test-password"})

def test_login_is_required(tmp_path):
    response = make_app(tmp_path).test_client().get("/")
    assert response.status_code == 302 and "/login" in response.location


def test_base_layout_loads_scrollable_workbench_styles(tmp_path):
    app = make_app(tmp_path); client = app.test_client(); login(client)
    page = client.get("/")
    assert b"responsive.css" in page.data
    css = client.get("/static/css/responsive.css")
    assert css.status_code == 200
    assert b"overflow: auto" in css.data and b"overflow-y: auto" in css.data
    assert b"overflow-x: scroll" in css.data and b"width: max-content" in css.data


def test_notifications_render_as_floating_dismissible_toasts(tmp_path):
    app = make_app(tmp_path); client = app.test_client(); login(client)
    response = client.post("/projects", data={})
    assert response.status_code == 302
    page = client.get(response.location)
    assert b"toast-stack" in page.data and b"data-toast-close" in page.data
    assert b'class="flash' not in page.data
    css = client.get("/static/css/toasts.css")
    assert b"position: fixed" in css.data and b"z-index: 2000" in css.data

def test_project_revision_and_approval_workflow(tmp_path):
    app = make_app(tmp_path); client = app.test_client(); login(client)
    response = client.post("/projects", data={"name":"Procurement", "dialect":"sqlite"})
    assert response.status_code == 302
    project_id = int(response.location.split("/")[2])
    page = client.get(response.location)
    assert b"SUPPLIER" in page.data and b"<svg" in page.data
    source = '''erModel Procurement {
 dialect "sqlite"
 direction LR
 subjectArea Core {
  table A {\n   integer id PK\n  }
  table B {\n   integer a_id FK\n  }
  relationship B.a_id -> A.id {\n   cardinality many-to-one\n  }
 }
}'''
    saved = client.post(response.location, data={"source":source, "action":"save", "revision_note":"baseline"})
    assert saved.status_code == 200 and b"Draft revision 1 created" in saved.data
    assert saved.data.count(b'class="button"') >= 4
    assert b'aria-label="Revision export actions"' in saved.data
    with app.app_context():
        project = db.session.get(SystemProject, project_id); revision = DiagramRevision.query.one()
        assert TableDefinition.query.count() == 2 and revision.model_hash
        revision_id = revision.id
    approved = client.post(f"/projects/{project_id}/revisions/{revision_id}/approve")
    assert approved.status_code == 302
    with app.app_context():
        assert db.session.get(SystemProject, project_id).active_revision_id == revision_id
        assert db.session.get(DiagramRevision, revision_id).status == "approved"


def test_catalogue_exports_diff_restore_and_conflict_detection(tmp_path):
    app = make_app(tmp_path); client = app.test_client(); login(client)
    created = client.post("/projects", data={"name": "Revision Lab", "dialect": "sqlite"})
    project_id = int(created.location.split("/")[2]); workbench = created.location
    source1 = '''erModel Revision_Lab {\n dialect "sqlite"\n direction LR\n subjectArea Core {\n  table ITEM {\n   integer item_id PK\n  }\n }\n}'''
    source2 = source1.replace("integer item_id PK", "integer item_id PK\n   string item_name not_null")
    first = client.post(workbench, data={"source": source1, "action": "save", "base_revision_number": "0", "revision_note": "first"})
    assert first.status_code == 200
    second = client.post(workbench, data={"source": source2, "action": "save", "base_revision_number": "1", "revision_note": "second"})
    assert second.status_code == 200
    conflict = client.post(workbench, data={"source": source1, "action": "save", "base_revision_number": "1"})
    assert conflict.status_code == 409 and b"changed after the editor was opened" in conflict.data
    with app.app_context():
        revisions = DiagramRevision.query.filter_by(project_id=project_id).order_by(DiagramRevision.revision_number).all()
        first_id, second_id = revisions[0].id, revisions[1].id
    catalogue = client.get(f"/projects/{project_id}/catalogue?revision_id={second_id}")
    assert catalogue.status_code == 200 and b"item_name" in catalogue.data
    source_export = client.get(f"/projects/{project_id}/revisions/{second_id}/source.erd")
    assert source_export.status_code == 200 and b"item_name" in source_export.data
    model_export = client.get(f"/projects/{project_id}/revisions/{second_id}/model.json")
    assert model_export.status_code == 200 and model_export.json["tables"][0]["columns"][1]["name"] == "item_name"
    comparison = client.get(f"/projects/{project_id}/revisions/{first_id}/compare/{second_id}")
    assert comparison.status_code == 200 and b"+   string item_name not_null" in comparison.data
    restored = client.post(f"/projects/{project_id}/revisions/{first_id}/restore")
    assert restored.status_code == 302
    with app.app_context():
        latest = DiagramRevision.query.filter_by(project_id=project_id).order_by(DiagramRevision.revision_number.desc()).first()
        assert latest.revision_number == 3 and latest.status == "draft" and latest.source == source1
