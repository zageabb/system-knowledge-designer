from __future__ import annotations

from datetime import datetime, timezone

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from database import db


def utcnow():
    return datetime.now(timezone.utc)


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)

    def set_password(self, value: str) -> None:
        self.password_hash = generate_password_hash(value)

    def check_password(self, value: str) -> bool:
        return check_password_hash(self.password_hash, value)


class TimestampMixin:
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class AppSetting(TimestampMixin, db.Model):
    key = db.Column(db.String(120), primary_key=True)
    value = db.Column(db.Text, default="", nullable=False)


class SystemProject(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False)
    slug = db.Column(db.String(160), unique=True, nullable=False)
    description = db.Column(db.Text, default="", nullable=False)
    platform = db.Column(db.String(80), default="SQLite", nullable=False)
    dialect = db.Column(db.String(40), default="sqlite", nullable=False)
    active_revision_id = db.Column(db.Integer, db.ForeignKey("diagram_revision.id"), nullable=True)
    revisions = db.relationship("DiagramRevision", foreign_keys="DiagramRevision.project_id", back_populates="project", cascade="all, delete-orphan")


class DiagramRevision(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("system_project.id"), nullable=False, index=True)
    revision_number = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(24), default="draft", nullable=False)
    source = db.Column(db.Text, nullable=False)
    model_json = db.Column(db.Text, nullable=False)
    model_hash = db.Column(db.String(64), nullable=False)
    revision_note = db.Column(db.Text, default="", nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    approved_at = db.Column(db.DateTime(timezone=True))
    project = db.relationship("SystemProject", foreign_keys=[project_id], back_populates="revisions")
    __table_args__ = (db.UniqueConstraint("project_id", "revision_number"),)


class TableDefinition(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("system_project.id"), nullable=False, index=True)
    revision_id = db.Column(db.Integer, db.ForeignKey("diagram_revision.id"), nullable=False, index=True)
    subject_area = db.Column(db.String(160), nullable=False)
    name = db.Column(db.String(160), nullable=False)
    kind = db.Column(db.String(20), default="table", nullable=False)
    columns = db.relationship("ColumnDefinition", back_populates="table", cascade="all, delete-orphan")


class ColumnDefinition(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    table_id = db.Column(db.Integer, db.ForeignKey("table_definition.id"), nullable=False, index=True)
    position = db.Column(db.Integer, nullable=False)
    name = db.Column(db.String(160), nullable=False)
    data_type = db.Column(db.String(80), nullable=False)
    nullable = db.Column(db.Boolean, default=True, nullable=False)
    primary_key = db.Column(db.Boolean, default=False, nullable=False)
    foreign_key = db.Column(db.Boolean, default=False, nullable=False)
    unique = db.Column(db.Boolean, default=False, nullable=False)
    attributes_json = db.Column(db.Text, default="{}", nullable=False)
    table = db.relationship("TableDefinition", back_populates="columns")


class RelationshipDefinition(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("system_project.id"), nullable=False, index=True)
    revision_id = db.Column(db.Integer, db.ForeignKey("diagram_revision.id"), nullable=False, index=True)
    source_table = db.Column(db.String(160), nullable=False)
    source_column = db.Column(db.String(160), nullable=False)
    target_table = db.Column(db.String(160), nullable=False)
    target_column = db.Column(db.String(160), nullable=False)
    cardinality = db.Column(db.String(40), default="many-to-one", nullable=False)
    label = db.Column(db.String(200), default="", nullable=False)


class SampleDataset(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("system_project.id"), nullable=False, index=True)
    name = db.Column(db.String(160), nullable=False)
    description = db.Column(db.Text, default="", nullable=False)
    provenance = db.Column(db.String(80), default="synthetic", nullable=False)
    classification = db.Column(db.String(80), default="non-sensitive", nullable=False)
    rows = db.relationship("SampleRowDefinition", back_populates="dataset", cascade="all, delete-orphan")


class SampleRowDefinition(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    dataset_id = db.Column(db.Integer, db.ForeignKey("sample_dataset.id"), nullable=False, index=True)
    table_name = db.Column(db.String(160), nullable=False)
    position = db.Column(db.Integer, nullable=False)
    values_json = db.Column(db.Text, nullable=False)
    dataset = db.relationship("SampleDataset", back_populates="rows")
    __table_args__ = (db.UniqueConstraint("dataset_id", "table_name", "position"),)


class SandboxBuild(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("system_project.id"), nullable=False, index=True)
    dataset_id = db.Column(db.Integer, db.ForeignKey("sample_dataset.id"), nullable=False)
    revision_id = db.Column(db.Integer, db.ForeignKey("diagram_revision.id"), nullable=False)
    status = db.Column(db.String(24), default="running", nullable=False)
    managed_path = db.Column(db.String(500), nullable=False)
    build_hash = db.Column(db.String(64), nullable=False)
    row_count = db.Column(db.Integer, default=0, nullable=False)
    warnings_json = db.Column(db.Text, default="[]", nullable=False)
    error = db.Column(db.Text, default="", nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    completed_at = db.Column(db.DateTime(timezone=True))


class SQLExecution(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("system_project.id"), nullable=False, index=True)
    sandbox_build_id = db.Column(db.Integer, db.ForeignKey("sandbox_build.id"), nullable=False)
    statement = db.Column(db.Text, nullable=False)
    referenced_objects_json = db.Column(db.Text, default="[]", nullable=False)
    status = db.Column(db.String(24), nullable=False)
    row_count = db.Column(db.Integer, default=0, nullable=False)
    runtime_ms = db.Column(db.Float, default=0, nullable=False)
    error = db.Column(db.Text, default="", nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)


class AIAction(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("system_project.id"), nullable=False, index=True)
    dataset_id = db.Column(db.Integer, db.ForeignKey("sample_dataset.id"), nullable=True)
    action_type = db.Column(db.String(80), nullable=False)
    status = db.Column(db.String(40), default="proposed", nullable=False)
    payload_json = db.Column(db.Text, nullable=False)
    result_json = db.Column(db.Text, default="{}", nullable=False)
    requested_by = db.Column(db.String(80), default="user", nullable=False)
    confirmed_at = db.Column(db.DateTime(timezone=True))


class KnowledgeDocument(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("system_project.id"), nullable=False, index=True)
    title = db.Column(db.String(240), nullable=False)
    original_filename = db.Column(db.String(240), nullable=False)
    media_type = db.Column(db.String(120), nullable=False)
    managed_path = db.Column(db.String(500), nullable=False)
    content_hash = db.Column(db.String(64), nullable=False)
    provenance = db.Column(db.String(80), default="uploaded", nullable=False)
    classification = db.Column(db.String(80), default="internal", nullable=False)
    status = db.Column(db.String(40), default="indexed", nullable=False)
    warnings_json = db.Column(db.Text, default="[]", nullable=False)
    chunks = db.relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")
    links = db.relationship("KnowledgeLink", back_populates="document", cascade="all, delete-orphan")
    version = db.relationship("DocumentVersion", foreign_keys="DocumentVersion.document_id", back_populates="document", cascade="all, delete-orphan", uselist=False)


class DocumentChunk(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey("knowledge_document.id"), nullable=False, index=True)
    position = db.Column(db.Integer, nullable=False)
    locator = db.Column(db.String(240), nullable=False)
    text = db.Column(db.Text, nullable=False)
    document = db.relationship("KnowledgeDocument", back_populates="chunks")
    links = db.relationship("ChunkKnowledgeLink", back_populates="chunk", cascade="all, delete-orphan")
    __table_args__ = (db.UniqueConstraint("document_id", "position"),)


class KnowledgeLink(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("system_project.id"), nullable=False, index=True)
    document_id = db.Column(db.Integer, db.ForeignKey("knowledge_document.id"), nullable=False, index=True)
    revision_id = db.Column(db.Integer, db.ForeignKey("diagram_revision.id"), nullable=False)
    target_type = db.Column(db.String(40), nullable=False)
    target_key = db.Column(db.String(340), nullable=False)
    created_by = db.Column(db.String(80), nullable=False)
    document = db.relationship("KnowledgeDocument", back_populates="links")
    __table_args__ = (db.UniqueConstraint("document_id", "revision_id", "target_type", "target_key"),)


class DocumentVersion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("system_project.id"), nullable=False, index=True)
    document_id = db.Column(db.Integer, db.ForeignKey("knowledge_document.id"), nullable=False, unique=True, index=True)
    family_id = db.Column(db.String(36), nullable=False, index=True)
    version_number = db.Column(db.Integer, nullable=False)
    predecessor_document_id = db.Column(db.Integer, db.ForeignKey("knowledge_document.id"), nullable=True)
    document = db.relationship("KnowledgeDocument", foreign_keys=[document_id], back_populates="version")
    __table_args__ = (db.UniqueConstraint("family_id", "version_number"),)


class ChunkKnowledgeLink(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("system_project.id"), nullable=False, index=True)
    chunk_id = db.Column(db.Integer, db.ForeignKey("document_chunk.id"), nullable=False, index=True)
    revision_id = db.Column(db.Integer, db.ForeignKey("diagram_revision.id"), nullable=False)
    target_type = db.Column(db.String(40), nullable=False)
    target_key = db.Column(db.String(340), nullable=False)
    created_by = db.Column(db.String(80), nullable=False)
    chunk = db.relationship("DocumentChunk", back_populates="links")
    __table_args__ = (db.UniqueConstraint("chunk_id", "revision_id", "target_type", "target_key"),)


class EvidenceRecord(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("system_project.id"), nullable=False, index=True)
    search_query = db.Column("query", db.String(500), nullable=False)
    source_filter = db.Column(db.String(40), nullable=False)
    model_revision_id = db.Column(db.Integer, db.ForeignKey("diagram_revision.id"), nullable=True)
    evidence_json = db.Column(db.Text, nullable=False)
    created_by = db.Column(db.String(80), nullable=False)


class AssistantExchange(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("system_project.id"), nullable=False, index=True)
    question = db.Column(db.Text, nullable=False)
    answer_json = db.Column(db.Text, nullable=False)
    evidence_json = db.Column(db.Text, nullable=False)
    model_name = db.Column(db.String(160), nullable=False)
    requested_by = db.Column(db.String(80), nullable=False)


class AssistantContextLink(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("system_project.id"), nullable=False, index=True)
    exchange_id = db.Column(db.Integer, db.ForeignKey("assistant_exchange.id"), nullable=False, unique=True, index=True)
    parent_exchange_id = db.Column(db.Integer, db.ForeignKey("assistant_exchange.id"), nullable=False, index=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)


class AssistantToolCall(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("system_project.id"), nullable=False, index=True)
    tool_name = db.Column(db.String(100), nullable=False)
    input_json = db.Column(db.Text, nullable=False)
    result_json = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(30), nullable=False)
    requested_by = db.Column(db.String(80), nullable=False)


class ExternalResearchJob(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("system_project.id"), nullable=False, index=True)
    original_query = db.Column(db.Text, nullable=False)
    outbound_query = db.Column(db.String(500), nullable=False)
    provider = db.Column(db.String(80), nullable=False)
    status = db.Column(db.String(30), nullable=False, default="proposed")
    results_json = db.Column(db.Text, nullable=False, default="[]")
    error = db.Column(db.Text, nullable=False, default="")
    requested_by = db.Column(db.String(80), nullable=False)
    sent_at = db.Column(db.DateTime(timezone=True))
    cancel_requested_at = db.Column(db.DateTime(timezone=True))
    completed_at = db.Column(db.DateTime(timezone=True))


class ExternalResearchPromotion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("system_project.id"), nullable=False, index=True)
    job_id = db.Column(db.Integer, db.ForeignKey("external_research_job.id"), nullable=False, index=True)
    citation_index = db.Column(db.Integer, nullable=False)
    document_id = db.Column(db.Integer, db.ForeignKey("knowledge_document.id"), nullable=False, unique=True, index=True)
    promoted_by = db.Column(db.String(80), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    __table_args__ = (db.UniqueConstraint("job_id", "citation_index"),)


class ExternalResearchJobEvent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("system_project.id"), nullable=False, index=True)
    job_id = db.Column(db.Integer, db.ForeignKey("external_research_job.id"), nullable=False, index=True)
    event_type = db.Column(db.String(40), nullable=False)
    related_job_id = db.Column(db.Integer, db.ForeignKey("external_research_job.id"), nullable=True)
    actor = db.Column(db.String(80), nullable=False)
    detail = db.Column(db.Text, nullable=False, default="")
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)


