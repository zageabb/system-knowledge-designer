from __future__ import annotations

import html
import re
import subprocess
from pathlib import Path

from services.er_language.schema import ERModel


def _ident(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]", "_", value)


def model_to_dot(model: ERModel, highlights: set[str] | None = None) -> str:
    highlights = {x.casefold() for x in (highlights or set())}
    lines = ["digraph ER {", f"rankdir={model.direction};", 'graph [bgcolor="transparent", pad="0.3", nodesep="0.45", ranksep="0.8"];', 'node [shape=plain fontname="Arial"];', 'edge [fontname="Arial" fontsize=9 color="#64748b"];']
    areas: dict[str, list] = {}
    for table in model.tables: areas.setdefault(table.subject_area, []).append(table)
    for area, tables in areas.items():
        lines += [f"subgraph cluster_{_ident(area)} {{", f'label="{html.escape(area)}";', 'color="#cbd5e1"; style="rounded";']
        for table in tables:
            table_highlighted = table.name.casefold() in highlights
            fill = "#fef3c7" if table_highlighted else "#e0f2fe"
            rows = [f'<TR><TD COLSPAN="4" BGCOLOR="{fill}"><B>{html.escape(table.name)}</B></TD></TR>']
            for column in table.columns:
                marker = "PK" if "PK" in column.markers else "FK" if "FK" in column.markers else ""
                port = _ident(column.name)
                column_key = f"{table.name}.{column.name}".casefold()
                row_fill = ' BGCOLOR="#fde68a"' if column_key in highlights else ""
                description = html.escape(column.description) or "&#160;"
                rows.append(
                    f'<TR><TD PORT="{port}_w"{row_fill}>{marker}</TD>'
                    f'<TD ALIGN="LEFT"{row_fill}>{html.escape(column.name)}</TD>'
                    f'<TD PORT="{port}_e" ALIGN="LEFT"{row_fill}><FONT COLOR="#64748b">'
                    f'{html.escape(column.data_type)}</FONT></TD>'
                    f'<TD ALIGN="LEFT"{row_fill}><FONT COLOR="#475569">{description}</FONT></TD></TR>'
                )
            label = '<<TABLE BORDER="1" CELLBORDER="0" CELLSPACING="0" CELLPADDING="5">' + "".join(rows) + "</TABLE>>"
            lines.append(f'{_ident(table.name)} [id="table-{_ident(table.name)}" label={label}];')
        lines.append("}")
    for rel in model.relationships:
        attrs = [f'label="{html.escape(rel.label)}"'] if rel.label else []
        if rel.cardinality.casefold() == "many-to-one":
            # Lay referenced parents before dependent children so LR diagrams
            # read from the one side to the many side. The crow's-foot remains
            # visual cardinality; the tooltip states the actual FK direction.
            attrs.extend([
                'dir="both"',
                'arrowtail="tee"',
                'arrowhead="crow"',
                f'tooltip="one-to-many; FK {html.escape(rel.source_table)}.{html.escape(rel.source_column)} references {html.escape(rel.target_table)}.{html.escape(rel.target_column)}"',
            ])
            left_table, left_column = rel.target_table, rel.target_column
            right_table, right_column = rel.source_table, rel.source_column
        else:
            attrs.append(f'tooltip="{html.escape(rel.cardinality)}"')
            left_table, left_column = rel.source_table, rel.source_column
            right_table, right_column = rel.target_table, rel.target_column
        lines.append(
            f'{_ident(left_table)}:{_ident(left_column)}_e:e -> '
            f'{_ident(right_table)}:{_ident(right_column)}_w:w '
            f'[{" ".join(attrs)}];'
        )
    lines.append("}")
    return "\n".join(lines)


def render_graphviz(dot_source: str, output: Path, format_name: str = "svg", scale: int = 1) -> Path:
    if format_name not in {"svg", "png"}: raise ValueError("Only SVG and PNG are supported.")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(render_graphviz_bytes(dot_source, format_name, scale))
    return output


def render_graphviz_bytes(dot_source: str, format_name: str = "svg", scale: int = 1) -> bytes:
    if format_name not in {"svg", "png"}: raise ValueError("Only SVG and PNG are supported.")
    command = ["dot", f"-T{format_name}"]
    if format_name == "png": command += [f"-Gdpi={96 * scale}"]
    result = subprocess.run(command, input=dot_source.encode(), capture_output=True, timeout=30, check=False)
    if result.returncode != 0: raise RuntimeError(result.stderr.decode(errors="replace") or "Graphviz rendering failed.")
    return result.stdout
