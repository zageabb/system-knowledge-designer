from __future__ import annotations

import json
import re
import sqlite3
from uuid import uuid4
from pathlib import Path

from flask import Flask, flash, redirect, render_template, request, send_file, url_for
from flask_login import LoginManager, current_user, login_required, login_user, logout_user
from flask_wtf import CSRFProtect
from sqlalchemy.exc import IntegrityError

from config import Config
from database import db
from models import AIAction, AssistantContextLink, AssistantExchange, AssistantToolCall, AuditEvent, ChunkKnowledgeLink, CrossProjectAttachment, DiagramRevision, DocumentChunk, DocumentVersion, ERInclude, EvidenceRecord, ExternalResearchJob, ExternalResearchJobEvent, ExternalResearchPromotion, KnowledgeDocument, KnowledgeLink, ProjectAlias, ProjectIntegrityScan, ProjectLink, RelationshipDefinition, SampleDataset, SampleRowDefinition, SandboxBuild, SQLExecution, SystemProject, TableDefinition, User, utcnow
from services.er_language import ERParseError, parse_er_source
from services.graph_renderer import model_to_dot, render_graphviz, render_graphviz_bytes
from services.revisions import create_revision, revision_model, unified_source_diff
from services.settings import CODEX_CONTROL_ENABLED, EXTERNAL_RESEARCH_ENABLED, get_bool, get_text, set_bool, set_text
from routes.codex_api import codex_api_bp
from services.sample_data import SampleValidationError, validate_dataset_relationships, validate_row
from services.sandbox import build_sandbox
from services.sql_safety import SQLValidationError, execute_readonly, validate_readonly_sql
from services.ai_sample_rows import AIRecordGenerationError, generate_record_proposal, validate_relationship_references
from services.ollama import OllamaError
from services.knowledge import KnowledgeIngestionError, ensure_fts_index, ingest_document, ingest_external_citation, remove_from_fts, search_documents
from services.federated_search import knowledge_coverage, search_cross_project_evidence, search_relationships, search_sample_values, search_schema
from services.grounded_assistant import GroundedAnswerError, generate_grounded_answer, plan_read_tools
from services.ai_sql import SQLProposalError, generate_sql_proposal
from services.assistant_tools import AssistantToolError, READ_TOOLS, execute_read_tool
from services.assistant_actions import AssistantActionError, KnowledgeLinkProposal, apply_chunk_link, apply_knowledge_link, plan_mutation_actions
from services.external_research import ExternalResearchError, sanitise_external_query, search_wikipedia, submit_research_task
from services.project_graph import ProjectGraphError, RELATIONSHIP_TYPES, normalize_alias, projects_are_linked, scan_project_integrity, traverse_projects, validate_project_link
from services.er_includes import include_sources, normalize_include_name
from services.readiness import readiness_report
from services.catalogue_editor import CatalogueEditError, edit_catalogue

login_manager = LoginManager()
csrf = CSRFProtect()


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")


def _dataset_rows(dataset, replacement=None, excluded_row_id=None):
    rows_by_table = {}
    for row in dataset.rows:
        if row.id == excluded_row_id:
            continue
        values = replacement[1] if replacement and row.id == replacement[0] else json.loads(row.values_json)
        rows_by_table.setdefault(row.table_name, []).append(values)
    return rows_by_table


