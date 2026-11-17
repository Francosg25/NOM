"""Controlled Word structures plus integrity checks of the dated official index."""

import gzip
import io
import json
import re
from pathlib import Path
from types import SimpleNamespace
from xml.sax.saxutils import escape
from zipfile import ZipFile

import pytest

from app import tariff_reference as reference
from app.collectors import CollectionError, FetchResult

SOURCE = "https://www.snice.gob.mx/~oracle/SNICE_DOCS/ACUERDO-REGLAS-SE-CONTROLLED.docx"


def paragraph(text):
    return f"<w:p><w:r><w:t>{escape(text)}</w:t></w:r></w:p>"


def table(rows):
    return "<w:tbl>" + "".join(
        "<w:tr>" + "".join("<w:tc>" + paragraph(c) + "</w:tc>" for c in row) + "</w:tr>"
        for row in rows
    ) + "</w:tbl>"


def word(*, bad_row=False, end=True):
    header = ["Fracción arancelaria/NICO", "Descripción", "NOM / Acotación"]
    rows = [header, ["1234.56.78", "Producto controlado", "NOM-999-SE-2099 Únicamente: muestra."],
            [""], ["01", "Muestra pequeña", "Excepto: usos controlados."]]
    if bad_row:
        rows.append(["1234", "Ambiguo", "NOM-998-SE-2099"])
    content = paragraph("(Modificación, DOF 2 de abril de 2026)")
    content += paragraph("ANEXO 2.4.1") + paragraph("1.- Introducción de mercancías") + table(rows)
    content += paragraph("3.- Información comercial")
    content += paragraph("I. Capítulo 5 de la NOM-997-SE-2099 (cancela la NOM-997-SE-2000).")
    content += table([header, ["1234.56.79", "Otro producto", ""], ["00", "Todos", ""]])
    content += paragraph("4.- Exportaciones") + table([header, ["9999.99.99", "Exportación", "NOM-996-SE-2099"]])
    if end:
        content += paragraph("ANEXO 2.5.1")
    raw = io.BytesIO()
    with ZipFile(raw, "w") as archive:
        archive.writestr("word/document.xml", '<w:document xmlns:w="' + reference.NS["w"] + '"><w:body>' + content + "</w:body></w:document>")
    return raw.getvalue()


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(reference, "get_settings", lambda: SimpleNamespace(storage_path=str(tmp_path)))
    reference._read.cache_clear()
    return tmp_path


def test_parser_preserves_exact_rows_qualifications_and_nico_without_export_or_cancelled_predecessor():
    result = reference.parse_compilation(word(), SOURCE, retrieved_at="2026-11-17T12:00:00Z")
    assert result["document_date"] == "2026-04-02"
    assert set(result["relations"]) == {"12345678", "12345679"}
    row = result["relations"]["12345678"][0]
    assert row["nom_codes"] == ["NOM-999-SE-2099"]
    assert row["qualification"] == "NOM-999-SE-2099 Únicamente: muestra."
    assert row["nico_rows"] == [["01", "Muestra pequeña", "Excepto: usos controlados."]]
    assert result["relations"]["12345679"][0]["nom_codes"] == ["NOM-997-SE-2099"]
    assert len(result["source_sha256"]) == 64


@pytest.mark.parametrize("raw,source", [(b"HTML error", SOURCE), (word(bad_row=True), SOURCE),
    (word(end=False), SOURCE), (word(), "https://untrusted.example/file.docx")])
def test_parser_rejects_unknown_or_incomplete_sources(raw, source):
    with pytest.raises(ValueError):
        reference.parse_compilation(raw, source)


def test_parser_rejects_xml_entities_and_size_limits(monkeypatch):
    raw = io.BytesIO()
    with ZipFile(raw, "w") as archive:
        archive.writestr("word/document.xml", '<!DOCTYPE x [<!ENTITY y "no">]><x/>')
    with pytest.raises(ValueError, match="entidades"):
        reference.parse_compilation(raw.getvalue(), SOURCE)
    monkeypatch.setattr(reference, "MAX_XML", 5)
    with pytest.raises(ValueError, match="grande"):
        reference.parse_compilation(word(), SOURCE)


def test_bundled_reference_is_dated_and_contains_verified_import_rows(isolated):
    data = reference.load_reference()
    assert data["document_date"] == "2026-04-02" and len(data["relations"]) == 2529
    assert len(data["source_sha256"]) == 64
    assert all(re.fullmatch(r"\d{8}", code) for code in data["relations"])
    assert all(row["section"] in {"1", "2", "3", "5"} for rows in data["relations"].values() for row in rows)
    result = reference.lookup_tariff("8501520401")
    assert result["matches"][0]["nom_codes"] == ["NOM-016-ENER-2016"]
    assert result["match_level"] == "fraccion_base" and result["requested_nico"] == "01"
    assert reference.lookup_tariff("85011001")["matches"] == []


