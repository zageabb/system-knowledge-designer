from __future__ import annotations

import json
import re
from collections import deque

from database import db
from models import ChunkKnowledgeLink, CrossProjectAttachment, DiagramRevision, KnowledgeDocument, KnowledgeLink, ProjectAlias, ProjectLink, SampleDataset, SystemProject, TableDefinition
from services.knowledge import search_documents


def search_schema(*, project, query: str, limit: int = 30) -> list[dict]:
    revision_id = project.active_revision_id
    if not revision_id:
        return []
    terms = _terms(query)
    if not terms:
        return []
    tables = TableDefinition.query.filter_by(project_id=project.id, revision_id=revision_id).order_by(TableDefinition.name).all()
    results = []
    for table in tables:
        table_match = any(term in table.name.casefold() or term in table.subject_area.casefold() for term in terms)
        matching_columns = [column for column in table.columns if any(term in column.name.casefold() or term in column.data_type.casefold() for term in terms)]
        if table_match or matching_columns:
            column_text = ", ".join(f"{column.name} ({column.data_type})" for column in (matching_columns or table.columns[:8]))
            results.append({"kind": "schema", "title": table.name, "locator": f"Subject area: {table.subject_area}", "excerpt": column_text})
        if len(results) >= limit:
            break
    return results


def search_relationships(*, project, query: str, limit: int = 20) -> list[dict]:
    revision = DiagramRevision.query.filter_by(id=project.active_revision_id, project_id=project.id).first() if project.active_revision_id else None
    if not revision:
        return []
    model = json.loads(revision.model_json)
    terms = _terms(query)
    results = []
    for relationship in model.get("relationships", []):
        route = f"{relationship['source_table']}.{relationship['source_column']} → {relationship['target_table']}.{relationship['target_column']}"
        searchable = " ".join((route, relationship.get("label", ""), relationship.get("cardinality", ""))).casefold()
        if any(term in searchable for term in terms):
            results.append({"kind": "relationship", "title": relationship.get("label") or "Schema relationship", "locator": relationship.get("cardinality", "relationship"), "excerpt": route})
        if len(results) >= limit:
            break
    remaining = max(0, limit - len(results))
    if remaining and len(terms) >= 2:
        results.extend(_relationship_paths(model, terms, remaining))
    return results


def search_sample_values(*, project_id: int, query: str, limit: int = 20) -> list[dict]:
    needle = query.casefold().strip()
    if not needle:
        return []
    results = []
    datasets = SampleDataset.query.filter_by(project_id=project_id).order_by(SampleDataset.updated_at.desc()).all()
    for dataset in datasets:
        for row in dataset.rows:
            values = json.loads(row.values_json)
            matches = [f"{key}={value}" for key, value in values.items() if needle in str(key).casefold() or needle in str(value).casefold()]
            if matches:
                results.append({"kind": "sample", "title": f"{dataset.name} · {row.table_name}", "locator": f"Row {row.position} · {dataset.classification}", "excerpt": ", ".join(matches[:8])})
            if len(results) >= limit:
                return results
    return results


