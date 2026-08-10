from __future__ import annotations

from models import ERInclude


def normalize_include_name(value: str) -> str:
    normalized = " ".join(value.casefold().split())
    if not normalized or len(normalized) > 160:
        raise ValueError("Include name must contain 1 to 160 characters.")
    return normalized


def include_sources(project_id: int) -> dict[str, str]:
    return {record.normalized_name: record.source for record in ERInclude.query.filter_by(project_id=project_id).all()}
