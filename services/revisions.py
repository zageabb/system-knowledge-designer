from __future__ import annotations

import difflib
import hashlib, json
from sqlalchemy import func

from database import db
from models import ColumnDefinition, DiagramRevision, RelationshipDefinition, SystemProject, TableDefinition
from services.er_language.schema import ERModel


def create_revision(project: SystemProject, source: str, model: ERModel, note: str = "") -> DiagramRevision:
    model_json = model.model_dump_json()
    number = (db.session.query(func.max(DiagramRevision.revision_number)).filter_by(project_id=project.id).scalar() or 0) + 1
    revision = DiagramRevision(project=project, revision_number=number, source=source, model_json=model_json, model_hash=hashlib.sha256(model_json.encode()).hexdigest(), revision_note=note)
    db.session.add(revision); db.session.flush()
    for table in model.tables:
        record = TableDefinition(project_id=project.id, revision_id=revision.id, subject_area=table.subject_area, name=table.name, kind=table.kind)
        db.session.add(record); db.session.flush()
        for position, column in enumerate(table.columns):
            db.session.add(ColumnDefinition(table=record, position=position, name=column.name, data_type=column.data_type, nullable=column.nullable, primary_key="PK" in column.markers, foreign_key="FK" in column.markers, unique="unique" in column.markers, attributes_json=json.dumps(column.attributes, sort_keys=True)))
    for rel in model.relationships:
        db.session.add(RelationshipDefinition(project_id=project.id, revision_id=revision.id, source_table=rel.source_table, source_column=rel.source_column, target_table=rel.target_table, target_column=rel.target_column, cardinality=rel.cardinality, label=rel.label))
    db.session.flush()
    return revision


def unified_source_diff(older: DiagramRevision, newer: DiagramRevision) -> str:
    return "".join(difflib.unified_diff(
        older.source.splitlines(keepends=True),
        newer.source.splitlines(keepends=True),
        fromfile=f"revision-{older.revision_number}.erd",
        tofile=f"revision-{newer.revision_number}.erd",
    ))
