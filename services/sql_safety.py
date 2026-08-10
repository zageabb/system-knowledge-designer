from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

from sqlglot import exp, parse

from services.er_language.schema import ERModel


class SQLValidationError(ValueError): pass


@dataclass
class ValidatedSQL:
    statement: str
    tables: list[str]
    columns: list[str]


@dataclass
class QueryResult:
    columns: list[str]
    rows: list[list]
    truncated: bool
    runtime_ms: float


FORBIDDEN = (exp.Insert, exp.Update, exp.Delete, exp.Create, exp.Drop, exp.Alter, exp.Command, exp.Merge, exp.Transaction)


def validate_readonly_sql(statement: str, model: ERModel) -> ValidatedSQL:
    try: expressions = parse(statement, read="sqlite")
    except Exception as exc: raise SQLValidationError(f"SQL parse failed: {exc}") from exc
    if len(expressions) != 1 or expressions[0] is None: raise SQLValidationError("Exactly one SQL statement is required.")
    root = expressions[0]
    if not isinstance(root, (exp.Select, exp.Union, exp.Intersect, exp.Except)):
        raise SQLValidationError("Only SELECT statements and read-only CTEs are allowed.")
    if any(root.find(node) is not None for node in FORBIDDEN): raise SQLValidationError("Mutation and administrative SQL are not allowed.")
    known_tables = {t.name.casefold(): t for t in model.tables}
    referenced_tables = sorted({table.name for table in root.find_all(exp.Table)})
    cte_names = {cte.alias.casefold() for cte in root.find_all(exp.CTE)}
    unknown_tables = [name for name in referenced_tables if name.casefold() not in known_tables and name.casefold() not in cte_names]
    if unknown_tables: raise SQLValidationError(f"Unknown table(s): {', '.join(unknown_tables)}.")
    known_columns = {c.name.casefold() for t in model.tables for c in t.columns}
    referenced_columns = sorted({column.name for column in root.find_all(exp.Column) if column.name != "*"})
    unknown_columns = [name for name in referenced_columns if name.casefold() not in known_columns]
    if unknown_columns: raise SQLValidationError(f"Unknown field(s): {', '.join(unknown_columns)}.")
    return ValidatedSQL(statement=statement.strip(), tables=referenced_tables, columns=referenced_columns)


def execute_readonly(validated: ValidatedSQL, sandbox_path: Path, row_limit: int = 500, timeout_seconds: float = 10, allowed_root: Path | None = None) -> QueryResult:
    path = Path(sandbox_path).resolve()
    if allowed_root is not None and not path.is_relative_to(Path(allowed_root).resolve()):
        raise SQLValidationError("Sandbox path is outside the managed application directory.")
    started = time.monotonic(); connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    denied = {sqlite3.SQLITE_INSERT, sqlite3.SQLITE_UPDATE, sqlite3.SQLITE_DELETE, sqlite3.SQLITE_CREATE_TABLE, sqlite3.SQLITE_DROP_TABLE, sqlite3.SQLITE_ALTER_TABLE, sqlite3.SQLITE_ATTACH, sqlite3.SQLITE_DETACH, sqlite3.SQLITE_PRAGMA}
    def authorizer(action, arg1, arg2, database, trigger):
        if action in denied: return sqlite3.SQLITE_DENY
        if action == sqlite3.SQLITE_FUNCTION and str(arg2 or arg1).casefold() in {"load_extension", "writefile", "readfile"}: return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK
    connection.set_authorizer(authorizer)
    connection.set_progress_handler(lambda: 1 if time.monotonic() - started > timeout_seconds else 0, 1000)
    try:
        cursor = connection.execute(validated.statement)
        columns = [item[0] for item in cursor.description or []]
        fetched = cursor.fetchmany(row_limit + 1)
        return QueryResult(columns=columns, rows=[list(row) for row in fetched[:row_limit]], truncated=len(fetched) > row_limit, runtime_ms=(time.monotonic() - started) * 1000)
    finally: connection.close()
