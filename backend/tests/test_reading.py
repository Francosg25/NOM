"""A reading layout must preserve technical values and never execute source HTML."""

import json

from app.reading import inline_text, official_image, reading_tree


def all_text(items):
    parts = []
    for block in items:
        if block["type"] in {"paragraph", "heading"}:
            parts.append(inline_text(block["inlines"]))
        elif block["type"] == "table":
            parts.extend(all_text(cell["blocks"]) for row in block["rows"] for cell in row["cells"])
        elif block["type"] == "list":
            parts.extend(all_text(item) for item in block["items"])
    return "\n".join(parts)


def test_sidof_inline_fragments_rejoin_words_without_changing_numbers_or_definitions():
    html = """<html><head><title>Duplicate title</title></head><body>
      <h1>NOM controlada</h1><div>
      <p>Que en México la regulaci<span>ó</span>n existente conserva $3 000 millones y 5 800 unidades.</p>
      <div class="Texto"><b>3.5.</b><b> </b><span>Cemento portland compuesto (CPC)</span></div>
      <p>Definición con resistencia de 40 N/mm<span style="vertical-align:super">2</span> y H<sub>2</sub>O.</p>
      </div></body></html>"""
    raw = json.dumps({"Nota": {"cadenaContenido": html}}, ensure_ascii=False).encode()
    result = reading_tree(raw, "application/json", "regulaci\nó\nn", "NOM controlada")
    assert result["format"] == "structured"
    text = all_text(result["blocks"])
    assert "regulación existente" in text and "regulaci\nó\nn" not in text
    assert "$3 000 millones y 5 800 unidades" in text
    assert "40 N/mm2 y H2O" in text
    assert "NOM controlada" not in text
    assert result["blocks"][1]["type"] == "heading"
    assert inline_text(result["blocks"][1]["inlines"]) == "3.5. Cemento portland compuesto (CPC)"
    assert any(node["type"] == "sup" for node in result["blocks"][2]["inlines"])


def test_legacy_json_with_html_media_type_or_charset_still_gets_a_structured_reading():
    raw = json.dumps({"Nota": {"cadenaContenido": "<p>Regulaci<span>ó</span>n conservada.</p>"}}).encode()
    for media in ["text/html", "text/plain", "application/json;charset=UTF-8"]:
        result = reading_tree(raw, media, "Regulaci\nó\nn conservada.")
        assert result["format"] == "structured"
        assert inline_text(result["blocks"][0]["inlines"]) == "Regulación conservada."


def test_tables_preserve_rows_cells_spans_units_and_lists():
    html = """<main><table><tr><th rowspan="2">Clase resistente</th><th colspan="2">N/mm<sup>2</sup></th></tr>
      <tr><td>Mínimo</td><td>Máximo</td></tr><tr><td>30 R</td><td>30</td><td>50</td></tr></table>
      <ol start="3"><li>Requisito A.</li><li>Requisito B.<ul><li>Muestra de 2 kg.</li></ul></li></ol></main>"""
    result = reading_tree(html.encode(), "text/html", "fallback")
    table, items = result["blocks"]
    assert table["type"] == "table" and len(table["rows"]) == 3
    assert table["rows"][0]["cells"][0]["row_span"] == 2
    assert table["rows"][0]["cells"][1]["col_span"] == 2
    assert table["rows"][0]["cells"][0]["header"] is True
    assert all_text(table["rows"][2]["cells"][0]["blocks"]) == "30 R"
    assert items["type"] == "list" and items["ordered"] and items["start"] == 3
    assert "Muestra de 2 kg." in all_text(result["blocks"])


def test_scripts_events_and_source_css_cannot_enter_the_reading_tree():
    html = """<body><script>script-payload</script><iframe>frame-payload</iframe>
      <p class="evil" style="position:fixed" onclick="event-payload">Texto conservado.
      <a href="javascript:alert(1)">Enlace conservado como texto.</a>
      <img src="https://evil.example/tracker.png" onerror="image-payload"></p></body>"""
    result = reading_tree(html.encode(), "text/html", "fallback")
    encoded = json.dumps(result)
    assert "Texto conservado" in encoded and "Enlace conservado" in encoded
    assert not any(
        value in encoded
        for value in [
            "script-payload",
            "frame-payload",
            "event-payload",
            "image-payload",
            "javascript",
            "position:fixed",
            "evil.example",
        ]
    )
    assert result["blocks"][0]["inlines"][-1]["src"] is None


def test_saved_diary_figures_use_only_raster_images_on_the_production_host():
    path = "/imagenes_diarios/2026/11/02/MAT/seeco_1_Cimg_8562.png"
    assert official_image("https://sidofqa.segob.gob.mx" + path) == "https://sidof.segob.gob.mx" + path
    for url in [
        "javascript:alert(1)",
        "https://evil.example" + path,
        "https://sidof.segob.gob.mx:8443" + path,
        "https://user:secret@sidof.segob.gob.mx" + path,
        "https://sidof.segob.gob.mx" + path + "?track=1",
        "https://sidof.segob.gob.mx/imagenes_diarios/evil.svg",
    ]:
        assert official_image(url) is None


def test_invalid_or_missing_original_keeps_the_saved_text_and_its_numbering():
    content = "3.5. Cemento compuesto.\nTexto guardado.\n\n3.6. Cemento ordinario."
    for raw, media in [
        (None, "application/json"),
        (b"not json", "application/json"),
        (b"opaque original", "text/html"),
        (b'{"Nota":{"cadenaContenido":"null"}}', "application/json"),
        (b"%PDF-", "application/pdf"),
    ]:
        result = reading_tree(raw, media, content)
        assert result["format"] == "plain" and all_text(result["blocks"]) == content.replace("\n\n", "\n")
