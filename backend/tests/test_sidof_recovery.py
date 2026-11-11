"""Recovery must use verifiable original evidence, including negative cases."""

import io
import json

import httpx
import pytest
from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject

from app.collectors.core import CollectionError, FetchResult, SafeFetcher, _kind
from app.collectors.sidof import API_BASE, EDITIONS, _document, collect_daily
from app.collectors.sidof_recovery import JournalRecovery, ORIGIN
from datetime import date

DAY = date(2026, 11, 7)
PDF_DAY = date(2026, 11, 5)


def response(**fields):
    return FetchResult(
        json.dumps({"messageCode": 200, "response": "OK", **fields}).encode(), "application/json"
    )


def calendar_service(
    *, css=None, displayed="06-11-2026", diaries=None, notes=None, redirect=None, linked=True
):
    def fetch(url):
        if "/diarios/porFecha/" in url:
            raise CollectionError("HTTP 404")
        if "/notas/" in url:
            if notes is None:
                raise CollectionError("HTTP 404")
            return response(**notes)
        if url == f"{API_BASE}/diarios/2026":
            return response(ListaDiarios=diaries or [], FechasSinPublicacion=[])
        if "/welcome/" in url:
            link = '<link href="/assets/css/calendarCss/2026.css">' if linked else ""
            return FetchResult(
                (link + f'<input id="fechaPub" value="{displayed}">').encode(), url=redirect or url
            )
        if url.endswith("2026.css"):
            body = (
                css
                if css is not None
                else 'td[data-day="07/11/2026"] {color:#c9c9c9!important; cursor:not-allowed!important;}'
            )
            return FetchResult(body.encode(), "text/css", url)
        raise AssertionError(url)

    return fetch


def test_missing_api_calendar_recovers_only_from_linked_disabled_portal_date():
    batch = collect_daily([API_BASE], DAY, DAY, None, 40, fetcher=calendar_service())
    assert batch.complete and not batch.errors and not batch.documents
    check = batch.checks[0]
    assert check["declared_no_publication"]
    assert check["absence_basis"] == "sidof_portal_calendar"
    assert check["calendar_url"] == ORIGIN + "/assets/css/calendarCss/2026.css"
    assert len(check["calendar_sha256"]) == len(check["calendar_page_sha256"]) == 64


@pytest.mark.parametrize(
    "options",
    [
        {"css": 'td[data-day="08/11/2026"] {cursor:not-allowed!important;}'},
        {"css": '/* td[data-day="07/11/2026"] {cursor:not-allowed;} */'},
        {"css": 'td[data-day="07/11/2026"] {color:gray;}'},
        {
            "css": 'td[data-day="07/11/2026"] {cursor:not-allowed;} td[data-day="07/11/2026"] {border:2px solid red;}'
        },
        {"displayed": "07-11-2026"},
        {"displayed": "08-11-2026"},
        {"displayed": "invalid"},
        {"linked": False},
        {"redirect": ORIGIN + "/"},
        {"diaries": [{"fecha": "07-11-2026", "codDiario": 1, "codEdicion": "EXT"}]},
        {"notes": {**{group: [] for group in EDITIONS.values()}, "NotasExtraordinarias": [{"codNota": 1}]}},
    ],
)
def test_absence_cannot_be_inferred_from_weekend_redirect_incomplete_or_conflicting_calendar(options):
    batch = collect_daily([API_BASE], DAY, DAY, None, 40, fetcher=calendar_service(**options))
    assert not batch.complete and batch.errors and not batch.checks
    assert batch.continuation["queue"][0]["day"] == str(DAY)


def pdf(*, text=None):
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})}
    )
    lines = text or [
        "1 DIARIO OFICIAL Jueves 5 de noviembre de 2026",
        "SECRETARIA DE PRUEBA",
        "ACUERDO de prueba sobre un asunto ajeno a las normas.",
        "Al margen un sello con el Escudo Nacional.",
        "Texto controlado suficiente para comprobar una pagina del diario.",
    ]
    operations = ["BT /F1 10 Tf 50 750 Td 14 TL"]
    for line in lines:
        escaped = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        operations.append(f"({escaped}) Tj T*")
    operations.append("ET")
    stream = DecodedStreamObject()
    stream.set_data("\n".join(operations).encode("latin1"))
    page[NameObject("/Contents")] = writer._add_object(stream)
    result = io.BytesIO()
    writer.write(result)
    return result.getvalue()


def note_result(**changes):
    note = {"codNota": 1, "codDiario": 100, "fecha": "05-11-2026", "pagina": 1, "codSeccion": "UNICA"}
    return response(Nota={**note, **changes})


EXPECTED = {"id": "1", "diary": "100", "title": "", "page": 1, "section": "UNICA"}


def test_pdf_page_resolves_missing_json_text_with_evidence_and_one_download_per_journal():
    calls = []

    def fetch(url):
        calls.append(url)
        return FetchResult(pdf(), "application/pdf", url)

    recovery = JournalRecovery(fetch)
    for _ in range(2):
        check = {}
        doc = _document(note_result(), EXPECTED, PDF_DAY, recovery, check)
        assert doc is None  # Successfully read and classified as unrelated to NOM.
        evidence = check["recovered_references"][0]
        assert evidence["page"] == 1 and evidence["selected"] is False
        assert evidence["title"].startswith("ACUERDO de prueba")
        assert len(evidence["pdf_sha256"]) == len(evidence["page_text_sha256"]) == 64
    assert calls == [f"{API_BASE}/documentos/pdf/100"]


