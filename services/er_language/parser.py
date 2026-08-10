from __future__ import annotations

import ast
from lark import Lark, Transformer, UnexpectedInput, v_args

from .schema import ERColumn, ERModel, ERRelationship, ERTable

GRAMMAR = r'''
start: "erModel" NAME "{" statement* "}"
?statement: dialect | direction | subject_area | relationship
dialect: "dialect" STRING ";"
direction: "direction" DIRECTION ";"
subject_area: "subjectArea" NAME "{" area_statement* "}"
?area_statement: table | relationship
table: TABLE_KIND NAME "{" column* "}"
column: NAME NAME modifier* ";"
?modifier: marker | attribute
marker: MARKER
attribute: NAME "=" value
relationship: "relationship" reference "->" reference "{" rel_attribute* "}"
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
    def dialect(self, value): return ("dialect", value)
    def direction(self, value): return ("direction", str(value))
    def marker(self, value): return ("marker", str(value))
    def attribute(self, key, value): return ("attribute", str(key), value)
    def column(self, data_type, name, *items):
        markers = [x[1] for x in items if x[0] == "marker"]
        attrs = {x[1]: x[2] for x in items if x[0] == "attribute"}
        return ERColumn(name=str(name), data_type=str(data_type), markers=markers, attributes=attrs)
    def table(self, kind, name, *columns):
        return ("table", str(kind), str(name), list(columns))
    def reference(self, table, column): return (str(table), str(column))
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
        attrs = item[3]
        model.relationships.append(ERRelationship(source_table=item[1][0], source_column=item[1][1], target_table=item[2][0], target_column=item[2][1], cardinality=str(attrs.pop("cardinality", "many-to-one")), label=str(attrs.pop("label", "")), attributes=attrs))


_PARSER = Lark(GRAMMAR, parser="lalr", propagate_positions=True, transformer=_Transformer())


def parse_er_source(source: str) -> ERModel:
    try:
        model = _PARSER.parse(_terminate_lines(source))
    except UnexpectedInput as exc:
        expected = ", ".join(sorted(getattr(exc, "expected", None) or getattr(exc, "allowed", None) or []))
        raise ERParseError(f"Syntax error; expected {expected or 'valid ER syntax'}.", exc.line, exc.column) from exc
    _validate(model)
    return model


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
