import sqlite3
from pathlib import Path

from app import create_app
from database import db
from models import AuditEvent, Portfolio, SystemProject


def make_app(tmp_path):
    return create_app({"TESTING": True, "SECRET_KEY": "test", "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path/'portfolios.db'}", "DATA_DIR": tmp_path / "data", "WTF_CSRF_ENABLED": False, "ADMIN_PASSWORD": "test-password"})


def login(client):
    return client.post("/login", data={"username": "admin", "password": "test-password"})


def test_portfolio_is_created_atomically_with_first_project(tmp_path):
    app = make_app(tmp_path); client = app.test_client(); login(client)

    response = client.post("/portfolios", data={"portfolio_name": "TAIJU", "portfolio_description": "Transformation portfolio", "project_name": "TAIJU Development", "project_description": "Initial delivery", "dialect": "sqlite"})

    assert response.status_code == 302 and "portfolio=" in response.location
    with app.app_context():
        portfolio = Portfolio.query.filter_by(slug="taiju").one()
        project = SystemProject.query.filter_by(slug="taiju-development").one()
        assert project.portfolio_id == portfolio.id
        assert AuditEvent.query.filter_by(action="portfolio.create", object_id=str(portfolio.id)).count() == 1


def test_portfolio_without_first_project_is_not_created(tmp_path):
    app = make_app(tmp_path); client = app.test_client(); login(client)

    response = client.post("/portfolios", data={"portfolio_name": "Empty"})

    assert response.status_code == 302
    with app.app_context():
        assert Portfolio.query.count() == 0


def test_dashboard_filters_and_reassigns_projects(tmp_path):
    app = make_app(tmp_path)
    with app.app_context():
        first = Portfolio(name="First", slug="first", description="")
        second = Portfolio(name="Second", slug="second", description="")
        db.session.add_all([first, second]); db.session.flush()
        project = SystemProject(name="Mover", slug="mover", description="", portfolio_id=first.id)
        db.session.add(project); db.session.commit()
        first_id, second_id, project_id = first.id, second.id, project.id
    client = app.test_client(); login(client)

    first_page = client.get(f"/?portfolio={first_id}")
    assert first_page.status_code == 200 and b"Mover" in first_page.data and b"First" in first_page.data
    moved = client.post(f"/projects/{project_id}/portfolio", data={"portfolio_id": second_id, "return_portfolio": "all"})
    assert moved.status_code == 302
    with app.app_context():
        assert db.session.get(SystemProject, project_id).portfolio_id == second_id
        assert AuditEvent.query.filter_by(action="project.portfolio.assign", object_id=str(project_id)).count() == 1


def test_new_project_can_be_created_directly_in_portfolio(tmp_path):
    app = make_app(tmp_path)
    with app.app_context():
        portfolio = Portfolio(name="Delivery", slug="delivery", description="")
        db.session.add(portfolio); db.session.commit(); portfolio_id = portfolio.id
    client = app.test_client(); login(client)

    response = client.post("/projects", data={"name": "Build", "portfolio_id": portfolio_id, "dialect": "sqlite"})

    assert response.status_code == 302
    with app.app_context():
        assert SystemProject.query.filter_by(slug="build").one().portfolio_id == portfolio_id


def test_portfolio_migration_adds_table_and_project_membership_column(tmp_path):
    connection = sqlite3.connect(tmp_path / "migration.db")
    connection.execute("CREATE TABLE system_project (id INTEGER PRIMARY KEY, name TEXT NOT NULL)")
    migration = Path("migrations/versions/0022_portfolios.sql").read_text()

    connection.executescript(migration)

    tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    columns = {row[1] for row in connection.execute("PRAGMA table_info(system_project)")}
    assert "portfolio" in tables
    assert "portfolio_id" in columns
