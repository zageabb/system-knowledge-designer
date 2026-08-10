import pytest
import struct
from services.er_language import ERParseError, parse_er_source
from services.graph_renderer import model_to_dot, render_graphviz

SOURCE = '''erModel Procurement {
 dialect "sqlite"
 direction LR
 subjectArea Buying {
  table SUPPLIER {
   integer supplier_id PK
   string name length=200 not_null
  }
  table PO {
   integer po_id PK
   integer supplier_id FK not_null
  }
  relationship PO.supplier_id -> SUPPLIER.supplier_id {
   cardinality many-to-one
   label "placed with"
  }
 }
}'''

def test_parse_valid_model_to_typed_ir():
    model = parse_er_source(SOURCE)
    assert model.name == "Procurement" and len(model.tables) == 2
    assert model.tables[0].columns[1].attributes == {"length": 200}
    assert model.relationships[0].label == "placed with"

def test_dot_connects_exact_field_ports():
    dot = model_to_dot(parse_er_source(SOURCE))
    assert "PO:supplier_id_e:e -> SUPPLIER:supplier_id_w:w" in dot
    assert 'PORT="supplier_id_w"' in dot
    assert 'PORT="supplier_id_e"' in dot

def test_top_to_bottom_edges_still_use_external_table_boundaries():
    model = parse_er_source(SOURCE.replace("direction LR", "direction TB"))
    assert "PO:supplier_id_e:e -> SUPPLIER:supplier_id_w:w" in model_to_dot(model)

@pytest.mark.parametrize("bad, message", [
 (SOURCE.replace("table PO", "table SUPPLIER"), "Duplicate table"),
 (SOURCE.replace("SUPPLIER.supplier_id {", "SUPPLIER.missing {"), "missing field"),
])
def test_semantic_errors_are_actionable(bad, message):
    with pytest.raises(ERParseError, match=message): parse_er_source(bad)

def test_syntax_error_has_location():
    with pytest.raises(ERParseError) as caught: parse_er_source("erModel X { subjectArea Core { table T { integer } } }")
    assert caught.value.line == 1 and caught.value.column

def test_graphviz_exports_valid_svg_and_scaled_png(tmp_path):
    dot = model_to_dot(parse_er_source(SOURCE))
    svg = render_graphviz(dot, tmp_path / "model.svg", "svg")
    png1 = render_graphviz(dot, tmp_path / "model-1x.png", "png", 1)
    png4 = render_graphviz(dot, tmp_path / "model-4x.png", "png", 4)
    assert b"<svg" in svg.read_bytes()
    assert png1.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    width1, height1 = struct.unpack(">II", png1.read_bytes()[16:24])
    width4, height4 = struct.unpack(">II", png4.read_bytes()[16:24])
    assert width4 >= width1 * 3.9 and height4 >= height1 * 3.9


def test_graph_renderer_highlights_referenced_table_and_field():
    dot = model_to_dot(parse_er_source(SOURCE), {"SUPPLIER", "SUPPLIER.name"})
    assert 'BGCOLOR="#fef3c7"' in dot
    assert dot.count('BGCOLOR="#fde68a"') == 3
