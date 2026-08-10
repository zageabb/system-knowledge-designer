import json
from io import BytesIO

from app import create_app
from database import db
from models import CrossProjectAttachment, ProjectAlias, ProjectIntegrityScan, ProjectLink, SystemProject
from services.project_graph import ProjectGraphError, normalize_alias, scan_project_integrity, traverse_projects, validate_project_link
from tests.test_sandbox_sql import prepare


def make_app(tmp_path):
    return create_app({"TESTING": True, "SECRET_KEY": "test", "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path/'graph.db'}", "DATA_DIR": tmp_path/"data", "WTF_CSRF_ENABLED": False, "ADMIN_PASSWORD": "test-password"})


def test_alias_normalization_link_validation_and_bounded_traversal():
    assert normalize_alias("  Order--Management ") == "order management"
    try:
        validate_project_link(1, 1, "depends-on")
        assert False
    except ProjectGraphError:
        pass
    links = [ProjectLink(id=1, source_project_id=1, target_project_id=2, relationship_type="depends-on", created_by="a"), ProjectLink(id=2, source_project_id=2, target_project_id=3, relationship_type="integrates-with", created_by="a")]
    assert traverse_projects(1, links, max_depth=1) == [{"project_id": 2, "depth": 1, "via_link_id": 1}]


def test_system_map_persists_links_trusted_aliases_traversal_and_scan(tmp_path):
    app = make_app(tmp_path); client = app.test_client(); client.post("/login", data={"username": "admin", "password": "test-password"})
    with app.app_context():
        first = SystemProject(name="Orders", slug="orders"); second = SystemProject(name="Suppliers", slug="suppliers")
        db.session.add_all([first, second]); db.session.commit(); first_id, second_id = first.id, second.id
    linked = client.post("/system-map", data={"action": "link", "source_project_id": first_id, "target_project_id": second_id, "relationship_type": "depends-on", "label": "supplier master"}, follow_redirects=True)
    assert b"Project link created" in linked.data and b"supplier master" in linked.data
    aliased = client.post("/system-map", data={"action": "alias", "project_id": second_id, "alias": "Vendor Master", "trusted": "on"}, follow_redirects=True)
    assert b"trusted" in aliased.data and b"Vendor Master" in aliased.data
    traversed = client.get(f"/system-map?project_id={first_id}")
    assert b"Depth 1" in traversed.data and b"Suppliers" in traversed.data
    scanned = client.post("/system-map", data={"action": "scan"}, follow_redirects=True)
    assert b"0 issue(s)" in scanned.data
    with app.app_context():
        assert ProjectLink.query.count() == 1
        assert ProjectAlias.query.one().trusted is True
        scan = ProjectIntegrityScan.query.one(); assert scan.status == "clean" and json.loads(scan.results_json) == []


def test_system_map_rejects_self_links_and_duplicate_aliases(tmp_path):
    app = make_app(tmp_path); client = app.test_client(); client.post("/login", data={"username": "admin", "password": "test-password"})
    with app.app_context():
        project = SystemProject(name="Orders", slug="orders"); db.session.add(project); db.session.commit(); project_id = project.id
    rejected = client.post("/system-map", data={"action": "link", "source_project_id": project_id, "target_project_id": project_id, "relationship_type": "depends-on"}, follow_redirects=True)
    assert b"cannot link to itself" in rejected.data
    client.post("/system-map", data={"action": "alias", "project_id": project_id, "alias": "Order Hub"})
    duplicate = client.post("/system-map", data={"action": "alias", "project_id": project_id, "alias": "order---hub"}, follow_redirects=True)
    assert b"UNIQUE constraint failed" in duplicate.data
    with app.app_context(): assert ProjectAlias.query.count() == 1


def test_selected_attachment_and_trusted_alias_are_explicitly_federated(tmp_path):
    app = make_app(tmp_path); source_id, _, _ = prepare(app); client = app.test_client(); client.post("/login", data={"username": "admin", "password": "test-password"})
    with app.app_context():
        consumer = SystemProject(name="Buying Portal", slug="buying-portal"); db.session.add(consumer); db.session.commit(); consumer_id = consumer.id
    uploaded = client.post(f"/projects/{source_id}/knowledge", data={"document": (BytesIO(b"Supplier onboarding assurance controls"), "assurance.txt")}, content_type="multipart/form-data")
    assert uploaded.status_code == 302
    linked = client.post("/system-map", data={"action": "link", "source_project_id": consumer_id, "target_project_id": source_id, "relationship_type": "depends-on"})
    assert linked.status_code == 302
    with app.app_context():
        from models import KnowledgeDocument
        document_id = KnowledgeDocument.query.one().id
    attached = client.post("/system-map", data={"action": "attach", "consumer_project_id": consumer_id, "document_id": document_id}, follow_redirects=True)
    assert b"Selected document attached" in attached.data
    client.post("/system-map", data={"action": "alias", "project_id": source_id, "alias": "Vendor Master", "trusted": "on"})
    document_search = client.get(f"/projects/{consumer_id}/knowledge?q=onboarding&source=cross-project")
    assert b"Explicit cross-project evidence" in document_search.data and b"assurance.txt" in document_search.data
    alias_search = client.get(f"/projects/{consumer_id}/knowledge?q=Vendor+Master+supplier&source=cross-project")
    assert b"alias: Vendor Master" in alias_search.data and b"SUPPLIER" in alias_search.data
    with app.app_context():
        assert CrossProjectAttachment.query.count() == 1
        db.session.delete(ProjectLink.query.one()); db.session.commit()
        assert scan_project_integrity() == [{"type": "unlinked-attachment-projects", "attachment_id": CrossProjectAttachment.query.one().id}]


def test_attachment_requires_an_explicit_project_link(tmp_path):
    app = make_app(tmp_path); source_id, _, _ = prepare(app); client = app.test_client(); client.post("/login", data={"username": "admin", "password": "test-password"})
    with app.app_context():
        consumer = SystemProject(name="Isolated", slug="isolated"); db.session.add(consumer); db.session.commit(); consumer_id = consumer.id
    client.post(f"/projects/{source_id}/knowledge", data={"document": (BytesIO(b"Public architecture note"), "note.txt")}, content_type="multipart/form-data")
    with app.app_context():
        from models import KnowledgeDocument
        document_id = KnowledgeDocument.query.one().id
    rejected = client.post("/system-map", data={"action": "attach", "consumer_project_id": consumer_id, "document_id": document_id}, follow_redirects=True)
    assert b"explicit project link" in rejected.data
    with app.app_context(): assert CrossProjectAttachment.query.count() == 0
