from __future__ import annotations

import json
from pydantic import BaseModel, Field, ValidationError

from services.er_language.schema import ERModel
from services.ollama import OllamaClient
from services.sample_data import SampleValidationError, validate_row


class GeneratedRows(BaseModel):
    rows: list[dict] = Field(min_length=1, max_length=20)
    notes: str = ""


class AIRecordGenerationError(ValueError): pass


def relationship_constraints(*, model: ERModel, table_name: str, related_rows_by_table: dict[str, list[dict]] | None = None) -> list[dict]:
    """Return bounded, deterministic FK choices for a table's outgoing relationships."""
    rows_by_table = {name.casefold(): rows for name, rows in (related_rows_by_table or {}).items()}
    constraints = []
    for relationship in model.relationships:
        if relationship.source_table.casefold() != table_name.casefold():
            continue
        values = []
        for row in rows_by_table.get(relationship.target_table.casefold(), []):
            value = next((value for key, value in row.items() if key.casefold() == relationship.target_column.casefold()), None)
            if value is not None and value not in values:
                values.append(value)
        constraints.append({
            "field": relationship.source_column,
            "references": f"{relationship.target_table}.{relationship.target_column}",
            "allowed_values": values[:100],
        })
    return constraints


def validate_relationship_references(*, model: ERModel, table_name: str, rows: list[dict], related_rows_by_table: dict[str, list[dict]] | None = None) -> None:
    for constraint in relationship_constraints(model=model, table_name=table_name, related_rows_by_table=related_rows_by_table):
        allowed = constraint["allowed_values"]
        for index, row in enumerate(rows, 1):
            value = next((value for key, value in row.items() if key.casefold() == constraint["field"].casefold()), None)
            if value is not None and value not in allowed:
                choices = ", ".join(repr(item) for item in allowed) if allowed else "none (add referenced rows first)"
                raise AIRecordGenerationError(
                    f"Generated row {index} has invalid foreign key {table_name}.{constraint['field']}={value!r}. "
                    f"Allowed values from {constraint['references']}: {choices}."
                )


def generate_record_proposal(*, model: ERModel, table_name: str, count: int, instructions: str, ollama_url: str, ollama_model: str, existing_rows: list[dict] | None = None, related_rows_by_table: dict[str, list[dict]] | None = None, client=None) -> GeneratedRows:
    table = next((item for item in model.tables if item.name.casefold() == table_name.casefold()), None)
    if table is None: raise AIRecordGenerationError(f"Unknown table '{table_name}'.")
    count = max(1, min(count, 20))
    schema = [{"name": column.name, "type": column.data_type, "nullable": column.nullable, "markers": column.markers, "attributes": column.attributes} for column in table.columns]
    constraints = relationship_constraints(model=model, table_name=table.name, related_rows_by_table=related_rows_by_table)
    prompt = f"""You generate synthetic, non-sensitive demonstration records for a system design.
Return JSON only with this exact shape: {{"rows": [{{...}}], "notes": "short explanation"}}.
Generate exactly {count} rows for table {table.name}.
Use every field name exactly as supplied. Respect types, nullability, lengths, primary keys and uniqueness.
Do not use real people, real customer data, secrets, internal URLs or production identifiers.
Table schema: {json.dumps(schema, sort_keys=True)}
Existing rows to avoid duplicating: {json.dumps((existing_rows or [])[:20], sort_keys=True)}
Foreign-key constraints: {json.dumps(constraints, sort_keys=True)}
For each foreign-key field, use only a value in allowed_values. If allowed_values is empty, do not invent a reference.
User instructions: {instructions or 'Create realistic synthetic examples.'}
"""
    raw = (client or OllamaClient(ollama_url)).generate_json(ollama_model, prompt)
    try: generated = GeneratedRows.model_validate(raw)
    except ValidationError as exc: raise AIRecordGenerationError(f"Generated response has the wrong structure: {exc}") from exc
    if len(generated.rows) != count: raise AIRecordGenerationError(f"Ollama returned {len(generated.rows)} rows; exactly {count} were requested.")
    validated = []
    for index, row in enumerate(generated.rows, 1):
        try: validated.append(validate_row(model, table.name, row))
        except SampleValidationError as exc: raise AIRecordGenerationError(f"Generated row {index} failed validation: {exc}") from exc
    validate_relationship_references(model=model, table_name=table.name, rows=validated, related_rows_by_table=related_rows_by_table)
    return GeneratedRows(rows=validated, notes=generated.notes)
