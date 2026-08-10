from __future__ import annotations

import re
from collections import deque

from models import CrossProjectAttachment, DiagramRevision, KnowledgeDocument, ProjectAlias, ProjectLink, SystemProject


class ProjectGraphError(ValueError):
    pass


RELATIONSHIP_TYPES = {"depends-on", "integrates-with", "provides-data-to", "replaces"}


def normalize_alias(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()
    if len(normalized) < 2:
        raise ProjectGraphError("Alias must contain at least two letters or numbers.")
    return normalized[:160]


def validate_project_link(source_project_id: int, target_project_id: int, relationship_type: str) -> str:
    if source_project_id == target_project_id:
        raise ProjectGraphError("A project cannot link to itself.")
    if relationship_type not in RELATIONSHIP_TYPES:
        raise ProjectGraphError("Unknown project relationship type.")
    return relationship_type


def traverse_projects(start_project_id: int, links: list[ProjectLink], *, max_depth: int = 3, max_nodes: int = 50) -> list[dict]:
    adjacency = {}
    for link in links:
        adjacency.setdefault(link.source_project_id, []).append((link.target_project_id, link))
        adjacency.setdefault(link.target_project_id, []).append((link.source_project_id, link))
    queue = deque([(start_project_id, 0)])
    seen = {start_project_id}
    result = []
    while queue and len(seen) < max_nodes:
        project_id, depth = queue.popleft()
        if depth >= max_depth:
            continue
        for neighbour, link in sorted(adjacency.get(project_id, []), key=lambda item: (item[0], item[1].id or 0)):
            if neighbour in seen:
                continue
            seen.add(neighbour); queue.append((neighbour, depth + 1))
            result.append({"project_id": neighbour, "depth": depth + 1, "via_link_id": link.id})
            if len(seen) >= max_nodes:
                break
    return result


def scan_project_integrity() -> list[dict]:
    issues = []
    project_ids = {row.id for row in SystemProject.query.all()}
    for link in ProjectLink.query.order_by(ProjectLink.id).all():
        if link.source_project_id == link.target_project_id:
            issues.append({"type": "self-link", "link_id": link.id})
        if link.source_project_id not in project_ids or link.target_project_id not in project_ids:
            issues.append({"type": "missing-project", "link_id": link.id})
    for project in SystemProject.query.order_by(SystemProject.id).all():
        if project.active_revision_id:
            revision = DiagramRevision.query.filter_by(id=project.active_revision_id, project_id=project.id).first()
            if revision is None:
                issues.append({"type": "invalid-active-revision", "project_id": project.id})
    for alias in ProjectAlias.query.order_by(ProjectAlias.id).all():
        if alias.project_id not in project_ids:
            issues.append({"type": "missing-alias-project", "alias_id": alias.id})
    linked_pairs = {(link.source_project_id, link.target_project_id) for link in ProjectLink.query.all()}
    linked_pairs |= {(target, source) for source, target in linked_pairs}
    for attachment in CrossProjectAttachment.query.order_by(CrossProjectAttachment.id).all():
        document = KnowledgeDocument.query.filter_by(id=attachment.document_id, project_id=attachment.source_project_id).first()
        if document is None:
            issues.append({"type": "invalid-attachment-document", "attachment_id": attachment.id})
        if (attachment.consumer_project_id, attachment.source_project_id) not in linked_pairs:
            issues.append({"type": "unlinked-attachment-projects", "attachment_id": attachment.id})
    return issues


def projects_are_linked(first_id: int, second_id: int) -> bool:
    return ProjectLink.query.filter(
        ((ProjectLink.source_project_id == first_id) & (ProjectLink.target_project_id == second_id)) |
        ((ProjectLink.source_project_id == second_id) & (ProjectLink.target_project_id == first_id))
    ).first() is not None
