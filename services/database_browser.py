from __future__ import annotations

from datetime import datetime, timezone
from typing import Mapping

from sqlalchemy import Boolean, DateTime, Float, Integer, select, update
from sqlalchemy.sql.schema import Column, Table

from database import db


class DatabaseBrowserError(ValueError):
    pass


PROTECTED_COLUMNS = {"id", "password_hash", "created_at", "updated_at"}
READ_ONLY_TABLES = {"audit_event"}


def available_tables() -> list[Table]:
    return sorted(db.metadata.tables.values(), key=lambda table: table.name)


def resolve_table(name: str) -> Table:
    table = db.metadata.tables.get(name)
    if table is None:
        raise DatabaseBrowserError("Unknown database table.")
    return table


def primary_key_column(table: Table) -> Column:
    columns = list(table.primary_key.columns)
    if len(columns) != 1:
        raise DatabaseBrowserError("This table does not have one editable primary key.")
    return columns[0]


def editable_columns(table: Table) -> list[Column]:
    if table.name in READ_ONLY_TABLES:
        return []
    return [
        column
        for column in table.columns
        if column.name not in PROTECTED_COLUMNS and not column.foreign_keys and not column.primary_key
    ]


def read_page(table: Table, page: int, page_size: int = 50) -> tuple[list[Mapping], int]:
    primary_key = primary_key_column(table)
    page = max(page, 1)
    total = db.session.query(table).count()
    rows = db.session.execute(
        select(table).order_by(primary_key).limit(page_size).offset((page - 1) * page_size)
    ).mappings().all()
    return rows, total


def update_record(table: Table, raw_primary_key: str, values: Mapping[str, str]) -> tuple[object, list[str]]:
    primary_key = primary_key_column(table)
    record_id = _coerce(primary_key, raw_primary_key)
    allowed = {column.name: column for column in editable_columns(table)}
    changes = {}
    for name, column in allowed.items():
        if name in values:
            changes[name] = _coerce(column, values[name])
    if not changes:
        raise DatabaseBrowserError("No editable values were submitted.")
    if "updated_at" in table.c:
        changes["updated_at"] = datetime.now(timezone.utc)
    result = db.session.execute(update(table).where(primary_key == record_id).values(**changes))
    if result.rowcount != 1:
        raise DatabaseBrowserError("The selected record no longer exists.")
    return record_id, sorted(name for name in changes if name != "updated_at")


def _coerce(column: Column, raw_value: str):
    value = raw_value.strip()
    if value == "":
        if column.nullable:
            return None
        if isinstance(column.type, (Integer, Float, Boolean, DateTime)):
            raise DatabaseBrowserError(f"{column.name} cannot be empty.")
        return ""
    try:
        if isinstance(column.type, Boolean):
            normalized = value.casefold()
            if normalized not in {"true", "false", "1", "0", "yes", "no", "on", "off"}:
                raise ValueError
            return normalized in {"true", "1", "yes", "on"}
        if isinstance(column.type, Integer):
            return int(value)
        if isinstance(column.type, Float):
            return float(value)
        if isinstance(column.type, DateTime):
            return datetime.fromisoformat(value)
    except ValueError as exc:
        raise DatabaseBrowserError(f"{column.name} has an invalid {column.type} value.") from exc
    return raw_value[: column.type.length] if getattr(column.type, "length", None) else raw_value
