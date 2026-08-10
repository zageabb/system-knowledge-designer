from app import create_app
from database import db
from services.readiness import readiness_report


def make_app(tmp_path):
    return create_app({"TESTING": True, "SECRET_KEY": "test", "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path/'ready.db'}", "DATA_DIR": tmp_path/"data", "WTF_CSRF_ENABLED": False, "ADMIN_PASSWORD": "test-password"})


def test_health_is_liveness_and_ready_checks_dependencies(tmp_path):
    app = make_app(tmp_path); client = app.test_client()
    health = client.get("/health")
    ready = client.get("/ready")
    assert health.status_code == 200 and health.json["status"] == "ok"
    assert ready.status_code == 200 and ready.json["status"] == "ready"
    assert set(ready.json["checks"]) == {"database", "managed_storage", "graphviz"}


def test_readiness_fails_without_storage_or_graphviz(tmp_path):
    app = make_app(tmp_path)
    missing_storage = tmp_path / "missing"
    with app.app_context():
        report, status = readiness_report(session=db.session, data_dir=missing_storage, executable_finder=lambda name: None)
    assert status == 503 and report["status"] == "not_ready"
    assert report["checks"]["managed_storage"]["status"] == "failed"
    assert report["checks"]["graphviz"]["status"] == "failed"


def test_readiness_does_not_expose_database_exception(tmp_path):
    class BrokenSession:
        def execute(self, statement): raise RuntimeError("secret database location")

    storage = tmp_path / "data"; storage.mkdir()
    report, status = readiness_report(session=BrokenSession(), data_dir=storage, executable_finder=lambda name: "/usr/bin/dot")
    assert status == 503 and report["checks"]["database"]["status"] == "failed"
    assert "secret" not in str(report)