def search_cross_project_evidence(*, project, query: str, limit: int = 20) -> list[dict]:
    results = []
    attachments = CrossProjectAttachment.query.filter_by(consumer_project_id=project.id).order_by(CrossProjectAttachment.id).all()
    for attachment in attachments:
        document = KnowledgeDocument.query.filter_by(id=attachment.document_id, project_id=attachment.source_project_id).first()
        if not document:
            continue
        source_project = db.session.get(SystemProject, attachment.source_project_id)
        document_chunk_ids = {chunk.id for chunk in document.chunks}
        for match in search_documents(project_id=attachment.source_project_id, query=query, limit=limit):
            if match["chunk_id"] in document_chunk_ids:
                results.append({**match, "kind": "attached-document", "source_project_id": source_project.id, "source_project_name": source_project.name})
                if len(results) >= limit:
                    return results
    linked_ids = set()
    for link in ProjectLink.query.filter((ProjectLink.source_project_id == project.id) | (ProjectLink.target_project_id == project.id)).all():
        linked_ids.add(link.target_project_id if link.source_project_id == project.id else link.source_project_id)
    normalized_query = " ".join(_terms(query))
    aliases = ProjectAlias.query.filter(ProjectAlias.trusted.is_(True), ProjectAlias.project_id.in_(linked_ids or {-1})).all()
    for alias in aliases:
        if alias.normalized_alias not in normalized_query:
            continue
        source_project = db.session.get(SystemProject, alias.project_id)
        schema_query = normalized_query.replace(alias.normalized_alias, " ").strip() or query
        for match in search_schema(project=source_project, query=schema_query, limit=limit - len(results)):
            results.append({**match, "kind": "aliased-schema", "source_project_id": source_project.id, "source_project_name": source_project.name, "matched_alias": alias.alias})
        if len(results) >= limit:
            break
    return results


def knowledge_coverage(*, project, model) -> dict:
    table_targets = {table.name for table in model.tables} if model else set()
    column_targets = {f"{table.name}.{column.name}" for table in model.tables for column in table.columns} if model else set()
    links = KnowledgeLink.query.filter_by(project_id=project.id).all(); chunk_links = ChunkKnowledgeLink.query.filter_by(project_id=project.id).all()
    all_links = links + chunk_links
    linked_tables = {link.target_key for link in all_links if link.target_type == "table" and link.target_key in table_targets}
    linked_columns = {link.target_key for link in all_links if link.target_type == "column" and link.target_key in column_targets}
    stale = [link for link in all_links if (link.target_type == "table" and link.target_key not in table_targets) or (link.target_type == "column" and link.target_key not in column_targets)]
    documents = KnowledgeDocument.query.filter_by(project_id=project.id).all()
    linked_document_ids = {link.document_id for link in links} | {link.chunk.document_id for link in chunk_links}
    return {
        "tables_total": len(table_targets), "tables_linked": len(linked_tables),
        "columns_total": len(column_targets), "columns_linked": len(linked_columns),
        "documents_total": len(documents), "documents_unlinked": sum(document.id not in linked_document_ids for document in documents),
        "stale_links": stale,
    }


def _terms(query: str) -> list[str]:
    return [term.casefold() for term in re.findall(r"[A-Za-z0-9_]+", query) if len(term) > 1][:8]


def _relationship_paths(model: dict, terms: list[str], limit: int, max_hops: int = 4) -> list[dict]:
    tables = model.get("tables", [])
    searchable = {table["name"]: " ".join([table["name"]] + [column["name"] for column in table.get("columns", [])]).casefold() for table in tables}
    starts = {name for name, value in searchable.items() if terms[0] in value}
    ends = {name for name, value in searchable.items() if any(term in value for term in terms[1:])}
    adjacency = {name: [] for name in searchable}
    for relationship in model.get("relationships", []):
        source = relationship["source_table"]; target = relationship["target_table"]
        edge = f"{source}.{relationship['source_column']} → {target}.{relationship['target_column']}"
        adjacency.setdefault(source, []).append((target, edge)); adjacency.setdefault(target, []).append((source, edge))
    found = []; seen_paths = set()
    for start in sorted(starts):
        queue = deque([(start, [], {start})])
        while queue and len(found) < limit:
            node, edges, visited = queue.popleft()
            if node in ends and node != start and edges:
                signature = tuple(edges)
                if signature not in seen_paths:
                    seen_paths.add(signature); found.append({"kind": "path", "title": f"Relationship path: {start} to {node}", "locator": f"{len(edges)} hop{'s' if len(edges) != 1 else ''}", "excerpt": "  |  ".join(edges)})
                continue
            if len(edges) >= max_hops: continue
            for neighbor, edge in adjacency.get(node, []):
                if neighbor not in visited: queue.append((neighbor, edges + [edge], visited | {neighbor}))
    return found