def create_app(config_overrides: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)
    if config_overrides: app.config.update(config_overrides)
    if "RESEARCH_TASK_SUBMITTER" not in app.config:
        app.config["RESEARCH_TASK_SUBMITTER"] = (lambda task: task()) if app.config.get("TESTING") else submit_research_task
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    app.config["DATA_DIR"] = Path(app.config["DATA_DIR"])
    app.config["DATA_DIR"].mkdir(parents=True, exist_ok=True)
    app.jinja_env.filters["from_json"] = json.loads
    db.init_app(app); login_manager.init_app(app); csrf.init_app(app)
    app.register_blueprint(codex_api_bp)
    csrf.exempt(codex_api_bp)
    login_manager.login_view = "login"

    @login_manager.user_loader
    def load_user(user_id):
        try:
            database_id = int(user_id)
        except (TypeError, ValueError):
            return None
        return db.session.get(User, database_id)

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            user = User.query.filter_by(username=request.form.get("username", "").strip()).first()
            if user and user.check_password(request.form.get("password", "")):
                login_user(user); return redirect(url_for("dashboard"))
            flash("Invalid username or password.", "danger")
        return render_template("login.html")

    @app.post("/logout")
    @login_required
    def logout(): logout_user(); return redirect(url_for("login"))

    @app.route("/")
    @login_required
    def dashboard():
        projects = SystemProject.query.order_by(SystemProject.updated_at.desc()).all()
        return render_template("dashboard.html", projects=projects)

    @app.route("/system-map", methods=["GET", "POST"])
    @login_required
    def system_map():
        if request.method == "POST":
            action = request.form.get("action")
            try:
                if action == "link":
                    source_id = request.form.get("source_project_id", type=int); target_id = request.form.get("target_project_id", type=int)
                    relationship_type = validate_project_link(source_id, target_id, request.form.get("relationship_type", ""))
                    if not db.session.get(SystemProject, source_id) or not db.session.get(SystemProject, target_id): raise ProjectGraphError("Both linked projects must exist.")
                    link = ProjectLink(source_project_id=source_id, target_project_id=target_id, relationship_type=relationship_type, label=request.form.get("label", "").strip()[:200], created_by=current_user.username)
                    db.session.add(link); db.session.flush(); audit("project_link.create", "ProjectLink", link.id); db.session.commit(); flash("Project link created.", "success")
                elif action == "alias":
                    project_id = request.form.get("project_id", type=int)
                    if not db.session.get(SystemProject, project_id): raise ProjectGraphError("Project does not exist.")
                    trusted = request.form.get("trusted") == "on" and current_user.is_admin
                    alias = ProjectAlias(project_id=project_id, alias=request.form.get("alias", "").strip()[:160], normalized_alias=normalize_alias(request.form.get("alias", "")), trusted=trusted, created_by=current_user.username)
                    db.session.add(alias); db.session.flush(); audit("project_alias.create", "ProjectAlias", alias.id, f"trusted={trusted}"); db.session.commit(); flash("Project alias added.", "success")
                elif action == "scan":
                    issues = scan_project_integrity(); scan = ProjectIntegrityScan(status="issues" if issues else "clean", results_json=json.dumps(issues, sort_keys=True), issue_count=len(issues), requested_by=current_user.username)
                    db.session.add(scan); db.session.flush(); audit("project_integrity.scan", "ProjectIntegrityScan", scan.id, f"issues={len(issues)}"); db.session.commit(); flash(f"Integrity scan completed with {len(issues)} issue(s).", "success")
                elif action == "attach":
                    consumer_id = request.form.get("consumer_project_id", type=int); document_id = request.form.get("document_id", type=int)
                    document = db.session.get(KnowledgeDocument, document_id)
                    if not document or not db.session.get(SystemProject, consumer_id): raise ProjectGraphError("Consumer project and source document must exist.")
                    if consumer_id == document.project_id: raise ProjectGraphError("Cross-project attachments require two different projects.")
                    if not projects_are_linked(consumer_id, document.project_id): raise ProjectGraphError("Projects must have an explicit project link before attaching evidence.")
                    attachment = CrossProjectAttachment(consumer_project_id=consumer_id, source_project_id=document.project_id, document_id=document.id, created_by=current_user.username)
                    db.session.add(attachment); db.session.flush(); audit("cross_project_attachment.create", "CrossProjectAttachment", attachment.id, f"document={document.id}"); db.session.commit(); flash("Selected document attached to consumer project.", "success")
            except (ProjectGraphError, IntegrityError) as exc:
                db.session.rollback(); flash(str(getattr(exc, "orig", exc)), "danger")
            return redirect(url_for("system_map"))
        projects = SystemProject.query.order_by(SystemProject.name).all(); links = ProjectLink.query.order_by(ProjectLink.id.desc()).all(); aliases = ProjectAlias.query.order_by(ProjectAlias.id.desc()).all(); attachments = CrossProjectAttachment.query.order_by(CrossProjectAttachment.id.desc()).all(); attachable_documents = KnowledgeDocument.query.order_by(KnowledgeDocument.title).all()
        selected_id = request.args.get("project_id", type=int); traversal = traverse_projects(selected_id, links) if selected_id else []
        project_by_id = {project.id: project for project in projects}; latest_scan = ProjectIntegrityScan.query.order_by(ProjectIntegrityScan.id.desc()).first()
        return render_template("system_map.html", projects=projects, links=links, aliases=aliases, attachments=attachments, attachable_documents=attachable_documents, relationship_types=sorted(RELATIONSHIP_TYPES), selected_id=selected_id, traversal=traversal, project_by_id=project_by_id, latest_scan=latest_scan)

    @app.post("/system-map/attachments/<int:attachment_id>/delete")
    @login_required
    def delete_cross_project_attachment(attachment_id):
        attachment = db.get_or_404(CrossProjectAttachment, attachment_id)
        audit("cross_project_attachment.delete", "CrossProjectAttachment", attachment.id, f"document={attachment.document_id}")
        db.session.delete(attachment); db.session.commit(); flash("Cross-project document attachment removed.", "success")
        return redirect(url_for("system_map"))

    @app.post("/projects")
    @login_required
    def create_project_route():
        name = request.form.get("name", "").strip()
        if not name: flash("Project name is required.", "danger"); return redirect(url_for("dashboard"))
        base = slugify(name) or "project"; slug = base; suffix = 2
        while SystemProject.query.filter_by(slug=slug).first(): slug, suffix = f"{base}-{suffix}", suffix + 1
        project = SystemProject(name=name, slug=slug, description=request.form.get("description", "").strip(), dialect=request.form.get("dialect", "sqlite"))
        db.session.add(project); db.session.flush(); audit("project.create", "SystemProject", project.id, name); db.session.commit()
        return redirect(url_for("workbench", project_id=project.id))

    @app.route("/projects/<int:project_id>/workbench", methods=["GET", "POST"])
    @login_required
    def workbench(project_id):
        project = db.get_or_404(SystemProject, project_id)
        managed_includes = ERInclude.query.filter_by(project_id=project.id).order_by(ERInclude.name).all()
        latest = DiagramRevision.query.filter_by(project_id=project.id).order_by(DiagramRevision.revision_number.desc()).first()
        source = request.form.get("source") if request.method == "POST" else (latest.source if latest else starter_source(project.name))
        model = None; dot = None; preview_svg = None; error = None
        try:
            model = parse_er_source(source, includes=include_sources(project.id)); dot = model_to_dot(model)
            preview_svg = render_graphviz_bytes(dot, "svg").decode("utf-8")
            if request.method == "POST" and request.form.get("action") == "save":
                expected = request.form.get("base_revision_number", type=int)
                current_number = latest.revision_number if latest else 0
                if expected is not None and expected != current_number:
                    flash(f"This project changed after the editor was opened (expected r{expected}, now r{current_number}). Reload and reapply your changes.", "danger")
                    return render_template("workbench.html", project=project, source=source, model=model, dot=dot, preview_svg=preview_svg, error=None, latest=latest, managed_includes=managed_includes), 409
                latest = create_revision(project, source, model, request.form.get("revision_note", "")); audit("revision.create", "DiagramRevision", latest.id, latest.model_hash); db.session.commit(); flash(f"Draft revision {latest.revision_number} created.", "success")
            elif request.method == "POST": flash("Source is valid.", "success")
        except ERParseError as exc:
            location = f"Line {exc.line}, column {exc.column}: " if exc.line else ""
            error = location + str(exc)
        except (RuntimeError, FileNotFoundError) as exc:
            error = f"Graphviz preview is unavailable: {exc}"
        return render_template("workbench.html", project=project, source=source, model=model, dot=dot, preview_svg=preview_svg, error=error, latest=latest, managed_includes=managed_includes)

    @app.post("/projects/<int:project_id>/includes")
    @login_required
    def create_er_include(project_id):
        project = db.get_or_404(SystemProject, project_id); name = request.form.get("name", "").strip(); source = request.form.get("source", "").strip()
        try:
            normalized = normalize_include_name(name)
            if not source: raise ValueError("Include source is required.")
            if ERInclude.query.filter_by(project_id=project.id, normalized_name=normalized).first(): raise ValueError("That managed include name already exists in this project.")
            candidate_sources = include_sources(project.id); candidate_sources[normalized] = source
            parse_er_source(source, includes=candidate_sources)
            record = ERInclude(project_id=project.id, name=name[:160], normalized_name=normalized, source=source, created_by=current_user.username)
            db.session.add(record); db.session.flush(); audit("er_include.create", "ERInclude", record.id, f"project={project.id} name={normalized}"); db.session.commit(); flash(f"Managed include '{name}' created.", "success")
        except (ValueError, ERParseError) as exc:
            db.session.rollback(); flash(str(exc), "danger")
        return redirect(url_for("workbench", project_id=project.id))

    @app.post("/projects/<int:project_id>/includes/<int:include_id>/delete")
    @login_required
    def delete_er_include(project_id, include_id):
        project = db.get_or_404(SystemProject, project_id); record = db.get_or_404(ERInclude, include_id)
        if record.project_id != project.id: return ("Include does not belong to project", 400)
        name = record.name; audit("er_include.delete", "ERInclude", record.id, f"name={record.normalized_name}"); db.session.delete(record); db.session.commit(); flash(f"Managed include '{name}' deleted. Existing revisions retain their resolved model snapshots.", "success")
        return redirect(url_for("workbench", project_id=project.id))

    @app.post("/projects/<int:project_id>/revisions/<int:revision_id>/approve")
    @login_required
    def approve_revision(project_id, revision_id):
        project = db.get_or_404(SystemProject, project_id); revision = db.get_or_404(DiagramRevision, revision_id)
        if revision.project_id != project.id: return ("Revision does not belong to project", 400)
        DiagramRevision.query.filter_by(project_id=project.id, status="approved").update({"status": "inactive"})
        revision.status = "approved"; revision.approved_at = utcnow(); project.active_revision_id = revision.id
        audit("revision.approve", "DiagramRevision", revision.id, f"revision {revision.revision_number}"); db.session.commit()
        flash(f"Revision {revision.revision_number} approved.", "success"); return redirect(url_for("workbench", project_id=project.id))

    @app.get("/projects/<int:project_id>/revisions/<int:revision_id>/render.<format_name>")
    @login_required
    def export_render(project_id, revision_id, format_name):
        revision = db.get_or_404(DiagramRevision, revision_id)
        if revision.project_id != project_id or format_name not in {"svg", "png"}: return ("Invalid export", 400)
        model = revision_model(revision); scale = max(1, min(int(request.args.get("scale", 1)), 8))
        path = app.config["DATA_DIR"] / str(project_id) / "renders" / f"r{revision.revision_number}-{scale}x.{format_name}"
        try: render_graphviz(model_to_dot(model), path, format_name, scale)
        except (RuntimeError, FileNotFoundError) as exc: return (f"Graphviz is unavailable: {exc}", 503)
        return send_file(path, as_attachment=True, download_name=f"{revision.project.slug}-r{revision.revision_number}.{format_name}")

    @app.get("/projects/<int:project_id>/revisions")
    @login_required
    def revisions(project_id):
        project = db.get_or_404(SystemProject, project_id)
        records = DiagramRevision.query.filter_by(project_id=project.id).order_by(DiagramRevision.revision_number.desc()).all()
        return render_template("revisions.html", project=project, revisions=records)

    @app.route("/projects/<int:project_id>/catalogue", methods=["GET", "POST"])
    @login_required
    def catalogue(project_id):
        project = db.get_or_404(SystemProject, project_id)
        latest = DiagramRevision.query.filter_by(project_id=project.id).order_by(DiagramRevision.revision_number.desc()).first()
        revision_id = request.args.get("revision_id", type=int) or (latest.id if latest else None)
        revision = db.session.get(DiagramRevision, revision_id) if revision_id else None
        if revision and revision.project_id != project.id: return ("Revision does not belong to project", 400)
        if request.method == "POST":
            if latest is None: flash("Create the first ER revision before editing the catalogue.", "danger"); return redirect(url_for("workbench", project_id=project.id))
            expected = request.form.get("base_revision_number", type=int)
            if expected != latest.revision_number:
                flash(f"This project changed after the catalogue was opened (expected r{expected}, now r{latest.revision_number}). Reload and reapply your changes.", "danger")
                return redirect(url_for("catalogue", project_id=project.id)), 409
            try:
                model, source = edit_catalogue(revision_model(latest), request.form.get("action", ""), request.form)
                created = create_revision(project, source, model, request.form.get("revision_note", "Catalogue edit"))
                audit("catalogue.edit", "DiagramRevision", created.id, f"action={request.form.get('action', '')}")
                db.session.commit(); flash(f"Catalogue updated in draft revision {created.revision_number}; ER source and diagram regenerated.", "success")
                return redirect(url_for("catalogue", project_id=project.id, revision_id=created.id))
            except CatalogueEditError as exc:
                db.session.rollback(); flash(str(exc), "danger")
                return redirect(url_for("catalogue", project_id=project.id, revision_id=latest.id))
        tables = TableDefinition.query.filter_by(project_id=project.id, revision_id=revision_id).order_by(TableDefinition.subject_area, TableDefinition.name).all() if revision_id else []
        relationships = RelationshipDefinition.query.filter_by(project_id=project.id, revision_id=revision_id).order_by(RelationshipDefinition.source_table).all() if revision_id else []
        editable = bool(revision and latest and revision.id == latest.id)
        return render_template("catalogue.html", project=project, revision=revision, tables=tables, relationships=relationships, editable=editable)

    @app.get("/projects/<int:project_id>/revisions/<int:revision_id>/source.erd")
    @login_required
    def export_source(project_id, revision_id):
        project = db.get_or_404(SystemProject, project_id); revision = db.get_or_404(DiagramRevision, revision_id)
        if revision.project_id != project.id: return ("Revision does not belong to project", 400)
        return app.response_class(revision.source, mimetype="text/plain", headers={"Content-Disposition": f'attachment; filename="{project.slug}-r{revision.revision_number}.erd"'})

    @app.get("/projects/<int:project_id>/revisions/<int:revision_id>/model.json")
    @login_required
    def export_model(project_id, revision_id):
        project = db.get_or_404(SystemProject, project_id); revision = db.get_or_404(DiagramRevision, revision_id)
        if revision.project_id != project.id: return ("Revision does not belong to project", 400)
        return app.response_class(json.dumps(json.loads(revision.model_json), indent=2), mimetype="application/json", headers={"Content-Disposition": f'attachment; filename="{project.slug}-r{revision.revision_number}.json"'})

    @app.get("/projects/<int:project_id>/revisions/<int:older_id>/compare/<int:newer_id>")
    @login_required
    def compare_revisions(project_id, older_id, newer_id):
        project = db.get_or_404(SystemProject, project_id); older = db.get_or_404(DiagramRevision, older_id); newer = db.get_or_404(DiagramRevision, newer_id)
        if older.project_id != project.id or newer.project_id != project.id: return ("Revision does not belong to project", 400)
        return render_template("revision_diff.html", project=project, older=older, newer=newer, source_diff=unified_source_diff(older, newer))

    @app.post("/projects/<int:project_id>/revisions/<int:revision_id>/restore")
    @login_required
    def restore_revision(project_id, revision_id):
        project = db.get_or_404(SystemProject, project_id); original = db.get_or_404(DiagramRevision, revision_id)
        if original.project_id != project.id: return ("Revision does not belong to project", 400)
        restored = create_revision(project, original.source, revision_model(original), f"Restored from revision {original.revision_number}")
        audit("revision.restore", "DiagramRevision", restored.id, f"from={original.id}"); db.session.commit()
        flash(f"Revision {original.revision_number} restored as new draft r{restored.revision_number}.", "success")
        return redirect(url_for("revisions", project_id=project.id))

    @app.get("/projects/<int:project_id>/sample-data")
    @login_required
    def sample_data(project_id):
        project = db.get_or_404(SystemProject, project_id)
        datasets = SampleDataset.query.filter_by(project_id=project.id).order_by(SampleDataset.updated_at.desc()).all()
        builds = SandboxBuild.query.filter_by(project_id=project.id).order_by(SandboxBuild.id.desc()).limit(10).all()
        active_revision = db.session.get(DiagramRevision, project.active_revision_id) if project.active_revision_id else None
        model = revision_model(active_revision) if active_revision else None
        return render_template("sample_data.html", project=project, datasets=datasets, builds=builds, active_revision=active_revision, model=model)

    @app.post("/projects/<int:project_id>/datasets")
    @login_required
    def create_dataset(project_id):
        project = db.get_or_404(SystemProject, project_id); name = request.form.get("name", "").strip()
        if not name: flash("Dataset name is required.", "danger"); return redirect(url_for("sample_data", project_id=project.id))
        dataset = SampleDataset(project_id=project.id, name=name, description=request.form.get("description", "").strip(), provenance=request.form.get("provenance", "synthetic"), classification=request.form.get("classification", "non-sensitive"))
        db.session.add(dataset); db.session.flush(); audit("dataset.create", "SampleDataset", dataset.id, dataset.name); db.session.commit()
        flash(f"Sample dataset '{dataset.name}' created.", "success"); return redirect(url_for("sample_data", project_id=project.id))

    @app.post("/projects/<int:project_id>/datasets/<int:dataset_id>/delete")
    @login_required
    def delete_dataset(project_id, dataset_id):
        project = db.get_or_404(SystemProject, project_id); dataset = db.get_or_404(SampleDataset, dataset_id)
        if dataset.project_id != project.id: return ("Dataset does not belong to project", 400)
        name = dataset.name
        builds = SandboxBuild.query.filter_by(dataset_id=dataset.id).all()
        managed_paths = {build.managed_path for build in builds if build.managed_path}
        build_ids = [build.id for build in builds]
        if build_ids:
            SQLExecution.query.filter(SQLExecution.sandbox_build_id.in_(build_ids)).delete(synchronize_session=False)
            SandboxBuild.query.filter(SandboxBuild.id.in_(build_ids)).delete(synchronize_session=False)
        AIAction.query.filter_by(dataset_id=dataset.id).delete(synchronize_session=False)
        audit("dataset.delete", "SampleDataset", dataset.id, f"name={name} rows={len(dataset.rows)} builds={len(builds)}")
        db.session.delete(dataset); db.session.commit()
        cleanup_failed = False
        data_root = Path(app.config["DATA_DIR"]).resolve()
        for raw_path in managed_paths:
            path = Path(raw_path).resolve()
            if SandboxBuild.query.filter_by(managed_path=str(path)).first() or not path.is_relative_to(data_root):
                continue
            try:
                if path.is_file(): path.unlink()
            except OSError:
                cleanup_failed = True
        flash(f"Dataset '{name}' and its related records deleted.", "success")
        if cleanup_failed: flash("The dataset was deleted, but one or more obsolete sandbox files could not be removed.", "warning")
        return redirect(url_for("sample_data", project_id=project.id))

    @app.post("/projects/<int:project_id>/datasets/<int:dataset_id>/rows")
    @login_required
    def add_sample_row(project_id, dataset_id):
        project = db.get_or_404(SystemProject, project_id); dataset = db.get_or_404(SampleDataset, dataset_id)
        if dataset.project_id != project.id: return ("Dataset does not belong to project", 400)
        if not project.active_revision_id: flash("Approve a model revision before adding sample rows.", "danger"); return redirect(url_for("sample_data", project_id=project.id))
        revision = db.session.get(DiagramRevision, project.active_revision_id); model = revision_model(revision)
        table_editor = "values_json" not in request.form
        table_name = request.form.get("table_name", "")
        try:
            if table_editor:
                raw = {key.removeprefix("field:"): (value if value != "" else None) for key, value in request.form.items() if key.startswith("field:")}
            else:
                raw = json.loads(request.form.get("values_json", "{}"))
            if not isinstance(raw, dict): raise SampleValidationError("Row values must be a JSON object.")
            values = validate_row(model, table_name, raw)
        except (json.JSONDecodeError, SampleValidationError) as exc:
            flash(f"Sample row rejected: {exc}", "danger")
            if table_editor: return redirect(url_for("edit_sample_table", project_id=project.id, dataset_id=dataset.id, table_name=table_name))
            return redirect(url_for("sample_data", project_id=project.id))
        position = (db.session.query(db.func.max(SampleRowDefinition.position)).filter_by(dataset_id=dataset.id, table_name=table_name).scalar() or 0) + 1
        row = SampleRowDefinition(dataset_id=dataset.id, table_name=table_name, position=position, values_json=json.dumps(values, sort_keys=True))
        db.session.add(row); db.session.flush(); audit("sample_row.create", "SampleRowDefinition", row.id, row.table_name); db.session.commit()
        flash(f"Sample row added to {row.table_name}.", "success")
        if table_editor: return redirect(url_for("edit_sample_table", project_id=project.id, dataset_id=dataset.id, table_name=row.table_name))
        return redirect(url_for("sample_data", project_id=project.id))

    @app.get("/projects/<int:project_id>/datasets/<int:dataset_id>/tables/<path:table_name>/edit")
    @login_required
    def edit_sample_table(project_id, dataset_id, table_name):
        project = db.get_or_404(SystemProject, project_id); dataset = db.get_or_404(SampleDataset, dataset_id)
        if dataset.project_id != project.id: return ("Dataset does not belong to project", 400)
        if not project.active_revision_id:
            flash("Approve a model revision before editing sample rows.", "danger"); return redirect(url_for("sample_data", project_id=project.id))
        model = revision_model(db.session.get(DiagramRevision, project.active_revision_id))
        table = next((item for item in model.tables if item.name.casefold() == table_name.casefold()), None)
        if table is None: return ("Table does not belong to the active model", 400)
        rows = SampleRowDefinition.query.filter_by(dataset_id=dataset.id, table_name=table.name).order_by(SampleRowDefinition.position).all()
        return render_template("sample_table_edit.html", project=project, dataset=dataset, table=table, rows=rows)

    @app.post("/projects/<int:project_id>/datasets/<int:dataset_id>/rows/<int:row_id>/edit")
    @login_required
    def edit_sample_row(project_id, dataset_id, row_id):
        project = db.get_or_404(SystemProject, project_id); dataset = db.get_or_404(SampleDataset, dataset_id); row = db.get_or_404(SampleRowDefinition, row_id)
        if dataset.project_id != project.id or row.dataset_id != dataset.id: return ("Sample row does not belong to project dataset", 400)
        if not project.active_revision_id: flash("Approve a model revision before editing sample rows.", "danger"); return redirect(url_for("sample_data", project_id=project.id))
        model = revision_model(db.session.get(DiagramRevision, project.active_revision_id))
        table_editor = "values_json" not in request.form
        try:
            if table_editor:
                raw = {key.removeprefix("field:"): (value if value != "" else None) for key, value in request.form.items() if key.startswith("field:")}
            else:
                raw = json.loads(request.form.get("values_json", "{}"))
            if not isinstance(raw, dict): raise SampleValidationError("Row values must be a JSON object.")
            values = validate_row(model, row.table_name, raw)
            validate_dataset_relationships(model, _dataset_rows(dataset, replacement=(row.id, values)))
        except (json.JSONDecodeError, SampleValidationError) as exc:
            flash(f"Sample row update rejected: {exc}", "danger")
            if table_editor: return redirect(url_for("edit_sample_table", project_id=project.id, dataset_id=dataset.id, table_name=row.table_name))
            return redirect(url_for("sample_data", project_id=project.id))
        row.values_json = json.dumps(values, sort_keys=True)
        audit("sample_row.update", "SampleRowDefinition", row.id, row.table_name); db.session.commit()
        flash(f"Sample row #{row.id} updated.", "success")
        if table_editor: return redirect(url_for("edit_sample_table", project_id=project.id, dataset_id=dataset.id, table_name=row.table_name))
        return redirect(url_for("sample_data", project_id=project.id))

    @app.post("/projects/<int:project_id>/datasets/<int:dataset_id>/rows/<int:row_id>/delete")
    @login_required
    def delete_sample_row(project_id, dataset_id, row_id):
        project = db.get_or_404(SystemProject, project_id); dataset = db.get_or_404(SampleDataset, dataset_id); row = db.get_or_404(SampleRowDefinition, row_id)
        if dataset.project_id != project.id or row.dataset_id != dataset.id: return ("Sample row does not belong to project dataset", 400)
        if not project.active_revision_id: flash("Approve a model revision before deleting sample rows.", "danger"); return redirect(url_for("sample_data", project_id=project.id))
        model = revision_model(db.session.get(DiagramRevision, project.active_revision_id))
        try: validate_dataset_relationships(model, _dataset_rows(dataset, excluded_row_id=row.id))
        except SampleValidationError as exc:
            flash(f"Sample row deletion rejected: {exc}", "danger"); return redirect(url_for("sample_data", project_id=project.id))
        table_name = row.table_name; db.session.delete(row); audit("sample_row.delete", "SampleRowDefinition", row.id, table_name); db.session.commit()
        flash(f"Sample row #{row_id} deleted.", "success"); return redirect(url_for("sample_data", project_id=project.id))

    @app.post("/projects/<int:project_id>/datasets/<int:dataset_id>/build")
    @login_required
    def build_project_sandbox(project_id, dataset_id):
        project = db.get_or_404(SystemProject, project_id); dataset = db.get_or_404(SampleDataset, dataset_id)
        if dataset.project_id != project.id: return ("Dataset does not belong to project", 400)
        if not project.active_revision_id: flash("Approve a model revision before building a sandbox.", "danger"); return redirect(url_for("sample_data", project_id=project.id))
        revision = db.session.get(DiagramRevision, project.active_revision_id)
        try: build = build_sandbox(project, revision, dataset, app.config["DATA_DIR"])
        except ValueError as exc: flash(str(exc), "danger"); return redirect(url_for("sample_data", project_id=project.id))
        db.session.add(build); db.session.flush(); audit("sandbox.build", "SandboxBuild", build.id, f"status={build.status} hash={build.build_hash}"); db.session.commit()
        flash(f"Sandbox build {build.status}: {build.row_count} row(s).", "success" if build.status == "completed" else "danger")
        return redirect(url_for("sample_data", project_id=project.id))

    @app.route("/projects/<int:project_id>/sql", methods=["GET", "POST"])
    @login_required
    def sql_workbench(project_id):
        project = db.get_or_404(SystemProject, project_id)
        build = SandboxBuild.query.filter_by(project_id=project.id, status="completed").order_by(SandboxBuild.id.desc()).first()
        statement = request.form.get("statement", "SELECT * FROM SUPPLIER LIMIT 50") if request.method == "POST" else request.args.get("statement", "SELECT * FROM SUPPLIER LIMIT 50")
        validation = None; result = None; error = None; query_preview_svg = None
        if request.method == "POST":
            if not build: error = "Build a successful sandbox before validating SQL."
            else:
                revision = db.session.get(DiagramRevision, build.revision_id); model = revision_model(revision)
                try:
                    validation = validate_readonly_sql(statement, model)
                    if request.form.get("action") == "execute":
                        result = execute_readonly(validation, Path(build.managed_path), row_limit=500, timeout_seconds=10, allowed_root=app.config["DATA_DIR"])
                        execution = SQLExecution(project_id=project.id, sandbox_build_id=build.id, statement=validation.statement, referenced_objects_json=json.dumps({"tables": validation.tables, "columns": validation.columns}), status="completed", row_count=len(result.rows), runtime_ms=result.runtime_ms)
                        db.session.add(execution); db.session.flush(); audit("sql.execute", "SQLExecution", execution.id, f"rows={execution.row_count}"); db.session.commit()
                except (SQLValidationError, sqlite3.Error) as exc: error = str(exc)
        elif request.args.get("highlight") == "1" and project.active_revision_id:
            model = revision_model(db.session.get(DiagramRevision, project.active_revision_id))
            try: validation = validate_readonly_sql(statement, model)
            except SQLValidationError as exc: error = str(exc)
        if validation and project.active_revision_id:
            model = revision_model(db.session.get(DiagramRevision, project.active_revision_id))
            table_lookup = {table.name.casefold(): table.name for table in model.tables}
            column_lookup = {}
            for table in model.tables:
                for column in table.columns:
                    column_lookup.setdefault(column.name.casefold(), set()).add(f"{table.name}.{column.name}")
            highlights = {table_lookup[name.casefold()] for name in validation.tables if name.casefold() in table_lookup}
            for name in validation.columns:
                highlights.update(column_lookup.get(name.casefold(), set()))
            try: query_preview_svg = render_graphviz_bytes(model_to_dot(model, highlights), "svg").decode("utf-8")
            except RuntimeError as exc: error = f"Query diagram preview is unavailable: {exc}"
        history = SQLExecution.query.filter_by(project_id=project.id).order_by(SQLExecution.id.desc()).limit(10).all()
        proposals = AIAction.query.filter_by(project_id=project.id, action_type="propose_sql").order_by(AIAction.id.desc()).limit(10).all()
        return render_template("sql_workbench.html", project=project, build=build, statement=statement, validation=validation, result=result, error=error, history=history, proposals=proposals, query_preview_svg=query_preview_svg)

    @app.route("/projects/<int:project_id>/sql-viewer", methods=["GET", "POST"])
    @login_required
    def sql_viewer(project_id):
        project = db.get_or_404(SystemProject, project_id)
        build = None
        if project.active_revision_id:
            build = SandboxBuild.query.filter_by(project_id=project.id, revision_id=project.active_revision_id, status="completed").order_by(SandboxBuild.id.desc()).first()
        statement = request.form.get("statement", "") if request.method == "POST" else ""
        validation = None; result = None; error = None
        if request.method == "POST":
            if not build:
                error = "Build a successful sandbox for the active model before testing SQL."
            elif not statement.strip():
                error = "Drop or enter a SQL statement before testing it."
            else:
                model = revision_model(db.session.get(DiagramRevision, build.revision_id))
                try:
                    validation = validate_readonly_sql(statement, model)
                    result = execute_readonly(validation, Path(build.managed_path), row_limit=500, timeout_seconds=10, allowed_root=app.config["DATA_DIR"])
                    execution = SQLExecution(project_id=project.id, sandbox_build_id=build.id, statement=validation.statement, referenced_objects_json=json.dumps({"tables": validation.tables, "columns": validation.columns}), status="completed", row_count=len(result.rows), runtime_ms=result.runtime_ms)
                    db.session.add(execution); db.session.flush(); audit("sql_viewer.execute", "SQLExecution", execution.id, f"rows={execution.row_count}"); db.session.commit()
                except (SQLValidationError, sqlite3.Error) as exc:
                    error = str(exc)
        return render_template("sql_viewer.html", project=project, build=build, statement=statement, validation=validation, result=result, error=error)

    @app.post("/projects/<int:project_id>/sql/proposals")
    @login_required
    def propose_sql(project_id):
        project = db.get_or_404(SystemProject, project_id); question = request.form.get("question", "").strip()
        if not question: flash("Enter a data question.", "danger"); return redirect(url_for("sql_workbench", project_id=project.id))
        if not project.active_revision_id: flash("Approve a model revision before generating SQL.", "danger"); return redirect(url_for("sql_workbench", project_id=project.id))
        revision = db.session.get(DiagramRevision, project.active_revision_id); model = revision_model(revision)
        try:
            configured_url = get_text("ollama_url", app.config["OLLAMA_URL"]); model_name = get_text("ollama_model", app.config["OLLAMA_MODEL"])
            proposal = generate_sql_proposal(question=question, model=model, ollama_url=configured_url, ollama_model=model_name)
            action = AIAction(project_id=project.id, action_type="propose_sql", status="proposed", payload_json=json.dumps({"question": question, "statement": proposal.statement, "explanation": proposal.explanation, "assumptions": proposal.assumptions, "model_revision_id": revision.id}, sort_keys=True), requested_by=current_user.username)
            db.session.add(action); db.session.flush(); audit("ai_sql.propose", "AIAction", action.id, f"revision={revision.id}"); db.session.commit(); flash("Generated validated SQL for review.", "success")
        except (SQLProposalError, OllamaError) as exc: flash(str(exc), "danger")
        return redirect(url_for("sql_workbench", project_id=project.id))

    @app.post("/projects/<int:project_id>/sql/proposals/<int:action_id>/<decision>")
    @login_required
    def decide_sql_proposal(project_id, action_id, decision):
        project = db.get_or_404(SystemProject, project_id); action = db.get_or_404(AIAction, action_id)
        if action.project_id != project.id or action.action_type != "propose_sql": return ("SQL proposal does not belong to project", 400)
        if action.status != "proposed": flash("This SQL proposal is no longer awaiting review.", "warning"); return redirect(url_for("sql_workbench", project_id=project.id))
        if decision == "reject": action.status = "rejected"; audit("ai_sql.reject", "AIAction", action.id); db.session.commit(); flash("SQL proposal rejected.", "success"); return redirect(url_for("sql_workbench", project_id=project.id))
        if decision != "confirm": return ("Unknown decision", 400)
        payload = json.loads(action.payload_json)
        if payload.get("model_revision_id") != project.active_revision_id: flash("The active model changed; generate a new SQL proposal.", "danger"); return redirect(url_for("sql_workbench", project_id=project.id))
        model = revision_model(db.session.get(DiagramRevision, project.active_revision_id))
        try: validation = validate_readonly_sql(payload["statement"], model)
        except SQLValidationError as exc: flash(f"SQL proposal is no longer valid: {exc}", "danger"); return redirect(url_for("sql_workbench", project_id=project.id))
        action.status = "applied"; action.confirmed_at = utcnow(); action.result_json = json.dumps({"loaded_into_workbench": True}); audit("ai_sql.confirm", "AIAction", action.id); db.session.commit()
        flash("Validated SQL loaded into the workbench. Review it before choosing execute.", "success")
        return redirect(url_for("sql_workbench", project_id=project.id, statement=validation.statement, highlight=1))

    @app.route("/projects/<int:project_id>/knowledge", methods=["GET", "POST"])
    @login_required
    def knowledge(project_id):
        project = db.get_or_404(SystemProject, project_id)
        if request.method == "POST":
            upload = request.files.get("document")
            if not upload:
                flash("Choose a document to upload.", "danger")
            else:
                try:
                    document = ingest_document(project_id=project.id, upload=upload, title=request.form.get("title", ""), provenance=request.form.get("provenance", "uploaded"), classification=request.form.get("classification", "internal"), data_dir=app.config["DATA_DIR"])
                    db.session.add(DocumentVersion(project_id=project.id, document_id=document.id, family_id=str(uuid4()), version_number=1))
                    audit("knowledge_document.ingest", "KnowledgeDocument", document.id, f"chunks={len(document.chunks)} filename={document.original_filename}"); db.session.commit()
                    flash(f"Indexed '{document.title}' as {len(document.chunks)} searchable chunk(s).", "success")
                except KnowledgeIngestionError as exc:
                    db.session.rollback(); flash(f"Document rejected: {exc}", "danger")
            return redirect(url_for("knowledge", project_id=project.id))
        query = request.args.get("q", "").strip(); source = request.args.get("source", "all")
        document_results = search_documents(project_id=project.id, query=query) if query and source in {"all", "documents"} else []
        schema_results = search_schema(project=project, query=query) if query and source in {"all", "schema"} else []
        relationship_results = search_relationships(project=project, query=query) if query and source in {"all", "schema"} else []
        sample_results = search_sample_values(project_id=project.id, query=query) if query and source in {"all", "samples"} else []
        cross_project_results = search_cross_project_evidence(project=project, query=query) if query and source in {"all", "cross-project"} else []
        documents = KnowledgeDocument.query.filter_by(project_id=project.id).order_by(KnowledgeDocument.updated_at.desc()).all()
        link_targets = []; active_model = None
        if project.active_revision_id:
            active_model = revision_model(db.session.get(DiagramRevision, project.active_revision_id))
            for table in TableDefinition.query.filter_by(project_id=project.id, revision_id=project.active_revision_id).order_by(TableDefinition.name).all():
                link_targets.append(("table", table.name, f"Table · {table.name}"))
                link_targets.extend(("column", f"{table.name}.{column.name}", f"Column · {table.name}.{column.name}") for column in table.columns)
        coverage = knowledge_coverage(project=project, model=active_model)
        evidence_records = EvidenceRecord.query.filter_by(project_id=project.id).order_by(EvidenceRecord.id.desc()).limit(20).all()
        local_activity = []
        if query:
            local_activity.append({"action": "Parse query", "detail": f"{len(query.split())} term(s); source filter: {source}", "count": None})
            if source in {"all", "schema"}:
                local_activity.extend([
                    {"action": "Search catalogue", "detail": "Active approved tables and fields", "count": len(schema_results)},
                    {"action": "Traverse relationships", "detail": "Direct matches and bounded paths", "count": len(relationship_results)},
                ])
            if source in {"all", "documents"}: local_activity.append({"action": "Search document index", "detail": "Project-scoped SQLite FTS5 chunks", "count": len(document_results)})
            if source in {"all", "samples"}: local_activity.append({"action": "Scan sample values", "detail": "Bounded representative dataset rows", "count": len(sample_results)})
            if source in {"all", "cross-project"}: local_activity.append({"action": "Check attached projects", "detail": "Explicit links, aliases and attachments only", "count": len(cross_project_results)})
            total = sum(len(items) for items in (schema_results, relationship_results, document_results, sample_results, cross_project_results))
            local_activity.append({"action": "Assemble results", "detail": "Escaped evidence ready for review", "count": total})
        return render_template("knowledge.html", project=project, documents=documents, query=query, source=source, document_results=document_results, schema_results=schema_results, relationship_results=relationship_results, sample_results=sample_results, cross_project_results=cross_project_results, link_targets=link_targets, coverage=coverage, evidence_records=evidence_records, local_activity=local_activity)

    @app.get("/projects/<int:project_id>/knowledge/documents/<int:document_id>")
    @login_required
    def knowledge_document(project_id, document_id):
        project = db.get_or_404(SystemProject, project_id); document = db.get_or_404(KnowledgeDocument, document_id)
        if document.project_id != project.id: return ("Document does not belong to project", 400)
        versions = []
        if document.version:
            lineage = DocumentVersion.query.filter_by(family_id=document.version.family_id).order_by(DocumentVersion.version_number.desc()).all()
            versions = [db.session.get(KnowledgeDocument, item.document_id) for item in lineage]
        chunks = sorted(document.chunks, key=lambda item: item.position)
        return render_template("knowledge_document.html", project=project, document=document, chunks=chunks, versions=versions)

    @app.get("/projects/<int:project_id>/knowledge/chunks/<int:chunk_id>")
    @login_required
    def knowledge_chunk(project_id, chunk_id):
        project = db.get_or_404(SystemProject, project_id); chunk = db.get_or_404(DocumentChunk, chunk_id)
        if chunk.document.project_id != project.id: return ("Citation does not belong to project", 400)
        targets = []
        if project.active_revision_id:
            model = revision_model(db.session.get(DiagramRevision, project.active_revision_id))
            for table in model.tables:
                targets.append(("table", table.name, f"Table · {table.name}"))
                targets.extend(("column", f"{table.name}.{column.name}", f"Column · {table.name}.{column.name}") for column in table.columns)
        return render_template("knowledge_chunk.html", project=project, chunk=chunk, link_targets=targets)

    @app.post("/projects/<int:project_id>/knowledge/documents/<int:document_id>/delete")
    @login_required
    def delete_knowledge_document(project_id, document_id):
        project = db.get_or_404(SystemProject, project_id); document = db.get_or_404(KnowledgeDocument, document_id)
        if document.project_id != project.id: return ("Document does not belong to project", 400)
        title = document.title; path = Path(document.managed_path).resolve(); chunk_ids = [chunk.id for chunk in document.chunks]
        if document.version:
            DocumentVersion.query.filter_by(predecessor_document_id=document.id).update({DocumentVersion.predecessor_document_id: document.version.predecessor_document_id}, synchronize_session=False)
        remove_from_fts(chunk_ids); ExternalResearchPromotion.query.filter_by(document_id=document.id).delete(synchronize_session=False); CrossProjectAttachment.query.filter_by(document_id=document.id).delete(synchronize_session=False); audit("knowledge_document.delete", "KnowledgeDocument", document.id, f"title={title} chunks={len(chunk_ids)}"); db.session.delete(document); db.session.commit()
        cleanup_failed = False; data_root = Path(app.config["DATA_DIR"]).resolve()
        try:
            if path.is_relative_to(data_root) and path.is_file(): path.unlink()
        except OSError:
            cleanup_failed = True
        flash(f"Knowledge document '{title}' deleted.", "success")
        if cleanup_failed: flash("The document record was deleted, but its obsolete managed file could not be removed.", "warning")
        return redirect(url_for("knowledge", project_id=project.id))

    @app.post("/projects/<int:project_id>/knowledge/documents/<int:document_id>/versions")
    @login_required
    def upload_document_version(project_id, document_id):
        project = db.get_or_404(SystemProject, project_id); predecessor = db.get_or_404(KnowledgeDocument, document_id)
        if predecessor.project_id != project.id: return ("Document does not belong to project", 400)
        upload = request.files.get("document")
        if not upload: flash("Choose a document version to upload.", "danger"); return redirect(url_for("knowledge", project_id=project.id))
        lineage = predecessor.version
        if not lineage:
            lineage = DocumentVersion(project_id=project.id, document_id=predecessor.id, family_id=str(uuid4()), version_number=1); db.session.add(lineage); db.session.flush()
        latest_number = db.session.query(db.func.max(DocumentVersion.version_number)).filter_by(family_id=lineage.family_id).scalar() or lineage.version_number
        try:
            document = ingest_document(project_id=project.id, upload=upload, title=predecessor.title, provenance=request.form.get("provenance", predecessor.provenance), classification=request.form.get("classification", predecessor.classification), data_dir=app.config["DATA_DIR"])
            version = DocumentVersion(project_id=project.id, document_id=document.id, family_id=lineage.family_id, version_number=latest_number + 1, predecessor_document_id=predecessor.id)
            db.session.add(version); db.session.flush(); audit("knowledge_document.version", "KnowledgeDocument", document.id, f"family={lineage.family_id} version={version.version_number} predecessor={predecessor.id}"); db.session.commit()
            flash(f"Uploaded version {version.version_number} of '{document.title}'.", "success")
        except KnowledgeIngestionError as exc:
            db.session.rollback(); flash(f"Document version rejected: {exc}", "danger")
        return redirect(url_for("knowledge", project_id=project.id))

    @app.post("/projects/<int:project_id>/knowledge/documents/<int:document_id>/links")
    @login_required
    def create_knowledge_link(project_id, document_id):
        project = db.get_or_404(SystemProject, project_id); document = db.get_or_404(KnowledgeDocument, document_id)
        if document.project_id != project.id: return ("Document does not belong to project", 400)
        if not project.active_revision_id: flash("Approve a model revision before linking documents.", "danger"); return redirect(url_for("knowledge", project_id=project.id))
        target_type, separator, target_key = request.form.get("target", "").partition("|")
        model = revision_model(db.session.get(DiagramRevision, project.active_revision_id))
        valid_targets = {("table", table.name) for table in model.tables}
        valid_targets.update(("column", f"{table.name}.{column.name}") for table in model.tables for column in table.columns)
        if not separator or (target_type, target_key) not in valid_targets:
            flash("The selected model target is not valid for the active revision.", "danger"); return redirect(url_for("knowledge", project_id=project.id))
        existing = KnowledgeLink.query.filter_by(document_id=document.id, revision_id=project.active_revision_id, target_type=target_type, target_key=target_key).first()
        if existing:
            flash("That document link already exists.", "warning"); return redirect(url_for("knowledge", project_id=project.id))
        link = KnowledgeLink(project_id=project.id, document_id=document.id, revision_id=project.active_revision_id, target_type=target_type, target_key=target_key, created_by=current_user.username)
        db.session.add(link); db.session.flush(); audit("knowledge_link.create", "KnowledgeLink", link.id, f"document={document.id} target={target_type}:{target_key}"); db.session.commit()
        flash(f"Linked '{document.title}' to {target_key}.", "success"); return redirect(url_for("knowledge", project_id=project.id))

    @app.post("/projects/<int:project_id>/knowledge/links/<int:link_id>/delete")
    @login_required
    def delete_knowledge_link(project_id, link_id):
        project = db.get_or_404(SystemProject, project_id); link = db.get_or_404(KnowledgeLink, link_id)
        if link.project_id != project.id: return ("Knowledge link does not belong to project", 400)
        target = link.target_key; audit("knowledge_link.delete", "KnowledgeLink", link.id, target); db.session.delete(link); db.session.commit()
        flash(f"Removed document link to {target}.", "success"); return redirect(url_for("knowledge", project_id=project.id))

    @app.post("/projects/<int:project_id>/knowledge/chunks/<int:chunk_id>/links")
    @login_required
    def create_chunk_knowledge_link(project_id, chunk_id):
        project = db.get_or_404(SystemProject, project_id); chunk = db.get_or_404(DocumentChunk, chunk_id)
        if chunk.document.project_id != project.id: return ("Citation does not belong to project", 400)
        if not project.active_revision_id: flash("Approve a model revision before linking evidence.", "danger"); return redirect(url_for("knowledge_chunk", project_id=project.id, chunk_id=chunk.id))
        target_type, separator, target_key = request.form.get("target", "").partition("|")
        model = revision_model(db.session.get(DiagramRevision, project.active_revision_id))
        valid_targets = {("table", table.name) for table in model.tables}; valid_targets.update(("column", f"{table.name}.{column.name}") for table in model.tables for column in table.columns)
        if not separator or (target_type, target_key) not in valid_targets:
            flash("The selected model target is not valid for the active revision.", "danger"); return redirect(url_for("knowledge_chunk", project_id=project.id, chunk_id=chunk.id))
        if ChunkKnowledgeLink.query.filter_by(chunk_id=chunk.id, revision_id=project.active_revision_id, target_type=target_type, target_key=target_key).first():
            flash("That passage link already exists.", "warning"); return redirect(url_for("knowledge_chunk", project_id=project.id, chunk_id=chunk.id))
        link = ChunkKnowledgeLink(project_id=project.id, chunk_id=chunk.id, revision_id=project.active_revision_id, target_type=target_type, target_key=target_key, created_by=current_user.username)
        db.session.add(link); db.session.flush(); audit("chunk_knowledge_link.create", "ChunkKnowledgeLink", link.id, f"chunk={chunk.id} target={target_type}:{target_key}"); db.session.commit()
        flash(f"Linked cited passage to {target_key}.", "success"); return redirect(url_for("knowledge_chunk", project_id=project.id, chunk_id=chunk.id))

    @app.post("/projects/<int:project_id>/knowledge/chunk-links/<int:link_id>/delete")
    @login_required
    def delete_chunk_knowledge_link(project_id, link_id):
        project = db.get_or_404(SystemProject, project_id); link = db.get_or_404(ChunkKnowledgeLink, link_id)
        if link.project_id != project.id: return ("Passage link does not belong to project", 400)
        chunk_id = link.chunk_id; target = link.target_key; audit("chunk_knowledge_link.delete", "ChunkKnowledgeLink", link.id, target); db.session.delete(link); db.session.commit()
        flash(f"Removed passage link to {target}.", "success"); return redirect(url_for("knowledge_chunk", project_id=project.id, chunk_id=chunk_id))

    @app.post("/projects/<int:project_id>/knowledge/evidence")
    @login_required
    def save_evidence_record(project_id):
        project = db.get_or_404(SystemProject, project_id); query = request.form.get("q", "").strip(); source = request.form.get("source", "all")
        if not query: flash("Enter a search query before saving evidence.", "danger"); return redirect(url_for("knowledge", project_id=project.id))
        if source not in {"all", "schema", "documents", "samples", "cross-project"}: source = "all"
        evidence = {
            "schema": search_schema(project=project, query=query) if source in {"all", "schema"} else [],
            "relationships": search_relationships(project=project, query=query) if source in {"all", "schema"} else [],
            "documents": search_documents(project_id=project.id, query=query) if source in {"all", "documents"} else [],
            "samples": search_sample_values(project_id=project.id, query=query) if source in {"all", "samples"} else [],
            "cross_project": search_cross_project_evidence(project=project, query=query) if source in {"all", "cross-project"} else [],
        }
        record = EvidenceRecord(project_id=project.id, search_query=query[:500], source_filter=source, model_revision_id=project.active_revision_id, evidence_json=json.dumps(evidence, sort_keys=True), created_by=current_user.username)
        db.session.add(record); db.session.flush(); audit("evidence_record.create", "EvidenceRecord", record.id, f"query={query[:120]} sources={source}"); db.session.commit()
        flash(f"Saved evidence snapshot #{record.id}.", "success"); return redirect(url_for("evidence_record", project_id=project.id, record_id=record.id))

    @app.get("/projects/<int:project_id>/knowledge/evidence/<int:record_id>")
    @login_required
    def evidence_record(project_id, record_id):
        project = db.get_or_404(SystemProject, project_id); record = db.get_or_404(EvidenceRecord, record_id)
        if record.project_id != project.id: return ("Evidence record does not belong to project", 400)
        return render_template("evidence_record.html", project=project, record=record, evidence=json.loads(record.evidence_json))

    @app.post("/projects/<int:project_id>/knowledge/evidence/<int:record_id>/delete")
    @login_required
    def delete_evidence_record(project_id, record_id):
        project = db.get_or_404(SystemProject, project_id); record = db.get_or_404(EvidenceRecord, record_id)
        if record.project_id != project.id: return ("Evidence record does not belong to project", 400)
        audit("evidence_record.delete", "EvidenceRecord", record.id, record.search_query[:120]); db.session.delete(record); db.session.commit(); flash(f"Evidence snapshot #{record_id} deleted.", "success")
        return redirect(url_for("knowledge", project_id=project.id))

    @app.route("/projects/<int:project_id>/assistant", methods=["GET", "POST"])
    @login_required
    def project_assistant(project_id):
        project = db.get_or_404(SystemProject, project_id)
        if request.method == "POST":
            question = request.form.get("question", "").strip()
            if not question: flash("Enter a question.", "danger"); return redirect(url_for("project_assistant", project_id=project.id))
            evidence = []
            raw_context_ids = request.form.getlist("context_exchange_ids")
            legacy_context_id = request.form.get("context_exchange_id")
            if legacy_context_id and not raw_context_ids: raw_context_ids = [legacy_context_id]
            try:
                context_ids = list(dict.fromkeys(int(value) for value in raw_context_ids if value))
            except ValueError:
                flash("Invalid follow-up context selection.", "danger"); return redirect(url_for("project_assistant", project_id=project.id))
            if len(context_ids) > 3:
                flash("Select no more than three prior exchanges.", "danger"); return redirect(url_for("project_assistant", project_id=project.id))
            context_exchanges = [db.session.get(AssistantExchange, context_id) for context_id in context_ids]
            if any(exchange is None or exchange.project_id != project.id for exchange in context_exchanges):
                flash("A selected context does not belong to this project.", "danger"); return redirect(url_for("project_assistant", project_id=project.id))
            for context_exchange in context_exchanges:
                prior_answer = json.loads(context_exchange.answer_json)
                evidence.append({"evidence_id": f"context:{context_exchange.id}", "source": "conversation", "title": f"Prior exchange #{context_exchange.id}", "locator": context_exchange.question[:240], "excerpt": json.dumps({"answer": prior_answer.get("answer", "")[:2000], "citations": prior_answer.get("citations", [])[:10]}, sort_keys=True)})
            for prefix, items in (("schema", search_schema(project=project, query=question, limit=8)), ("relationship", search_relationships(project=project, query=question, limit=8)), ("document", search_documents(project_id=project.id, query=question, limit=8)), ("sample", search_sample_values(project_id=project.id, query=question, limit=8))):
                for index, item in enumerate(items):
                    evidence_id = f"chunk:{item['chunk_id']}" if prefix == "document" else f"{prefix}:{index}"
                    evidence.append({"evidence_id": evidence_id, "source": prefix, "title": item["title"], "locator": item["locator"], "excerpt": item["excerpt"]})
            try:
                configured_url = get_text("ollama_url", app.config["OLLAMA_URL"]); model_name = get_text("ollama_model", app.config["OLLAMA_MODEL"])
                model = revision_model(db.session.get(DiagramRevision, project.active_revision_id)) if project.active_revision_id else None
                if request.form.get("use_sql") == "on":
                    if not model: raise GroundedAnswerError("Approve a model and build its sandbox before asking data questions.")
                    proposal = generate_sql_proposal(question=question, model=model, ollama_url=configured_url, ollama_model=model_name)
                    result = execute_read_tool(tool_name="sql.query", argument=proposal.statement, project=project, model=model, allowed_root=app.config["DATA_DIR"])
                    persist_assistant_sql_execution(project, result)
                    call = AssistantToolCall(project_id=project.id, tool_name="sql.query", input_json=json.dumps({"argument": proposal.statement, "reason": proposal.explanation, "question": question[:1000]}, sort_keys=True), result_json=json.dumps(result, sort_keys=True), status="completed", requested_by=f"ollama:{current_user.username}")
                    db.session.add(call); db.session.flush(); audit("assistant_tool.auto", "AssistantToolCall", call.id, "tool=sql.query status=completed")
                    evidence.append({"evidence_id": f"tool:{call.id}", "source": "tool", "title": "Validated sandbox SQL", "locator": proposal.explanation or "AI-built read-only query", "excerpt": json.dumps(result, sort_keys=True)[:5000]})
                if request.form.get("use_tools") == "on":
                    planner_tools = {name: description for name, description in READ_TOOLS.items() if name not in {"sql.query", "samples.aggregate"}}
                    plan = plan_read_tools(question=question, evidence=evidence, allowed_tools=planner_tools, ollama_url=configured_url, ollama_model=model_name)
                    for planned in plan.tool_requests:
                        try:
                            result = execute_read_tool(tool_name=planned.tool_name, argument=planned.argument, project=project, model=model, allowed_root=app.config["DATA_DIR"]); status = "completed"
                        except AssistantToolError as exc:
                            result = {"error": str(exc)}; status = "rejected"
                        call = AssistantToolCall(project_id=project.id, tool_name=planned.tool_name, input_json=json.dumps({"argument": planned.argument, "reason": planned.reason}), result_json=json.dumps(result, sort_keys=True), status=status, requested_by=f"ollama:{current_user.username}")
                        db.session.add(call); db.session.flush(); audit("assistant_tool.auto", "AssistantToolCall", call.id, f"tool={planned.tool_name} status={status}")
                        if status == "completed": evidence.append({"evidence_id": f"tool:{call.id}", "source": "tool", "title": planned.tool_name, "locator": planned.reason or "Model-selected read tool", "excerpt": json.dumps(result, sort_keys=True)[:5000]})
                answer = generate_grounded_answer(question=question, evidence=evidence, ollama_url=configured_url, ollama_model=model_name)
                exchange = AssistantExchange(project_id=project.id, question=question, answer_json=answer.model_dump_json(), evidence_json=json.dumps(evidence, sort_keys=True), model_name=model_name, requested_by=current_user.username)
                db.session.add(exchange); db.session.flush()
                for context_exchange in context_exchanges:
                    db.session.add(AssistantContextLink(project_id=project.id, exchange_id=exchange.id, parent_exchange_id=context_exchange.id))
                audit("assistant.answer", "AssistantExchange", exchange.id, f"evidence={len(evidence)} model={model_name} contexts={context_ids or 'none'}"); db.session.commit()
                if request.form.get("propose_actions") == "on":
                    documents = KnowledgeDocument.query.filter_by(project_id=project.id).order_by(KnowledgeDocument.id).limit(50).all()
                    plan = plan_mutation_actions(question=question, evidence=evidence, model=model, documents=documents, ollama_url=configured_url, ollama_model=model_name)
                    for proposed in plan.action_requests:
                        payload = proposed.model_dump(); payload["model_revision_id"] = project.active_revision_id; payload["exchange_id"] = exchange.id
                        action = AIAction(project_id=project.id, action_type=proposed.action_name, status="proposed", payload_json=json.dumps(payload, sort_keys=True), requested_by=f"ollama:{current_user.username}")
                        db.session.add(action); db.session.flush(); audit("assistant_action.propose", "AIAction", action.id, f"action={proposed.action_name} exchange={exchange.id}")
                    db.session.commit()
                return redirect(url_for("project_assistant", project_id=project.id, exchange=exchange.id))
            except (AssistantActionError, AssistantToolError, GroundedAnswerError, SQLProposalError, OllamaError) as exc:
                db.session.rollback()
                flash(str(exc), "danger"); return redirect(url_for("project_assistant", project_id=project.id))
        history = AssistantExchange.query.filter_by(project_id=project.id).order_by(AssistantExchange.id.desc()).limit(20).all(); tool_calls = AssistantToolCall.query.filter_by(project_id=project.id).order_by(AssistantToolCall.id.desc()).limit(20).all()
        actions = AIAction.query.filter(AIAction.project_id == project.id, AIAction.action_type.in_(["knowledge.link_document", "knowledge.link_chunk"])).order_by(AIAction.id.desc()).limit(20).all()
        context_links = {}
        for link in AssistantContextLink.query.filter_by(project_id=project.id).order_by(AssistantContextLink.id).all():
            context_links.setdefault(link.exchange_id, []).append(link.parent_exchange_id)
        selected_id = request.args.get("exchange", type=int); selected = db.session.get(AssistantExchange, selected_id) if selected_id else (history[0] if history else None)
        if selected and selected.project_id != project.id: selected = None
        return render_template("assistant.html", project=project, history=history, selected=selected, read_tools=READ_TOOLS, tool_calls=tool_calls, actions=actions, context_links=context_links)

    @app.post("/projects/<int:project_id>/assistant/actions/<int:action_id>/<decision>")
    @login_required
    def decide_assistant_action(project_id, action_id, decision):
        project = db.get_or_404(SystemProject, project_id); action = db.get_or_404(AIAction, action_id)
        if action.project_id != project.id or action.action_type not in {"knowledge.link_document", "knowledge.link_chunk"}: return ("Assistant action does not belong to project", 400)
        if action.status != "proposed": flash("This action is no longer awaiting review.", "warning"); return redirect(url_for("project_assistant", project_id=project.id))
        if decision == "reject":
            action.status = "rejected"; audit("assistant_action.reject", "AIAction", action.id); db.session.commit(); flash("Assistant action rejected.", "success"); return redirect(url_for("project_assistant", project_id=project.id))
        if decision != "confirm": return ("Unknown decision", 400)
        payload = json.loads(action.payload_json)
        if payload.get("model_revision_id") != project.active_revision_id:
            flash("The active model changed; this action cannot be applied.", "danger"); return redirect(url_for("project_assistant", project_id=project.id))
        model = revision_model(db.session.get(DiagramRevision, project.active_revision_id)) if project.active_revision_id else None
        try:
            proposal = KnowledgeLinkProposal.model_validate(payload)
            if action.action_type == "knowledge.link_document":
                link = apply_knowledge_link(project=project, model=model, revision_id=project.active_revision_id, proposal=proposal, created_by=current_user.username)
                result_key = "knowledge_link_id"; message = "Assistant-proposed document link applied."
            else:
                link = apply_chunk_link(project=project, model=model, revision_id=project.active_revision_id, proposal=proposal, created_by=current_user.username)
                result_key = "chunk_knowledge_link_id"; message = "Assistant-proposed document chunk link applied."
            db.session.flush(); action.status = "applied"; action.confirmed_at = utcnow(); action.result_json = json.dumps({result_key: link.id})
            audit("assistant_action.confirm", "AIAction", action.id, f"type={action.action_type} link={link.id}"); db.session.commit(); flash(message, "success")
        except (AssistantActionError, ValueError) as exc:
            db.session.rollback(); flash(f"Assistant action could not be applied: {exc}", "danger")
        return redirect(url_for("project_assistant", project_id=project.id))

    @app.post("/projects/<int:project_id>/assistant/tools")
    @login_required
    def run_assistant_tool(project_id):
        project = db.get_or_404(SystemProject, project_id); tool_name = request.form.get("tool_name", ""); argument = request.form.get("argument", "")
        model = revision_model(db.session.get(DiagramRevision, project.active_revision_id)) if project.active_revision_id else None
        try:
            result = execute_read_tool(tool_name=tool_name, argument=argument, project=project, model=model, allowed_root=app.config["DATA_DIR"])
            if tool_name in {"sql.query", "samples.aggregate"}: persist_assistant_sql_execution(project, result)
            status = "completed"; category = "success"
        except AssistantToolError as exc:
            result = {"error": str(exc)}; status = "rejected"; category = "danger"
        call = AssistantToolCall(project_id=project.id, tool_name=tool_name[:100], input_json=json.dumps({"argument": argument[:12000]}), result_json=json.dumps(result, sort_keys=True), status=status, requested_by=current_user.username)
        db.session.add(call); db.session.flush(); audit("assistant_tool.run", "AssistantToolCall", call.id, f"tool={tool_name} status={status}"); db.session.commit(); flash(f"Assistant tool {status}.", category)
        return redirect(url_for("project_assistant", project_id=project.id))

    @app.route("/projects/<int:project_id>/ai-records", methods=["GET", "POST"])
    @login_required
    def ai_records(project_id):
        project = db.get_or_404(SystemProject, project_id)
        revision = db.session.get(DiagramRevision, project.active_revision_id) if project.active_revision_id else None
        model = revision_model(revision) if revision else None
        datasets = SampleDataset.query.filter_by(project_id=project.id).order_by(SampleDataset.updated_at.desc()).all()
        selected_table = request.values.get("table") or (model.tables[0].name if model and model.tables else None)
        dataset_values = request.values.getlist("dataset_id")
        selected_dataset_id = (int(dataset_values[-1]) if dataset_values and dataset_values[-1].isdigit() else None) or (datasets[0].id if datasets else None)
        selected_dataset = db.session.get(SampleDataset, selected_dataset_id) if selected_dataset_id else None
        if selected_dataset and selected_dataset.project_id != project.id: return ("Dataset does not belong to project", 400)
        if request.method == "POST":
            if not model: flash("Approve a model revision before generating records.", "danger")
            elif not selected_dataset: flash("Create a sample dataset before generating records.", "danger")
            else:
                related_rows = {}
                for row in selected_dataset.rows:
                    related_rows.setdefault(row.table_name, []).append(json.loads(row.values_json))
                existing = next((rows for name, rows in related_rows.items() if name.casefold() == str(selected_table).casefold()), [])
                try:
                    configured_url = get_text("ollama_url", app.config["OLLAMA_URL"]); configured_model = get_text("ollama_model", app.config["OLLAMA_MODEL"])
                    proposal = generate_record_proposal(model=model, table_name=selected_table, count=request.form.get("count", 3, type=int), instructions=request.form.get("instructions", "").strip(), ollama_url=configured_url, ollama_model=request.form.get("model", "").strip() or configured_model, existing_rows=existing, related_rows_by_table=related_rows)
                    action = AIAction(project_id=project.id, dataset_id=selected_dataset.id, action_type="propose_sample_rows", status="proposed", payload_json=json.dumps({"table_name": selected_table, "rows": proposal.rows, "notes": proposal.notes, "model_revision_id": revision.id}, sort_keys=True), requested_by=current_user.username)
                    db.session.add(action); db.session.flush(); audit("ai_action.propose", "AIAction", action.id, f"table={selected_table} rows={len(proposal.rows)}"); db.session.commit()
                    flash(f"Generated {len(proposal.rows)} validated row proposal(s) for review.", "success")
                except (AIRecordGenerationError, OllamaError) as exc: flash(str(exc), "danger")
                return redirect(url_for("ai_records", project_id=project.id, table=selected_table, dataset_id=selected_dataset.id))
        proposals = AIAction.query.filter_by(project_id=project.id, action_type="propose_sample_rows").order_by(AIAction.id.desc()).limit(20).all()
        return render_template("ai_records.html", project=project, revision=revision, model=model, datasets=datasets, selected_table=selected_table, selected_dataset=selected_dataset, proposals=proposals, ollama_model=get_text("ollama_model", app.config["OLLAMA_MODEL"]), ollama_url=get_text("ollama_url", app.config["OLLAMA_URL"]))

    @app.post("/projects/<int:project_id>/ai-records/<int:action_id>/confirm")
    @login_required
    def confirm_ai_records(project_id, action_id):
        project = db.get_or_404(SystemProject, project_id); action = db.get_or_404(AIAction, action_id)
        if action.project_id != project.id or action.action_type != "propose_sample_rows": return ("Action does not belong to project", 400)
        if action.status != "proposed": flash("This proposal is no longer awaiting confirmation.", "warning"); return redirect(url_for("ai_records", project_id=project.id))
        dataset = db.session.get(SampleDataset, action.dataset_id); revision = db.session.get(DiagramRevision, project.active_revision_id) if project.active_revision_id else None
        payload = json.loads(action.payload_json)
        if not dataset or dataset.project_id != project.id or not revision or payload.get("model_revision_id") != revision.id:
            flash("The dataset or active model changed; generate a new proposal.", "danger"); return redirect(url_for("ai_records", project_id=project.id))
        model = revision_model(revision); table_name = payload["table_name"]
        related_rows = {}
        for stored_row in dataset.rows:
            related_rows.setdefault(stored_row.table_name, []).append(json.loads(stored_row.values_json))
        next_position = (db.session.query(db.func.max(SampleRowDefinition.position)).filter_by(dataset_id=dataset.id, table_name=table_name).scalar() or 0) + 1
        created_ids = []
        try:
            for offset, raw in enumerate(payload["rows"]):
                values = validate_row(model, table_name, raw)
                validate_relationship_references(model=model, table_name=table_name, rows=[values], related_rows_by_table=related_rows)
                row = SampleRowDefinition(dataset_id=dataset.id, table_name=table_name, position=next_position + offset, values_json=json.dumps(values, sort_keys=True))
                db.session.add(row); db.session.flush(); created_ids.append(row.id)
            action.status = "applied"; action.confirmed_at = utcnow(); action.result_json = json.dumps({"created_row_ids": created_ids})
            audit("ai_action.apply", "AIAction", action.id, f"rows={len(created_ids)}"); db.session.commit()
            flash(f"Applied {len(created_ids)} generated row(s) to {dataset.name}.", "success")
        except (SampleValidationError, AIRecordGenerationError) as exc:
            db.session.rollback(); flash(f"Proposal could not be applied: {exc}", "danger")
        return redirect(url_for("ai_records", project_id=project.id, table=table_name, dataset_id=dataset.id))

    @app.post("/projects/<int:project_id>/ai-records/<int:action_id>/reject")
    @login_required
    def reject_ai_records(project_id, action_id):
        project = db.get_or_404(SystemProject, project_id); action = db.get_or_404(AIAction, action_id)
        if action.project_id != project.id or action.action_type != "propose_sample_rows": return ("Action does not belong to project", 400)
        if action.status == "proposed": action.status = "rejected"; audit("ai_action.reject", "AIAction", action.id); db.session.commit(); flash("Generated row proposal rejected.", "success")
        return redirect(url_for("ai_records", project_id=project.id))

    @app.route("/projects/<int:project_id>/research", methods=["GET", "POST"])
    @login_required
    def external_research(project_id):
        project = db.get_or_404(SystemProject, project_id)
        if request.method == "POST":
            original_query = request.form.get("query", "").strip()
            try:
                outbound_query = sanitise_external_query(original_query)
                job = ExternalResearchJob(project_id=project.id, original_query=original_query[:4000], outbound_query=outbound_query, provider="Wikipedia", status="proposed", requested_by=current_user.username)
                db.session.add(job); db.session.flush()
                db.session.add(ExternalResearchJobEvent(project_id=project.id, job_id=job.id, event_type="prepared", actor=current_user.username, detail=f"Sanitised locally to {len(outbound_query.split())} outbound term(s); awaiting confirmation"))
                audit("external_research.propose", "ExternalResearchJob", job.id, f"outbound={outbound_query}"); db.session.commit()
                flash("Sanitised outbound query prepared. Review it before sending.", "success")
            except ExternalResearchError as exc:
                flash(str(exc), "danger")
            return redirect(url_for("external_research", project_id=project.id))
        jobs = ExternalResearchJob.query.filter_by(project_id=project.id).order_by(ExternalResearchJob.id.desc()).limit(20).all()
        promotions = {(promotion.job_id, promotion.citation_index): promotion for promotion in ExternalResearchPromotion.query.filter_by(project_id=project.id).all()}
        retry_origins = {event.related_job_id: event.job_id for event in ExternalResearchJobEvent.query.filter_by(project_id=project.id, event_type="retried").all() if event.related_job_id}
        activity_events = ExternalResearchJobEvent.query.filter_by(project_id=project.id).order_by(ExternalResearchJobEvent.id.desc()).limit(100).all()
        return render_template("external_research.html", project=project, jobs=jobs, enabled=get_bool(EXTERNAL_RESEARCH_ENABLED), promotions=promotions, retry_origins=retry_origins, activity_events=activity_events)

    @app.get("/projects/<int:project_id>/research/activity")
    @login_required
    def external_research_activity(project_id):
        project = db.get_or_404(SystemProject, project_id)
        events = ExternalResearchJobEvent.query.filter_by(project_id=project.id).order_by(ExternalResearchJobEvent.id.desc()).limit(100).all()
        jobs = ExternalResearchJob.query.filter_by(project_id=project.id).order_by(ExternalResearchJob.id.desc()).limit(20).all()
        return {"running": sum(job.status == "running" for job in jobs), "events": [{"id": event.id, "job_id": event.job_id, "event_type": event.event_type, "detail": event.detail, "created_at": event.created_at.isoformat()} for event in events]}

    @app.post("/projects/<int:project_id>/research/<int:job_id>/send")
    @login_required
    def send_external_research(project_id, job_id):
        project = db.get_or_404(SystemProject, project_id); job = db.get_or_404(ExternalResearchJob, job_id)
        if job.project_id != project.id: return ("Research job does not belong to project", 400)
        if job.status != "proposed": flash("This research query is no longer awaiting confirmation.", "warning"); return redirect(url_for("external_research", project_id=project.id))
        if not get_bool(EXTERNAL_RESEARCH_ENABLED):
            flash("External research is disabled. Local knowledge search remains available.", "danger"); return redirect(url_for("external_research", project_id=project.id))
        job.status = "running"; job.sent_at = utcnow()
        db.session.add(ExternalResearchJobEvent(project_id=project.id, job_id=job.id, event_type="provider_started", actor=current_user.username, detail=f"Confirmed and sent to fixed provider {job.provider}"))
        audit("external_research.send", "ExternalResearchJob", job.id, f"provider={job.provider}"); db.session.commit()
        outbound_query = job.outbound_query
        def run_research():
            try:
                citations = search_wikipedia(outbound_query)
                failure = None
            except ExternalResearchError as exc:
                citations, failure = [], str(exc)[:4000]
            with app.app_context():
                current_job = db.session.get(ExternalResearchJob, job_id)
                if current_job is None or current_job.status == "cancelled":
                    return
                current_job.completed_at = utcnow()
                if failure is None:
                    current_job.status = "completed"
                    current_job.results_json = json.dumps([citation.__dict__ for citation in citations], sort_keys=True)
                    db.session.add(ExternalResearchJobEvent(project_id=current_job.project_id, job_id=current_job.id, event_type="completed", actor="background-worker", detail=f"Provider returned {len(citations)} bounded citation(s)"))
                    db.session.add(AuditEvent(action="external_research.complete", object_type="ExternalResearchJob", object_id=str(job_id), detail=f"citations={len(citations)}"))
                else:
                    current_job.status = "failed"; current_job.error = failure
                    db.session.add(ExternalResearchJobEvent(project_id=current_job.project_id, job_id=current_job.id, event_type="failed", actor="background-worker", detail="Provider request failed; no local knowledge changed"))
                    db.session.add(AuditEvent(action="external_research.fail", object_type="ExternalResearchJob", object_id=str(job_id), detail=failure[:240]))
                db.session.commit()
        app.config["RESEARCH_TASK_SUBMITTER"](run_research)
        flash("External research started in the background. Refresh this page for progress.", "success")
        return redirect(url_for("external_research", project_id=project.id))

    @app.post("/projects/<int:project_id>/research/<int:job_id>/cancel")
    @login_required
    def cancel_external_research(project_id, job_id):
        project = db.get_or_404(SystemProject, project_id); job = db.get_or_404(ExternalResearchJob, job_id)
        if job.project_id != project.id: return ("Research job does not belong to project", 400)
        if job.status not in {"proposed", "running"}:
            flash("Only a proposed or running research job can be cancelled.", "warning"); return redirect(url_for("external_research", project_id=project.id))
        was_running = job.status == "running"
        job.status = "cancelled"; job.cancel_requested_at = utcnow(); job.completed_at = utcnow()
        detail = "Cancelled after provider request; any late response will be discarded" if was_running else "Cancelled before provider request"
        event = ExternalResearchJobEvent(project_id=project.id, job_id=job.id, event_type="cancelled", actor=current_user.username, detail=detail)
        db.session.add(event); audit("external_research.cancel", "ExternalResearchJob", job.id, "running" if was_running else "before-send"); db.session.commit()
        flash("Running research cancelled; any late provider response will be discarded." if was_running else "External research proposal cancelled without sending.", "success")
        return redirect(url_for("external_research", project_id=project.id))

    @app.post("/projects/<int:project_id>/research/<int:job_id>/retry")
    @login_required
    def retry_external_research(project_id, job_id):
        project = db.get_or_404(SystemProject, project_id); job = db.get_or_404(ExternalResearchJob, job_id)
        if job.project_id != project.id: return ("Research job does not belong to project", 400)
        if job.status != "failed":
            flash("Only a failed research job can be retried.", "warning"); return redirect(url_for("external_research", project_id=project.id))
        retry = ExternalResearchJob(project_id=project.id, original_query=job.original_query, outbound_query=job.outbound_query, provider=job.provider, status="proposed", requested_by=current_user.username)
        db.session.add(retry); db.session.flush()
        event = ExternalResearchJobEvent(project_id=project.id, job_id=job.id, related_job_id=retry.id, event_type="retried", actor=current_user.username, detail="Created new reviewable proposal; no provider request made")
        db.session.add(event); audit("external_research.retry", "ExternalResearchJob", retry.id, f"source_job={job.id}"); db.session.commit()
        flash(f"Retry prepared as job #{retry.id}. Review and confirm before sending.", "success"); return redirect(url_for("external_research", project_id=project.id))

    @app.post("/projects/<int:project_id>/research/<int:job_id>/citations/<int:citation_index>/promote")
    @login_required
    def promote_external_research_citation(project_id, job_id, citation_index):
        project = db.get_or_404(SystemProject, project_id); job = db.get_or_404(ExternalResearchJob, job_id)
        if job.project_id != project.id: return ("Research job does not belong to project", 400)
        if job.status != "completed": flash("Only citations from completed research can be promoted.", "danger"); return redirect(url_for("external_research", project_id=project.id))
        if ExternalResearchPromotion.query.filter_by(job_id=job.id, citation_index=citation_index).first():
            flash("That citation is already in local knowledge.", "warning"); return redirect(url_for("external_research", project_id=project.id))
        citations = json.loads(job.results_json)
        if citation_index < 0 or citation_index >= len(citations): return ("Citation does not exist", 404)
        citation = citations[citation_index]
        try:
            document = ingest_external_citation(project_id=project.id, job_id=job.id, citation_index=citation_index, title=citation.get("title", ""), url=citation.get("url", ""), excerpt=citation.get("excerpt", ""), data_dir=app.config["DATA_DIR"])
            promotion = ExternalResearchPromotion(project_id=project.id, job_id=job.id, citation_index=citation_index, document_id=document.id, promoted_by=current_user.username)
            db.session.add(promotion); db.session.add(DocumentVersion(project_id=project.id, document_id=document.id, family_id=str(uuid4()), version_number=1)); db.session.flush()
            db.session.add(ExternalResearchJobEvent(project_id=project.id, job_id=job.id, event_type="citation_promoted", actor=current_user.username, detail=f"Citation {citation_index + 1} saved as local document #{document.id}"))
            audit("external_research.promote", "ExternalResearchPromotion", promotion.id, f"job={job.id} citation={citation_index} document={document.id}"); db.session.commit()
            flash(f"Added '{document.title}' to local project knowledge.", "success")
        except KnowledgeIngestionError as exc:
            db.session.rollback(); flash(f"Citation could not be promoted: {exc}", "danger")
        return redirect(url_for("external_research", project_id=project.id))

    @app.route("/settings/control", methods=["GET", "POST"])
    @login_required
    def control_settings():
        if not current_user.is_admin: return ("Administrator access required", 403)
        if request.method == "POST":
            section = request.form.get("section")
            if section == "llm":
                ollama_url = request.form.get("ollama_url", "").strip().rstrip("/")
                ollama_model = request.form.get("ollama_model", "").strip()
                if not ollama_url.startswith(("http://", "https://")):
                    flash("Ollama URL must begin with http:// or https://.", "danger")
                elif not ollama_model:
                    flash("Ollama model is required.", "danger")
                else:
                    set_text("ollama_url", ollama_url); set_text("ollama_model", ollama_model)
                    audit("setting.update", "AppSetting", "ollama", f"url={ollama_url} model={ollama_model}"); db.session.commit()
                    flash("LLM settings saved and active.", "success")
            elif section == "external_research":
                enabled = request.form.get("external_research_enabled") == "on"
                set_bool(EXTERNAL_RESEARCH_ENABLED, enabled); audit("setting.update", "AppSetting", EXTERNAL_RESEARCH_ENABLED, f"enabled={enabled}"); db.session.commit()
                flash(f"External research {'enabled' if enabled else 'disabled'}.", "success")
            else:
                enabled = request.form.get("codex_control_enabled") == "on"
                if enabled and not app.config.get("CODEX_CONTROL_TOKEN"):
                    flash("Set CODEX_CONTROL_TOKEN in the environment before enabling Codex control.", "danger")
                else:
                    set_bool(CODEX_CONTROL_ENABLED, enabled)
                    audit("setting.update", "AppSetting", CODEX_CONTROL_ENABLED, f"enabled={enabled}")
                    db.session.commit()
                    flash(f"Codex control API {'enabled' if enabled else 'disabled'}.", "success")
            return redirect(url_for("control_settings"))
        return render_template("control_settings.html", enabled=get_bool(CODEX_CONTROL_ENABLED), external_research_enabled=get_bool(EXTERNAL_RESEARCH_ENABLED), token_configured=bool(app.config.get("CODEX_CONTROL_TOKEN")), ollama_url=get_text("ollama_url", app.config["OLLAMA_URL"]), ollama_model=get_text("ollama_model", app.config["OLLAMA_MODEL"]))

    @app.get("/health")
    def health(): return {"status": "ok", "service": "system-knowledge-designer"}

    @app.get("/ready")
    def ready():
        report, status = readiness_report(session=db.session, data_dir=app.config["DATA_DIR"])
        return report, status

    with app.app_context():
        db.create_all()
        ensure_fts_index()
        if not User.query.filter_by(username=app.config["ADMIN_USERNAME"]).first():
            user = User(username=app.config["ADMIN_USERNAME"], is_admin=True); user.set_password(app.config["ADMIN_PASSWORD"]); db.session.add(user); db.session.commit()
    return app


