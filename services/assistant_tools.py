from __future__ import annotations

from database import db
from models import DocumentChunk
from services.sql_safety import SQLValidationError, validate_readonly_sql


class AssistantToolError(ValueError): pass


READ_TOOLS = {
    "schema.inspect": "Inspect one table in the active authoritative model",
    "documents.read_chunk": "Read one project-scoped citation chunk",
    "sql.validate": "Validate one read-only statement without executing it",
}


def execute_read_tool(*, tool_name: str, argument: str, project, model) -> dict:
    if tool_name not in READ_TOOLS: raise AssistantToolError("Unknown or non-permitted assistant tool.")
    if tool_name == "schema.inspect":
        if not model: raise AssistantToolError("An active approved model is required.")
        table = next((table for table in model.tables if table.name.casefold() == argument.strip().casefold()), None)
        if not table: raise AssistantToolError(f"Unknown table '{argument.strip()}'.")
        relationships = [relationship.model_dump() for relationship in model.relationships if table.name.casefold() in {relationship.source_table.casefold(), relationship.target_table.casefold()}]
        return {"table": table.model_dump(), "relationships": relationships}
    if tool_name == "documents.read_chunk":
        try: chunk_id = int(argument.strip())
        except ValueError as exc: raise AssistantToolError("Chunk ID must be an integer.") from exc
        chunk = db.session.get(DocumentChunk, chunk_id)
        if not chunk or chunk.document.project_id != project.id: raise AssistantToolError("Citation chunk was not found in this project.")
        return {"chunk_id": chunk.id, "document": chunk.document.title, "locator": chunk.locator, "text": chunk.text}
    if not model: raise AssistantToolError("An active approved model is required.")
    try: validation = validate_readonly_sql(argument, model)
    except SQLValidationError as exc: raise AssistantToolError(str(exc)) from exc
    return {"statement": validation.statement, "tables": validation.tables, "columns": validation.columns, "executable": False}