class ProjectLink(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    source_project_id = db.Column(db.Integer, db.ForeignKey("system_project.id"), nullable=False, index=True)
    target_project_id = db.Column(db.Integer, db.ForeignKey("system_project.id"), nullable=False, index=True)
    relationship_type = db.Column(db.String(40), nullable=False)
    label = db.Column(db.String(200), nullable=False, default="")
    created_by = db.Column(db.String(80), nullable=False)
    __table_args__ = (db.UniqueConstraint("source_project_id", "target_project_id", "relationship_type"),)


class ProjectAlias(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("system_project.id"), nullable=False, index=True)
    alias = db.Column(db.String(160), nullable=False)
    normalized_alias = db.Column(db.String(160), nullable=False, unique=True, index=True)
    trusted = db.Column(db.Boolean, nullable=False, default=False)
    created_by = db.Column(db.String(80), nullable=False)


class ProjectIntegrityScan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    status = db.Column(db.String(30), nullable=False)
    results_json = db.Column(db.Text, nullable=False, default="[]")
    issue_count = db.Column(db.Integer, nullable=False, default=0)
    requested_by = db.Column(db.String(80), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)


class CrossProjectAttachment(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    consumer_project_id = db.Column(db.Integer, db.ForeignKey("system_project.id"), nullable=False, index=True)
    source_project_id = db.Column(db.Integer, db.ForeignKey("system_project.id"), nullable=False, index=True)
    document_id = db.Column(db.Integer, db.ForeignKey("knowledge_document.id"), nullable=False, index=True)
    created_by = db.Column(db.String(80), nullable=False)
    __table_args__ = (db.UniqueConstraint("consumer_project_id", "document_id"),)


class AuditEvent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    actor_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    action = db.Column(db.String(100), nullable=False)
    object_type = db.Column(db.String(80), nullable=False)
    object_id = db.Column(db.String(80), nullable=False)
    detail = db.Column(db.Text, default="", nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
