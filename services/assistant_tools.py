from __future__ import annotations

import json
from pathlib import Path

from database import db
from models import DocumentChunk, SandboxBuild
from services.sql_safety import SQLValidationError, execute_readonly, validate_readonly_sql


class AssistantToolError(ValueError): pass


READ_TOOLS = {
    "schema.inspect": "Inspect one table in the active authoritative model",
    "documents.read_chunk": "Read one project-scoped citation chunk",
    "sql.validate": "Validate one read-only statement without executing it",
    "sql.query": "Execute one validated read-only SQL statement against the current managed sandbox",
    "samples.aggregate": "Run a typed count, sum, average, minimum or maximum against one sandbox table",
}


def execute_read_tool(*, tool_name: str, argument: str, project, model, allowed_root: Path | None = None) -> dict:
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
    if tool_name in {"sql.query", "samples.aggregate"}:
        build = SandboxBuild.query.filter_by(project_id=project.id, revision_id=project.active_revision_id, status="completed").order_by(SandboxBuild.id.desc()).first()
        if not build: raise AssistantToolError("Build a completed sandbox from the current active revision before running Assistant data queries.")
        if allowed_root is None: raise AssistantToolError("The managed sandbox root is not configured for Assistant execution.")
        statement = argument
        if tool_name == "samples.aggregate":
            statement = _aggregate_statement(argument, model)
        try:
            validation = validate_readonly_sql(statement, model)
            query_result = execute_readonly(validation, Path(build.managed_path), row_limit=100, timeout_seconds=5, allowed_root=allowed_root)
        except (SQLValidationError, ValueError) as exc:
            raise AssistantToolError(str(exc)) from exc
        return {
            "statement": validation.statement, "tables": validation.tables, "columns": validation.columns,
            "result_columns": query_result.columns, "rows": query_result.rows, "row_count": len(query_result.rows),
            "truncated": query_result.truncated, "runtime_ms": query_result.runtime_ms,
            "sandbox_build_id": build.id, "model_revision_id": build.revision_id,
        }
    try: validation = validate_readonly_sql(argument, model)
    except SQLValidationError as exc: raise AssistantToolError(str(exc)) from exc
    return {"statement": validation.statement, "tables": validation.tables, "columns": validation.columns, "executable": False}


def _aggregate_statement(argument: str, model) -> str:
    try: request = json.loads(argument)
    except json.JSONDecodeError as exc: raise AssistantToolError("Aggregation argument must be JSON.") from exc
    operation = str(request.get("operation", "")).casefold()
    functions = {"count": "COUNT", "sum": "SUM", "average": "AVG", "minimum": "MIN", "maximum": "MAX"}
    if operation not in functions: raise AssistantToolError("Aggregation operation must be count, sum, average, minimum or maximum.")
    table = next((item for item in model.tables if item.name.casefold() == str(request.get("table", "")).casefold()), None)
    if not table: raise AssistantToolError("Aggregation table is not in the active model.")
    column_name = str(request.get("column", "*")).strip()
    column = next((item for item in table.columns if item.name.casefold() == column_name.casefold()), None) if column_name != "*" else None
    if column_name == "*" and operation != "count": raise AssistantToolError("Only count may use '*' as its column.")
    if column_name != "*" and column is None: raise AssistantToolError("Aggregation column is not in the selected table.")
    if operation in {"sum", "average"} and column.data_type.casefold() not in {"integer", "int", "bigint", "smallint", "decimal", "numeric", "real", "float", "double"}:
        raise AssistantToolError("Sum and average require a numeric column.")
    group_name = str(request.get("group_by", "")).strip()
    group = next((item for item in table.columns if item.name.casefold() == group_name.casefold()), None) if group_name else None
    if group_name and group is None: raise AssistantToolError("Aggregation group_by field is not in the selected table.")
    quote = lambda value: '"' + value.replace('"', '""') + '"'
    target = "*" if column_name == "*" else quote(column.name)
    aggregate = f"{functions[operation]}({target}) AS value"
    if group:
        return f"SELECT {quote(group.name)} AS group_value, {aggregate} FROM {quote(table.name)} GROUP BY {quote(group.name)} ORDER BY {quote(group.name)}"
    return f"SELECT {aggregate} FROM {quote(table.name)}"
