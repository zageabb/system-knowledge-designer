import json

import pytest

import app as app_module
from app import create_app
from database import db
from models import DocumentVersion, ExternalResearchJob, ExternalResearchJobEvent, ExternalResearchPromotion, KnowledgeDocument
from services.external_research import ExternalResearchError, ResearchCitation, sanitise_external_query
from services.knowledge import search_documents
from services.settings import EXTERNAL_RESEARCH_ENABLED, set_bool
from tests.test_sandbox_sql import prepare


def make_app(tmp_path):
    return create_app({"TESTING": True, "SECRET_KEY": "test", "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path/'research.db'}", "DATA_DIR": tmp_path/"data", "WTF_CSRF_ENABLED": False, "ADMIN_PASSWORD": "test-password"})


def test_privacy_sanitiser_removes_sensitive_shapes_and_bounds_terms():
    query = 'Research "Secret supplier contract" owner@example.com 192.168.1.9 123456789 public procurement onboarding governance standards guidance controls'
    outbound = sanitise_external_query(query)
    assert "Secret" not in outbound and "example" not in outbound and "192" not in outbound and "123456789" not in outbound
    assert len(outbound.split()) <= 12 and "public procurement" in outbound
    with pytest.raises(ExternalResearchError, match="too specific"):
        sanitise_external_query("owner@example.com 123456789")


def test_research_requires_review_and_disabled_mode_never_calls_provider(tmp_path, monkeypatch):
    app = make_app(tmp_path); project_id, revision_id, dataset_id = prepare(app); client = app.test_client(); client.post("/login", data={"username": "admin", "password": "test-password"})
    called = []
    monkeypatch.setattr(app_module, "search_wikipedia", lambda query: called.append(query))
    prepared = client.post(f"/projects/{project_id}/research", data={"query": "public procurement supplier onboarding"}, follow_redirects=True)
    assert prepared.status_code == 200 and b"Exact outbound query" in prepared.data and b"Local-only mode" in prepared.data
    with app.app_context(): job = ExternalResearchJob.query.one(); job_id = job.id; assert job.status == "proposed"
    blocked = client.post(f"/projects/{project_id}/research/{job_id}/send", follow_redirects=True)
    assert b"External research is disabled" in blocked.data and called == []
    with app.app_context(): assert db.session.get(ExternalResearchJob, job_id).status == "proposed"


def test_confirmed_research_persists_citations_and_failure_is_local_only(tmp_path, monkeypatch):
    app = make_app(tmp_path); project_id, revision_id, dataset_id = prepare(app); client = app.test_client(); client.post("/login", data={"username": "admin", "password": "test-password"})
    with app.app_context(): set_bool(EXTERNAL_RESEARCH_ENABLED, True); db.session.commit()
    monkeypatch.setattr(app_module, "search_wikipedia", lambda query: [ResearchCitation(title="Procurement", url="https://en.wikipedia.org/?curid=1", excerpt="Public purchasing")])
    client.post(f"/projects/{project_id}/research", data={"query": "public procurement governance"})
    with app.app_context(): first_id = ExternalResearchJob.query.one().id
    completed = client.post(f"/projects/{project_id}/research/{first_id}/send", follow_redirects=True)
    assert completed.status_code == 200 and b"Public purchasing" in completed.data
    with app.app_context():
        first = db.session.get(ExternalResearchJob, first_id); assert first.status == "completed" and json.loads(first.results_json)[0]["title"] == "Procurement"
    monkeypatch.setattr(app_module, "search_wikipedia", lambda query: (_ for _ in ()).throw(ExternalResearchError("offline")))
    client.post(f"/projects/{project_id}/research", data={"query": "supplier assurance standards"})
    with app.app_context(): failed_id = ExternalResearchJob.query.order_by(ExternalResearchJob.id.desc()).first().id
    failed = client.post(f"/projects/{project_id}/research/{failed_id}/send", follow_redirects=True)
    assert b"No local data changed" in failed.data and b"Local knowledge search" in failed.data
    with app.app_context(): assert db.session.get(ExternalResearchJob, failed_id).status == "failed"


