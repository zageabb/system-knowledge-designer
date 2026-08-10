import re
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


def test_many_to_one_chain_renders_parent_to_child_order():
    source = '''erModel Ordering {
 direction LR
 subjectArea Core {
  table PARENT {
   integer id PK
  }
  table CHILD {
   integer id PK
   integer parent_id FK
  }
  table GRANDCHILD {
   integer id PK
   integer child_id FK
  }
  relationship CHILD.parent_id -> PARENT.id {
   cardinality many-to-one
  }
  relationship GRANDCHILD.child_id -> CHILD.id {
   cardinality many-to-one
  }
 }
}'''
    dot = model_to_dot(parse_er_source(source))
    assert "PARENT:id_e:e -> CHILD:parent_id_w:w" in dot
    assert "CHILD:id_e:e -> GRANDCHILD:child_id_w:w" in dot
    svg = render_graphviz_bytes(dot, "svg")
    def left_x(table_name: str) -> float:
        match = re.search(
            rf'<title>{table_name}</title>\s*<polygon[^>]+points="([0-9.-]+),'.encode(),
            svg,
        )
        assert match is not None
        return float(match.group(1))

    parent_x = left_x("PARENT")
    child_x = left_x("CHILD")
    grandchild_x = left_x("GRANDCHILD")
    assert parent_x < child_x < grandchild_x