def test_corrupt_runtime_index_falls_back_and_unavailable_is_not_no_matches(isolated, monkeypatch):
    target, _ = reference._paths()
    reference._atomic_write(target, b"broken")
    assert reference.lookup_tariff("85015204")["available"]
    reference._atomic_write(target, gzip.compress(b'{"schema":0}'))
    assert reference.lookup_tariff("85015204")["available"]
    monkeypatch.setattr(reference, "BUNDLED", Path(isolated) / "absent")
    assert reference.lookup_tariff("85015204") == {"available": False, "matches": [], "source_page": reference.SOURCE_PAGE}


def test_old_persistent_reference_does_not_hide_a_newer_bundle(isolated):
    target, _ = reference._paths()
    data = reference.parse_compilation(word(), SOURCE)
    data['document_date'] = '2020-01-01'
    reference._atomic_write(target, gzip.compress(json.dumps(data).encode()))
    assert reference.lookup_tariff('85015204')['document_date'] == '2026-04-02'
    assert reference.lookup_tariff('85015204')['matches']


def test_refresh_failure_keeps_valid_index_and_daily_retry_state(isolated):
    def fail(url):
        raise CollectionError("controlled network failure")
    assert not reference.refresh_reference(fetcher=fail, force=True)
    assert reference.lookup_tariff("85015204")["refresh_failed"]
    assert reference.lookup_tariff("85015204")["matches"]
    assert not reference.refresh_reference(fetcher=lambda url: pytest.fail("Retried too early"))


def test_refresh_discovers_only_official_word_and_replaces_valid_index(isolated, monkeypatch):
    data = reference.parse_compilation(word(), SOURCE)
    # Controlled fixture exceeds the minimum-size guard without inventing
    # entries in the bundled reference or any real user's database.
    data["relations"].update({f"{i:08}": [] for i in range(100)})
    monkeypatch.setattr(reference, "parse_compilation", lambda *args, **kwargs: data)
    monkeypatch.setattr(reference, "load_reference", lambda: None)
    calls = []
    def fetch(url):
        calls.append(url)
        return FetchResult(f'<a href="{SOURCE}">Word</a>'.encode() if url == reference.LIBRARY_URL else word())
    assert reference.refresh_reference(fetcher=fetch, force=True)
    target, state = reference._paths()
    assert json.loads(gzip.decompress(target.read_bytes()))["relations"]["12345678"]
    assert not json.loads(state.read_text())["error"]
    assert calls == [reference.LIBRARY_URL, SOURCE]


def test_refresh_rejects_ambiguous_or_regressing_compilations(isolated, monkeypatch):
    assert not reference.refresh_reference(fetcher=lambda url: FetchResult(b"<p>No Word compilation</p>"), force=True)
    data = reference.parse_compilation(word(), SOURCE)
    monkeypatch.setattr(reference, "parse_compilation", lambda *a, **k: data)
    def fetch(url):
        return FetchResult(f'<a href="{SOURCE}">Word</a>'.encode() if url == reference.LIBRARY_URL else word())
    assert not reference.refresh_reference(fetcher=fetch, force=True)
    assert reference.lookup_tariff("85015204")["matches"]


def test_unchanged_download_does_not_reparse_or_relabel_document_date(isolated, monkeypatch):
    data = reference.parse_compilation(word(), SOURCE)
    monkeypatch.setattr(reference, "load_reference", lambda: data)
    monkeypatch.setattr(reference, "parse_compilation", lambda *a, **k: pytest.fail("Unchanged source reparsed"))
    class Client:
        closed = False
        def __call__(self, url):
            return FetchResult(f'<a href="{SOURCE}">Word</a>'.encode() if url == reference.LIBRARY_URL else word())
        def close(self):
            self.closed = True
    client = Client()
    monkeypatch.setattr(reference, "SafeFetcher", lambda **kwargs: client)
    assert reference.refresh_reference(force=True)
    assert client.closed and data["document_date"] == "2026-04-02"
    assert not reference._paths()[0].exists()


def test_client_configuration_error_is_visible_without_discarding_bundled_reference(isolated, monkeypatch):
    def fail(**kwargs):
        raise CollectionError("Controlled TLS configuration error")
    monkeypatch.setattr(reference, "SafeFetcher", fail)
    assert not reference.refresh_reference(force=True)
    assert reference.lookup_tariff("85015204")["refresh_failed"]
    assert reference.lookup_tariff("85015204")["matches"]