def test_selected_citation_is_explicitly_promoted_once_with_provenance(tmp_path, monkeypatch):
    app = make_app(tmp_path); project_id, revision_id, dataset_id = prepare(app); client = app.test_client(); client.post("/login", data={"username": "admin", "password": "test-password"})
    with app.app_context(): set_bool(EXTERNAL_RESEARCH_ENABLED, True); db.session.commit()
    monkeypatch.setattr(app_module, "search_wikipedia", lambda query: [ResearchCitation(title="Supplier assurance", url="https://en.wikipedia.org/?curid=42", excerpt="Assurance evaluates supplier controls and governance.")])
    client.post(f"/projects/{project_id}/research", data={"query": "supplier assurance governance"})
    with app.app_context(): job_id = ExternalResearchJob.query.one().id
    client.post(f"/projects/{project_id}/research/{job_id}/send")
    promoted = client.post(f"/projects/{project_id}/research/{job_id}/citations/0/promote", follow_redirects=True)
    assert promoted.status_code == 200 and b"Added &#39;Supplier assurance&#39;" in promoted.data and b"Local document #" in promoted.data
    with app.app_context():
        document = KnowledgeDocument.query.one(); promotion = ExternalResearchPromotion.query.one()
        assert document.provenance == "external-wikipedia" and document.classification == "public"
        assert promotion.document_id == document.id and DocumentVersion.query.filter_by(document_id=document.id).count() == 1
        assert search_documents(project_id=project_id, query="supplier controls")[0]["chunk_id"] == document.chunks[0].id
    duplicate = client.post(f"/projects/{project_id}/research/{job_id}/citations/0/promote", follow_redirects=True)
    assert b"already in local knowledge" in duplicate.data
    with app.app_context(): assert KnowledgeDocument.query.count() == 1


def test_cancel_and_retry_never_send_without_a_new_confirmation(tmp_path, monkeypatch):
    app = make_app(tmp_path); project_id, revision_id, dataset_id = prepare(app); client = app.test_client(); client.post("/login", data={"username": "admin", "password": "test-password"})
    calls = []
    monkeypatch.setattr(app_module, "search_wikipedia", lambda query: calls.append(query))
    client.post(f"/projects/{project_id}/research", data={"query": "public supplier assurance"})
    with app.app_context(): proposed_id = ExternalResearchJob.query.one().id
    cancelled = client.post(f"/projects/{project_id}/research/{proposed_id}/cancel", follow_redirects=True)
    assert b"cancelled without sending" in cancelled.data and calls == []
    with app.app_context():
        assert db.session.get(ExternalResearchJob, proposed_id).status == "cancelled"
        assert ExternalResearchJobEvent.query.filter_by(job_id=proposed_id, event_type="cancelled").count() == 1
        failed = ExternalResearchJob(project_id=project_id, original_query="supplier governance", outbound_query="supplier governance", provider="Wikipedia", status="failed", error="offline", requested_by="admin")
        db.session.add(failed); db.session.commit(); failed_id = failed.id
    retried = client.post(f"/projects/{project_id}/research/{failed_id}/retry", follow_redirects=True)
    assert b"Review and confirm before sending" in retried.data and b"retry of #" in retried.data and calls == []
    with app.app_context():
        retry = ExternalResearchJob.query.filter_by(status="proposed").one(); event = ExternalResearchJobEvent.query.filter_by(job_id=failed_id, event_type="retried").one()
        assert event.related_job_id == retry.id and retry.outbound_query == "supplier governance"


def test_running_research_can_be_cancelled_and_late_results_are_discarded(tmp_path, monkeypatch):
    app = make_app(tmp_path); project_id, _, _ = prepare(app); client = app.test_client(); client.post("/login", data={"username": "admin", "password": "test-password"})
    queued = []
    app.config["RESEARCH_TASK_SUBMITTER"] = queued.append
    with app.app_context(): set_bool(EXTERNAL_RESEARCH_ENABLED, True); db.session.commit()
    monkeypatch.setattr(app_module, "search_wikipedia", lambda query: [ResearchCitation(title="Late", url="https://en.wikipedia.org/?curid=9", excerpt="Must not persist")])
    client.post(f"/projects/{project_id}/research", data={"query": "public supplier governance"})
    with app.app_context(): job_id = ExternalResearchJob.query.one().id
    started = client.post(f"/projects/{project_id}/research/{job_id}/send", follow_redirects=True)
    assert b"started in the background" in started.data and len(queued) == 1
    with app.app_context(): assert db.session.get(ExternalResearchJob, job_id).status == "running"
    cancelled = client.post(f"/projects/{project_id}/research/{job_id}/cancel", follow_redirects=True)
    assert b"late provider response will be discarded" in cancelled.data
    queued[0]()
    with app.app_context():
        job = db.session.get(ExternalResearchJob, job_id)
        assert job.status == "cancelled" and json.loads(job.results_json) == []
        event = ExternalResearchJobEvent.query.filter_by(job_id=job_id, event_type="cancelled").one()
        assert "after provider request" in event.detail and job.cancel_requested_at is not None
