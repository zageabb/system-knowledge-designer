import time

import pytest

from services.er_language import parse_er_source
from services.graph_renderer import model_to_dot, render_graphviz_bytes


def generated_model(table_count: int) -> str:
    tables = []
    for index in range(table_count):
        tables.append(f"table T_{index} {{\n integer id PK\n string display_name length=120 not_null\n }}")
    return "erModel Scale {\n direction LR\n subjectArea Core {\n" + "\n".join(tables) + "\n}\n}"


@pytest.mark.parametrize("table_count", [10, 50, 100])
def test_parse_and_svg_render_scale_profile(table_count):
    started = time.perf_counter()
    model = parse_er_source(generated_model(table_count))
    dot = model_to_dot(model)
    svg = render_graphviz_bytes(dot, "svg")
    elapsed = time.perf_counter() - started
    assert len(model.tables) == table_count
    assert svg.startswith(b"<?xml") and b"<svg" in svg
    assert elapsed < 15
