from __future__ import annotations

import json
import re
from collections.abc import Mapping

from services.er_language import parse_er_source
from services.er_language.schema import ERColumn, ERModel, ERRelationship, ERTable


class CatalogueEditError(ValueError):
    pass


_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]*$")


def edit_catalogue(model: ERModel, action: str, values: Mapping[str, str]) -> tuple[ERModel, str]:
    """Apply one catalogue form operation and return a fully revalidated model/source pair."""
    edited = model.model_copy(deep=True)
    if action == "add_table":
        name = _identifier(values.get("name", ""), "Table name")
        if _table(edited, name, required=False):
            raise CatalogueEditError(f"Table '{name}' already exists.")
        edited.tables.append(ERTable(name=name, kind=_kind(values.get("kind", "table")), subject_area=_identifier(values.get("subject_area", "Core"), "Subject area")))
    elif action == "update_table":
        table = _table(edited, values.get("original_table", ""))
        old_name = table.name; new_name = _identifier(values.get("name", ""), "Table name")
        duplicate = _table(edited, new_name, required=False)
        if duplicate is not None and duplicate is not table:
            raise CatalogueEditError(f"Table '{new_name}' already exists.")
        table.name = new_name; table.kind = _kind(values.get("kind", "table")); table.subject_area = _identifier(values.get("subject_area", "Core"), "Subject area")
        for relationship in edited.relationships:
            if relationship.source_table.casefold() == old_name.casefold(): relationship.source_table = new_name
            if relationship.target_table.casefold() == old_name.casefold(): relationship.target_table = new_name
    elif action == "add_column":
        table = _table(edited, values.get("table", "")); name = _identifier(values.get("name", ""), "Field name")
        if _column(table, name, required=False): raise CatalogueEditError(f"Field '{table.name}.{name}' already exists.")
        table.columns.append(ERColumn(name=name, data_type=_identifier(values.get("data_type", "string"), "Data type"), description=_description(values), markers=_markers(values)))
    elif action == "update_column":
        table = _table(edited, values.get("table", "")); column = _column(table, values.get("original_column", ""))
        old_name = column.name; new_name = _identifier(values.get("name", ""), "Field name")
        duplicate = _column(table, new_name, required=False)
        if duplicate is not None and duplicate is not column: raise CatalogueEditError(f"Field '{table.name}.{new_name}' already exists.")
        column.name = new_name; column.data_type = _identifier(values.get("data_type", ""), "Data type"); column.description = _description(values); column.markers = _markers(values)
        for relationship in edited.relationships:
            if relationship.source_table.casefold() == table.name.casefold() and relationship.source_column.casefold() == old_name.casefold(): relationship.source_column = new_name
            if relationship.target_table.casefold() == table.name.casefold() and relationship.target_column.casefold() == old_name.casefold(): relationship.target_column = new_name
    elif action in {"add_relationship", "update_relationship"}:
        relationship = ERRelationship(
            source_table=_identifier(values.get("many_table", ""), "Many table"),
            source_column=_identifier(values.get("many_column", ""), "Many field"),
            target_table=_identifier(values.get("one_table", ""), "One table"),
            target_column=_identifier(values.get("one_column", ""), "One field"),
            cardinality="many-to-one",
            label=values.get("label", "").strip()[:200],
        )
        many_table = _table(edited, relationship.source_table); many_column = _column(many_table, relationship.source_column)
        _column(_table(edited, relationship.target_table), relationship.target_column)
        if "FK" not in many_column.markers: many_column.markers.append("FK")
        if action == "add_relationship": edited.relationships.append(relationship)
        else:
            index = next((position for position, existing in enumerate(edited.relationships) if (
                existing.source_table.casefold(), existing.source_column.casefold(), existing.target_table.casefold(), existing.target_column.casefold()
            ) == (
                values.get("original_many_table", "").casefold(), values.get("original_many_column", "").casefold(), values.get("original_one_table", "").casefold(), values.get("original_one_column", "").casefold()
            )), -1)
            if index < 0: raise CatalogueEditError("Relationship selection is invalid.")
            edited.relationships[index] = relationship
    else:
        raise CatalogueEditError("Unknown catalogue edit action.")

    source = model_to_er_source(edited)
    try:
        return parse_er_source(source), source
    except ValueError as exc:
        raise CatalogueEditError(str(exc)) from exc


def model_to_er_source(model: ERModel) -> str:
    lines = [f"erModel {model.name} {{", f"  dialect {json.dumps(model.dialect)};", f"  direction {model.direction};"]
    areas: dict[str, list[ERTable]] = {}
    for table in model.tables: areas.setdefault(table.subject_area, []).append(table)
    for area, tables in areas.items():
        lines.append(f"  subjectArea {area} {{")
        for table in tables:
            lines.append(f"    {table.kind} {table.name} {{")
            for column in table.columns:
                suffix = "".join(f" {marker}" for marker in column.markers)
                suffix += "".join(f" {key}={_value(value)}" for key, value in column.attributes.items())
                suffix += f" description={json.dumps(column.description)}"
                lines.append(f"      {column.data_type} {column.name}{suffix};")
            lines.append("    }")
        lines.append("  }")
    for relationship in model.relationships:
        lines.extend((
            f"  relationship {relationship.source_table}.{relationship.source_column} -> {relationship.target_table}.{relationship.target_column} {{",
            "    cardinality many-to-one;",
            *( [f"    label {json.dumps(relationship.label)};"] if relationship.label else [] ),
        ))
        for key, value in relationship.attributes.items():
            if not key.startswith("composite_"): lines.append(f"    {key} {_value(value)};")
        lines.append("  }")
    lines.append("}")
    return "\n".join(lines) + "\n"


def _identifier(value: str, label: str) -> str:
    value = value.strip()
    if not _IDENTIFIER.fullmatch(value): raise CatalogueEditError(f"{label} must start with a letter or underscore and contain only letters, numbers, underscores or hyphens.")
    return value


def _kind(value: str) -> str:
    if value not in {"table", "view"}: raise CatalogueEditError("Kind must be table or view.")
    return value


def _markers(values: Mapping[str, str]) -> list[str]:
    return [marker for marker, field in (("PK", "primary_key"), ("FK", "foreign_key"), ("not_null", "not_null"), ("unique", "unique")) if values.get(field)]


def _description(values: Mapping[str, str]) -> str:
    return values.get("description", "").strip()[:2000]


def _table(model: ERModel, name: str, *, required: bool = True) -> ERTable | None:
    result = next((table for table in model.tables if table.name.casefold() == name.strip().casefold()), None)
    if required and result is None: raise CatalogueEditError(f"Table '{name}' does not exist.")
    return result


def _column(table: ERTable, name: str, *, required: bool = True) -> ERColumn | None:
    result = next((column for column in table.columns if column.name.casefold() == name.strip().casefold()), None)
    if required and result is None: raise CatalogueEditError(f"Field '{table.name}.{name}' does not exist.")
    return result


def _value(value: object) -> str:
    return json.dumps(value) if isinstance(value, str) else str(value).lower() if isinstance(value, bool) else str(value)