def test_nom_on_shared_pdf_page_is_not_discarded_by_unrelated_first_heading():
    content = [
        "1 DIARIO OFICIAL Jueves 5 de noviembre de 2026",
        "ACUERDO de prueba sobre otro asunto.",
        "Al margen un sello.",
        "Texto de prueba.",
        "NORMA Oficial Mexicana NOM-TEST-2026, titulo controlado.",
        "Requisitos del documento.",
    ]
    recovery = JournalRecovery(lambda url: FetchResult(pdf(text=content), "application/pdf", url))
    check = {}
    doc = _document(note_result(), EXPECTED, PDF_DAY, recovery, check)
    assert doc and "NOM-TEST-2026" in doc.content and doc.raw.startswith(b"%PDF-")
    assert check["recovered_references"][0]["selected"]
    assert not doc.processing_note


def test_literal_nulls_in_api_do_not_pass_as_readable_title_or_content():
    recovery = JournalRecovery(lambda url: FetchResult(pdf(), "application/pdf", url))
    check = {}
    result = note_result(titulo="null", cadenaContenido="null", contenidoTxt="None")
    doc = _document(result, EXPECTED, PDF_DAY, recovery, check)
    assert doc is None and check["recovered_references"]


def test_untitled_pdf_page_does_not_duplicate_the_same_indexed_nom():
    title = "NORMA Oficial Mexicana de Emergencia NOM-EM-TEST-2026, prueba."
    content = [
        "1 DIARIO OFICIAL Jueves 5 de noviembre de 2026",
        title,
        "Al margen un sello.",
        "Contenido controlado suficiente para verificar la pagina original.",
    ]
    expected = {**EXPECTED, "page_titles": [{"id": "2", "title": title}]}
    recovery = JournalRecovery(lambda url: FetchResult(pdf(text=content), "application/pdf", url))
    check = {}
    doc = _document(note_result(existeDoc="N"), expected, PDF_DAY, recovery, check)
    assert doc is None
    assert check["recovered_references"][0]["represented_by"] == "DOF:2"
    assert check["recovered_references"][0]["selected"] is False
    # Same page but a different heading is insufficient to merge two records.
    expected["page_titles"][0]["title"] = "NORMA Oficial Mexicana NOM-OTHER-2026, otra norma."
    assert _document(note_result(existeDoc="N"), expected, PDF_DAY, recovery, {}) is not None
    expected["page_titles"][0]["title"] = title
    content.append("NORMA Oficial Mexicana NOM-OTHER-2026, adicional en la misma pagina.")
    recovery = JournalRecovery(lambda url: FetchResult(pdf(text=content), "application/pdf", url))
    assert _document(note_result(existeDoc="N"), expected, PDF_DAY, recovery, {}) is not None


@pytest.mark.parametrize(
    "change", ["wrong_date", "wrong_page", "not_pdf", "redirect", "invalid_section", "mismatched_index"]
)
def test_unverifiable_pdf_never_clears_a_reference(change):
    body = pdf()
    result = note_result()
    if change == "wrong_date":
        body = pdf(
            text=[
                "1 DIARIO OFICIAL Viernes 6 de noviembre de 2026",
                "ACUERDO de prueba.",
                "Texto de prueba " * 15,
            ]
        )
    if change == "wrong_page":
        body = pdf(
            text=[
                "2 DIARIO OFICIAL Jueves 5 de noviembre de 2026",
                "ACUERDO de prueba.",
                "Texto de prueba " * 15,
            ]
        )
    if change == "not_pdf":
        body = b"<html>Unavailable</html>"
    if change == "invalid_section":
        result = note_result(codSeccion="PRIMERA")
    if change == "mismatched_index":
        result = note_result(pagina=2)
    recovery = JournalRecovery(
        lambda url: FetchResult(body, "application/pdf", ORIGIN + "/" if change == "redirect" else url)
    )
    check = {}
    doc = _document(result, EXPECTED, PDF_DAY, recovery, check)
    assert isinstance(doc, dict) and doc["recovery_error"]
    assert not check.get("recovered_references")


def test_larger_pdf_limit_does_not_expand_html_or_json_downloads():
    def route(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        return httpx.Response(200, content=b"a" * 100)

    with httpx.Client(transport=httpx.MockTransport(route)) as client:
        fetch = SafeFetcher(client=client, interval=0, resolve_dns=False, max_bytes=20, pdf_max_bytes=120)
        assert len(fetch(f"{API_BASE}/documentos/pdf/100").body) == 100
        with pytest.raises(CollectionError, match="límite"):
            fetch(f"{API_BASE}/notas/nota/1")
        with pytest.raises(CollectionError, match="límite"):
            fetch(ORIGIN + "/other.pdf")


def test_emergency_norm_is_distinct_from_definitive_norm():
    assert _kind("Norma Oficial Mexicana de Emergencia NOM-EM-023-SE-2026") == "norma_emergencia"
