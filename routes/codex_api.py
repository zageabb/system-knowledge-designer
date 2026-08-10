from __future__ import annotations

import hmac
from functools import wraps

from flask import Blueprint, current_app, jsonify, request
from pydantic import BaseModel, Field, ValidationError
from database import db
from models import AuditEvent, DiagramRevision, SystemProject
from services.er_language import ERParseError, parse_er_source
from services.revisions import create_revision
from services.er_includes import include_sources
from services.settings import CODEX_CONTROL_ENABLED, get_bool

codex_api_bp = Blueprint("codex_api", __name__, url_prefix="/api/codex/v1")


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=5000)
    dialect: str = Field(default="sqlite", pattern=r"^[A-Za-z0-9_-]{1,40}$")


class SourceRequest(BaseModel):
    source: str = Field(min_length=1, max_length=1_000_000)


class RevisionCreate(SourceRequest):
    note: str = Field(default="Created through the Codex control API", max_length=5000)


def codex_access_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not get_bool(CODEX_CONTROL_ENABLED):
            return _error("codex_control_disabled", "Codex control is disabled in Control Settings.", 403)
        configured = current_app.config.get("CODEX_CONTROL_TOKEN", "")
        supplied = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
        if not configured:
            return _error("token_not_configured", "Set CODEX_CONTROL_TOKEN before enabling Codex control.", 503)
        if not supplied or not hmac.compare_digest(supplied, configured):
            return _error("unauthorised", "A valid bearer token is required.", 401)
        return view(*args, **kwargs)
    return wrapped


def _error(code: str, message: str, status: int, details=None):
    return jsonify({"ok": False, "error": {"code": code, "message": message, "details": details or []}}), status


def _payload(model_type):
    try:
        return model_type.model_validate(request.get_json(silent=True) or {})
    except ValidationError as exc:
        return _error("invalid_request", "Request validation failed.", 400, exc.errors(include_url=False))


def _audit(action: str, object_type: str, object_id, detail: str = ""):
    db.session.add(AuditEvent(action=action, object_type=object_type, object_id=str(object_id), detail=f"Codex API: {detail}"))


@codex_api_bp.get("/status")
@codex_access_required
def status():
    return {"ok": True, "service": "system-knowledge-designer", "api_version": "v1", "capabilities": ["inspect", "validate_er_source", "create_project", "create_draft_revision"], "material_changes_require_ui_confirmation": True}


@codex_api_bp.get("/projects")
@codex_access_required
def projects():
    records = SystemProject.query.order_by(SystemProject.id).all()
    return {"ok": True, "projects": [{"id": p.id, "name": p.name, "slug": p.slug, "dialect": p.dialect, "active_revision_id": p.active_revision_id, "revision_count": len(p.revisions)} for p in records]}


@codex_api_bp.get("/projects/<int:project_id>")
@codex_access_required
def project_detail(project_id):
    project = db.session.get(SystemProject, project_id)
    if project is None: return _error("not_found", "Project was not found.", 404)
    revisions = DiagramRevision.query.filter_by(project_id=project.id).order_by(DiagramRevision.revision_number.desc()).all()
    return {"ok": True, "project": {"id": project.id, "name": project.name, "slug": project.slug, "description": project.description, "platform": project.platform, "dialect": project.dialect, "active_revision_id": project.active_revision_id, "revisions": [{"id": r.id, "number": r.revision_number, "status": r.status, "model_hash": r.model_hash, "note": r.revision_note} for r in revisions]}}


@codex_api_bp.post("/validate")
@codex_access_required
def validate_source():
    payload = _payload(SourceRequest)
    if isinstance(payload, tuple): return payload
    try: model = parse_er_source(payload.source)
    except ERParseError as exc: return _error("invalid_er_source", str(exc), 422, [{"line": exc.line, "column": exc.column}])
    return {"ok": True, "model": model.model_dump(), "summary": {"tables": len(model.tables), "columns": sum(len(t.columns) for t in model.tables), "relationships": len(model.relationships)}}


@codex_api_bp.post("/projects")
@codex_access_required
def create_project():
    payload = _payload(ProjectCreate)
    if isinstance(payload, tuple): return payload
    from app import slugify
    base = slugify(payload.name) or "project"; slug = base; suffix = 2
    while SystemProject.query.filter_by(slug=slug).first(): slug, suffix = f"{base}-{suffix}", suffix + 1
    project = SystemProject(name=payload.name.strip(), slug=slug, description=payload.description, dialect=payload.dialect)
    db.session.add(project); db.session.flush(); _audit("project.create", "SystemProject", project.id, project.name); db.session.commit()
    return {"ok": True, "project": {"id": project.id, "name": project.name, "slug": project.slug}}, 201


@codex_api_bp.post("/projects/<int:project_id>/revisions")
@codex_access_required
def create_draft_revision(project_id):
    project = db.session.get(SystemProject, project_id)
    if project is None: return _error("not_found", "Project was not found.", 404)
    payload = _payload(RevisionCreate)
    if isinstance(payload, tuple): return payload
    try: model = parse_er_source(payload.source, includes=include_sources(project.id))
    except ERParseError as exc: return _error("invalid_er_source", str(exc), 422, [{"line": exc.line, "column": exc.column}])
    revision = create_revision(project, payload.source, model, payload.note)
    _audit("revision.create", "DiagramRevision", revision.id, revision.model_hash); db.session.commit()
    return {"ok": True, "revision": {"id": revision.id, "number": revision.revision_number, "status": revision.status, "model_hash": revision.model_hash}, "confirmation_required_for_approval": True}, 201
