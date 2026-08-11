from __future__ import annotations

import ast
from collections.abc import Mapping
from lark import Lark, Transformer, UnexpectedInput, v_args

from .schema import ERColumn, ERModel, ERRelationship, ERTable

GRAMMAR = r'''
start: "erModel" NAME "{" statement* "}"
?statement: dialect | direction | include | subject_area | relationship
dialect: "dialect" STRING ";"
direction: "direction" DIRECTION ";"
include: "include" STRING ";"
subject_area: "subjectArea" NAME "{" area_statement* "}"
?area_statement: table | relationship
table: TABLE_KIND NAME "{" column* "}"
column: NAME NAME modifier* ";"
?modifier: marker | attribute
marker: MARKER
attribute: NAME "=" value
relationship: "relationship" reference_set "->" reference_set "{" rel_attribute* "}"
?reference_set: reference -> single_reference
              | "(" reference ("," reference)* ")" -> composite_reference
reference: NAME "." NAME
rel_attribute: NAME value ";"
?value: STRING -> string
      | SIGNED_NUMBER -> number
      | NAME -> name
TABLE_KIND.3: "table" | "view"
DIRECTION.3: "LR" | "TB"
MARKER.3: "PK" | "FK" | "not_null" | "unique"
NAME: /(?!PK\b|FK\b|not_null\b|unique\b)[A-Za-z_][A-Za-z0-9_-]*/
STRING: ESCAPED_STRING
%import common.ESCAPED_STRING
%import common.SIGNED_NUMBER
%import common.WS
%ignore WS
%ignore /#[^\n]*/
%ignore /\/\/[^\n]*/
'''


class ERParseError(ValueError):
    def __init__(self, message: str, line: int | None = None, column: int | None = None):
        super().__init__(message)
        self.line, self.column = line, column


@v_args(inline=True)
class _Transformer(Transformer):
    def string(self, token): return ast.literal_eval(str(token))
    def number(self, token):
        value = str(token)
        return float(value) if "." in value else int(value)
    def name(self, token): return str(token)
    def dialect(self, value): return ("dialect", ast.literal_eval(str(value)))
    def direction(self, value): return ("direction", str(value))
    def include(self, value): return ("include", ast.literal_eval(str(value)))
    def marker(self, value): return ("marker", str(value))
    def attribute(self, key, value): return ("attribute", str(key), value)
    def column(self, data_type, name, *items):
        markers = [x[1] for x in items if x[0] == "marker"]
        attrs = {x[1]: x[2] for x in items if x[0] == "attribute"}
        description = str(attrs.pop("description", ""))
        return ERColumn(name=str(name), data_type=str(data_type), description=description, markers=markers, attributes=attrs)
    def table(self, kind, name, *columns):
        return ("table", str(kind), str(name), list(columns))
    def reference(self, table, column): return (str(table), str(column))
    def single_reference(self, reference): return [reference]
    def composite_reference(self, *references): return list(references)
    def rel_attribute(self, key, value): return (str(key), value)
    def relationship(self, source, target, *attributes):
        attrs = dict(attributes)
        return ("relationship", source, target, attrs)
    def subject_area(self, name, *items): return ("area", str(name), list(items))
    def start(self, name, *statements):
        model = ERModel(name=str(name))
        for statement in statements:
            if statement[0] == "dialect": model.dialect = statement[1]
            elif statement[0] == "direction": model.direction = statement[1]
            elif statement[0] == "include": model.includes.append(statement[1])
            elif statement[0] == "relationship": self._add_relationship(model, statement)
            elif statement[0] == "area":
                area = statement[1]
                for item in statement[2]:
                    if item[0] == "table":
                        model.tables.append(ERTable(name=item[2], kind=item[1], subject_area=area, columns=item[3]))
                    elif item[0] == "relationship": self._add_relationship(model, item)
        return model
    @staticmethod
    def _add_relationship(model, item):
        sources, targets, authored_attrs = item[1], item[2], item[3]
        if len(sources) != len(targets):
            raise ERParseError("Composite relationship source and target must contain the same number of fields.")
        attrs = dict(authored_attrs)
        cardinality = str(attrs.pop("cardinality", "many-to-one")); label = str(attrs.pop("label", ""))
        composite_group = "|".join(f"{table}.{column}" for table, column in sources + targets) if len(sources) > 1 else None
        for position, (source, target) in enumerate(zip(sources, targets), start=1):
            pair_attrs = dict(attrs)
            if composite_group:
                pair_attrs.update({"composite_group": composite_group, "composite_position": position, "composite_size": len(sources)})
            model.relationships.append(ERRelationship(source_table=source[0], source_column=source[1], target_table=target[0], target_column=target[1], cardinality=cardinality, label=label, attributes=pair_attrs))


