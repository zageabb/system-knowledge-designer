from app import create_app
from database import db
from models import AuditEvent, SystemProject, User


def make_app(tmp_path):
    return create_app({
        "TESTING": True,
        "SECRET_KEY": "test",
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path/'browser.db'}",
        "DATA_DIR": tmp_path / "data",
        "WTF_CSRF_ENABLED": False,
        "ADMIN_PASSWORD": "test-password",
    })


def login(client, username="admin", password="test-password"):
    return client.post("/login", data={"username": username, "password": password})


def test_admin_can_list_tables_without_exposing_password_hash(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    login(client)

    response = client.get("/data-browser?table=user")

    assert response.status_code == 200
    assert b"system_project" in response.data
    assert b"password_hash" not in response.data
    assert b"Data browser" in response.data


def test_admin_can_edit_safe_record_fields_and_action_is_audited(tmp_path):
    app = make_app(tmp_path)
    with app.app_context():
        project = SystemProject(name="Before", slug="before", description="Old")
        db.session.add(project)
        db.session.commit()
        project_id = project.id
    client = app.test_client()
    login(client)

    response = client.post(
        f"/data-browser/system_project/{project_id}/edit",
        data={"name": "After", "slug": "after", "description": "New", "platform": "SQLite", "dialect": "sqlite"},
    )

    assert response.status_code == 302
    with app.app_context():
        updated = db.session.get(SystemProject, project_id)
        assert (updated.name, updated.slug, updated.description) == ("After", "after", "New")
        event = AuditEvent.query.filter_by(action="database_record.update", object_type="system_project", object_id=str(project_id)).one()
        assert "description" in event.detail and "slug" in event.detail


def test_non_admin_cannot_open_or_edit_database_browser(tmp_path):
    app = make_app(tmp_path)
    with app.app_context():
        user = User(username="reader", is_admin=False)
        user.set_password("reader-password")
        db.session.add(user)
        project = SystemProject(name="Protected", slug="protected", description="Original")
        db.session.add(project)
        db.session.commit()
        project_id = project.id
    client = app.test_client()
    login(client, "reader", "reader-password")

    assert client.get("/data-browser").status_code == 403
    assert client.post(f"/data-browser/system_project/{project_id}/edit", data={"name": "Changed"}).status_code == 403
    with app.app_context():
        assert db.session.get(SystemProject, project_id).name == "Protected"


def test_audit_table_is_read_only(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    login(client)

    response = client.get("/data-browser?table=audit_event")

    assert response.status_code == 200
    assert b"Read only" in response.data
