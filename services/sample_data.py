from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from services.er_language.schema import ERColumn, ERModel


class SampleValidationError(ValueError):
    pass


def validate_row(model: ERModel, table_name: str, values: dict) -> dict:
    table = next((t for t in model.tables if t.name.casefold() == table_name.casefold()), None)
    if table is None: raise SampleValidationError(f"Unknown table '{table_name}'.")
    columns = {c.name.casefold(): c for c in table.columns}
    unknown = sorted(set(k.casefold() for k in values) - set(columns))
    if unknown: raise SampleValidationError(f"Unknown field(s) for {table.name}: {', '.join(unknown)}.")
    normalised = {}
    for column in table.columns:
        value = next((v for k, v in values.items() if k.casefold() == column.name.casefold()), None)
        if value is None and not column.nullable:
            raise SampleValidationError(f"{table.name}.{column.name} cannot be null.")
        normalised[column.name] = _coerce(column, value)
    return normalised


def validate_dataset_relationships(model: ERModel, rows_by_table: dict[str, list[dict]]) -> None:
    """Reject dangling non-null references across a complete sample dataset."""
    canonical = {name.casefold(): rows for name, rows in rows_by_table.items()}
    for relationship in model.relationships:
        target_values = {
            _casefold_get(row, relationship.target_column)
            for row in canonical.get(relationship.target_table.casefold(), [])
            if _casefold_get(row, relationship.target_column) is not None
        }
        for position, row in enumerate(canonical.get(relationship.source_table.casefold(), []), 1):
            value = _casefold_get(row, relationship.source_column)
            if value is not None and value not in target_values:
                raise SampleValidationError(
                    f"{relationship.source_table} row {position} has {relationship.source_column}={value!r}, "
                    f"but no {relationship.target_table}.{relationship.target_column} has that value."
                )


def _casefold_get(row: dict, field_name: str):
    return next((value for key, value in row.items() if key.casefold() == field_name.casefold()), None)


def _coerce(column: ERColumn, value):
    if value is None: return None
    kind = column.data_type.casefold()
    try:
        if kind in {"integer", "int", "bigint", "smallint"}: return int(value)
        if kind in {"decimal", "numeric", "real", "float", "double"}: return float(Decimal(str(value)))
        if kind in {"boolean", "bool"}:
            if isinstance(value, bool): return int(value)
            if str(value).casefold() in {"true", "1", "yes"}: return 1
            if str(value).casefold() in {"false", "0", "no"}: return 0
            raise ValueError
        if kind == "date": return date.fromisoformat(str(value)).isoformat()
        if kind in {"datetime", "timestamp"}: return datetime.fromisoformat(str(value)).isoformat()
    except (ValueError, TypeError, InvalidOperation) as exc:
        raise SampleValidationError(f"Value {value!r} is incompatible with {column.name} ({column.data_type}).") from exc
    text = str(value)
    length = column.attributes.get("length")
    if length and len(text) > int(length): raise SampleValidationError(f"{column.name} exceeds length {length}.")
    return text