def audit(action, object_type, object_id, detail=""):
    db.session.add(AuditEvent(actor_id=current_user.id if current_user.is_authenticated else None, action=action, object_type=object_type, object_id=str(object_id), detail=detail))


def persist_assistant_sql_execution(project, result: dict) -> SQLExecution:
    execution = SQLExecution(project_id=project.id, sandbox_build_id=result["sandbox_build_id"], statement=result["statement"], referenced_objects_json=json.dumps({"tables": result["tables"], "columns": result["columns"]}, sort_keys=True), status="completed", row_count=result["row_count"], runtime_ms=result["runtime_ms"])
    db.session.add(execution); db.session.flush(); result["sql_execution_id"] = execution.id
    audit("assistant_sql.execute", "SQLExecution", execution.id, f"rows={execution.row_count} sandbox={execution.sandbox_build_id}")
    return execution


def starter_source(name: str) -> str:
    model_name = re.sub(r"[^A-Za-z0-9_]", "_", name) or "New_System"
    return f'''erModel {model_name} {{
  dialect "sqlite";
  direction LR;
  subjectArea Core {{
    table SUPPLIER {{
      integer supplier_id PK description="Unique supplier identifier";
      string supplier_name length=200 not_null description="Supplier display name";
    }}
    table PURCHASE_ORDER {{
      integer purchase_order_id PK description="Unique purchase order identifier";
      integer supplier_id FK not_null description="Supplier that receives the order";
      decimal order_value precision=18 scale=2 description="Total monetary value of the order";
    }}
    relationship PURCHASE_ORDER.supplier_id -> SUPPLIER.supplier_id {{
      cardinality many-to-one;
      label "placed with";
    }}
  }}
}}'''


app = create_app()

if __name__ == "__main__": app.run(host="0.0.0.0", port=5015)
