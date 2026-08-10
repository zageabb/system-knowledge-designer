from __future__ import annotations

import json
from pydantic import BaseModel, Field, ValidationError

from services.er_language.schema import ERModel
from services.ollama import OllamaClient
from services.sql_safety import SQLValidationError, validate_readonly_sql


class SQLProposal(BaseModel):
    statement: str = Field(min_length=1, max_length=12000)
    explanation: str = Field(default="", max_length=4000)
    assumptions: list[str] = Field(default_factory=list, max_length=12)


class SQLProposalError(ValueError): pass


def generate_sql_proposal(*, question: str, model: ERModel, ollama_url: str, ollama_model: str, client=None) -> SQLProposal:
    schema = [{"table": table.name, "columns": [{"name": column.name, "type": column.data_type, "markers": column.markers} for column in table.columns]} for table in model.tables]
    relationships = [relationship.model_dump() for relationship in model.relationships]
    prompt = f"""Generate one read-only SQL query for the user's question using only this authoritative schema.
Return JSON only: {{"statement":"SELECT ...", "explanation":"...", "assumptions":["..."]}}.
Never emit INSERT, UPDATE, DELETE, DDL, PRAGMA, ATTACH, multiple statements, comments that hide SQL, or filesystem/database paths.
Dialect: {model.dialect}
Schema: {json.dumps(schema, sort_keys=True)}
Relationships: {json.dumps(relationships, sort_keys=True)}
Question: {question[:1000]}
"""
    raw = (client or OllamaClient(ollama_url)).generate_json(ollama_model, prompt)
    try: proposal = SQLProposal.model_validate(raw)
    except ValidationError as exc: raise SQLProposalError(f"SQL proposal has the wrong structure: {exc}") from exc
    try: validation = validate_readonly_sql(proposal.statement, model)
    except SQLValidationError as exc: raise SQLProposalError(f"Generated SQL failed deterministic validation: {exc}") from exc
    proposal.statement = validation.statement
    return proposal
