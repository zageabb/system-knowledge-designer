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


def test_base_layout_loads_local_tabulator_for_all_tables(tmp_path):
    app = make_app(tmp_path); client = app.test_client(); login(client)
    page = client.get("/")
    assert b"vendor/tabulator/tabulator.min.css" in page.data
    assert b"vendor/tabulator/tabulator.min.js" in page.data
    assert b"js/tabulator-app.js" in page.data
    adapter = client.get("/static/js/tabulator-app.js")
    assert adapter.status_code == 200
    assert b'querySelectorAll("table")' in adapter.data
    assert b'headerFilter = "list"' in adapter.data
    assert b'headerFilter = "input"' in adapter.data


def test_base_layout_has_keyboard_landmarks_and_visible_focus(tmp_path):
    app = make_app(tmp_path); client = app.test_client(); login(client)
    page = client.get("/")
    assert b'href="#main-content"' in page.data
    assert b'<main id="main-content" tabindex="-1">' in page.data
    assert b'<nav aria-label="Primary navigation">' in page.data
    assert b"<span>Search</span>" not in page.data
    css = client.get("/static/css/app.css")
    assert b".skip-link" in css.data and b":focus-visible" in css.data


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


def test_catalogue_always_presents_foreign_keys_as_one_to_many(tmp_path):
    app = make_app(tmp_path); client = app.test_client(); login(client)
    created = client.post("/projects", data={"name": "Relationship Catalogue", "dialect": "sqlite"})
    project_id = int(created.location.split("/")[2])
    source = '''erModel Relationship_Catalogue {
 dialect "sqlite"
 direction LR
 subjectArea Core {
  table PARENT {
   integer parent_id PK
  }
  table CHILD {
   integer child_id PK
   integer parent_id FK
  }
  relationship CHILD.parent_id -> PARENT.parent_id {
   cardinality many-to-one
   label "belongs to"
  }
 }
}'''
    saved = client.post(created.location, data={"source": source, "action": "save", "base_revision_number": "0"})
    assert saved.status_code == 200

    catalogue = client.get(f"/projects/{project_id}/catalogue")

    assert catalogue.status_code == 200
    assert b"One table" in catalogue.data and b"Many table" in catalogue.data
    assert b'name="one_table" data-relationship-table="one"' in catalogue.data
    assert b'name="many_table" data-relationship-table="many"' in catalogue.data
    assert catalogue.data.index(b'name="one_table"') < catalogue.data.index(b'name="many_table"')
    assert b'data-relationship-field="one"' in catalogue.data and b'data-relationship-field="many"' in catalogue.data
    assert b"option.hidden=option.dataset.table!==selected" in catalogue.data
    assert b'<select name="data_type"' in catalogue.data
    assert b"one-to-many" in catalogue.data
    assert b">many-to-one<" not in catalogue.data


def test_catalogue_edits_create_revision_and_regenerate_er_source(tmp_path):
    app = make_app(tmp_path); client = app.test_client(); login(client)
    created = client.post("/projects", data={"name": "Editable Catalogue", "dialect": "sqlite"})
    project_id = int(created.location.split("/")[2])
    initial = '''erModel Editable_Catalogue {
 dialect "sqlite"
 direction LR
 subjectArea Core {
  table PARENT {
   integer parent_id PK
  }
 }
}'''
    client.post(created.location, data={"source": initial, "action": "save", "base_revision_number": "0"})

    added_table = client.post(f"/projects/{project_id}/catalogue", data={"action": "add_table", "base_revision_number": "1", "name": "CHILD", "subject_area": "Core", "kind": "table"})
    assert added_table.status_code == 302 and "revision_id=" in added_table.location
    added_field = client.post(f"/projects/{project_id}/catalogue", data={"action": "add_column", "base_revision_number": "2", "table": "CHILD", "name": "parent_id", "data_type": "integer", "foreign_key": "1"})
    assert added_field.status_code == 302
    added_relationship = client.post(f"/projects/{project_id}/catalogue", data={"action": "add_relationship", "base_revision_number": "3", "one_table": "PARENT", "one_column": "parent_id", "many_table": "CHILD", "many_column": "parent_id", "label": "has children"})
    assert added_relationship.status_code == 302

    workbench = client.get(f"/projects/{project_id}/workbench")
    assert b"table CHILD" in workbench.data
    assert b"relationship CHILD.parent_id -&gt; PARENT.parent_id" in workbench.data
    assert b"has children" in workbench.data
    with app.app_context():
        revisions = DiagramRevision.query.filter_by(project_id=project_id).order_by(DiagramRevision.revision_number).all()
        assert len(revisions) == 4
        assert "table CHILD" in revisions[-1].source