_PARSER = Lark(GRAMMAR, parser="lalr", propagate_positions=True, transformer=_Transformer())


def parse_er_source(source: str, *, includes: Mapping[str, str] | None = None) -> ERModel:
    model = _parse_unvalidated(source)
    if model.includes:
        if includes is None:
            raise ERParseError("This model uses managed includes, but no project include catalogue was supplied.")
        model = _resolve_includes(model, includes)
    _validate(model)
    return model


def _parse_unvalidated(source: str) -> ERModel:
    try:
        return _PARSER.parse(_terminate_lines(source))
    except UnexpectedInput as exc:
        expected = ", ".join(sorted(getattr(exc, "expected", None) or getattr(exc, "allowed", None) or []))
        raise ERParseError(f"Syntax error; expected {expected or 'valid ER syntax'}.", exc.line, exc.column) from exc


def _resolve_includes(root: ERModel, catalogue: Mapping[str, str]) -> ERModel:
    normalized = {_include_key(name): source for name, source in catalogue.items()}
    resolved_tables, resolved_relationships = [], []
    expanded_count = 0

    def visit(name: str, chain: tuple[str, ...]) -> None:
        nonlocal expanded_count
        key = _include_key(name)
        if key in chain:
            cycle = " -> ".join((*chain, key))
            raise ERParseError(f"Managed include cycle detected: {cycle}.")
        source = normalized.get(key)
        if source is None:
            raise ERParseError(f"Managed include '{name}' does not exist in this project.")
        if len(chain) >= 8:
            raise ERParseError("Managed includes exceed the maximum nesting depth of 8.")
        expanded_count += 1
        if expanded_count > 20:
            raise ERParseError("A model may expand at most 20 managed includes.")
        included = _parse_unvalidated(source)
        for nested in included.includes:
            visit(nested, (*chain, key))
        resolved_tables.extend(included.tables)
        resolved_relationships.extend(included.relationships)

    for include_name in root.includes:
        visit(include_name, ())
    root.tables = resolved_tables + root.tables
    root.relationships = resolved_relationships + root.relationships
    return root


def _include_key(value: str) -> str:
    key = " ".join(value.casefold().split())
    if not key or len(key) > 160:
        raise ERParseError("Managed include names must contain 1 to 160 characters.")
    return key


def _terminate_lines(source: str) -> str:
    """Make the documented newline-oriented syntax explicit for the grammar."""
    output = []
    for line in source.splitlines():
        stripped = line.strip()
        if stripped and not stripped.endswith(("{", "}", ";")) and not stripped.startswith(("#", "//")):
            line += ";"
        output.append(line)
    return "\n".join(output)


def _validate(model: ERModel) -> None:
    tables = {}
    for table in model.tables:
        key = table.name.casefold()
        if key in tables: raise ERParseError(f"Duplicate table '{table.name}'. Rename or remove one definition.")
        tables[key] = table
        seen = set()
        for column in table.columns:
            col_key = column.name.casefold()
            if col_key in seen: raise ERParseError(f"Duplicate field '{table.name}.{column.name}'.")
            seen.add(col_key)
    for rel in model.relationships:
        for table_name, column_name in ((rel.source_table, rel.source_column), (rel.target_table, rel.target_column)):
            table = tables.get(table_name.casefold())
            if not table: raise ERParseError(f"Relationship references missing table '{table_name}'.")
            if column_name.casefold() not in {c.name.casefold() for c in table.columns}:
                raise ERParseError(f"Relationship references missing field '{table_name}.{column_name}'.")
