"""Controlled connector tests. Fixtures do not assert live official coverage."""
from datetime import date
from pathlib import Path

import httpx
import pytest

from app.collectors import (CollectionError, FetchResult, SafeFetcher, collect,
                            extract_document, normalize_url, validate_url)


FIXTURES = Path(__file__).parent / "fixtures"
DAY = date(2026, 11, 2)
INDEX = "https://www.dof.gob.mx/index.php?year=2026&month=11&day=2"
BASE = "https://www.dof.gob.mx/index.php"


def fixture(name):
    return FetchResult((FIXTURES / name).read_bytes())


def dof_fetch(url):
    if "nota_detalle" in url:
        return fixture("dof_note.html")
    if "page=2" in url:
        return fixture("dof_page2.html")
    if "edicion=VES" in url:
        return fixture("dof_edition.html")
    return fixture("dof_index.html")


def test_discovery_additional_edition_pagination_and_continuation():
    first = collect("dof", [BASE], DAY, DAY, limit=1, fetcher=dof_fetch)
    assert not first.complete and len(first.documents) == 1
    all_documents = first.documents[:]
    cursor = first.continuation
    for _ in range(8):
        batch = collect("dof", [BASE], DAY, DAY, cursor, limit=1, fetcher=dof_fetch)
        assert not batch.errors
        all_documents.extend(batch.documents)
        cursor = batch.continuation
        if batch.complete:
            break
    else:
        pytest.fail("Continuation did not finish")
    assert {d.official_id for d in all_documents} == {"DOF:10001", "DOF:10002", "DOF:10003"}
    assert len(all_documents) == 3
    assert all(d.published_on == DAY for d in all_documents)
    assert all_documents[0].kind == "proyecto"


def test_failed_document_preserves_progress_and_retry_point():
    calls = []

    def fetch(url):
        calls.append(url)
        if "codigo=10002" in url:
            raise CollectionError("HTTP 503 controlado")
        return dof_fetch(url)

    partial = collect("dof", [BASE], DAY, DAY, fetcher=fetch)
    assert len(partial.documents) == 1
    assert partial.errors and not partial.complete
    assert "10002" in partial.continuation["pending"][0]["url"]
    resumed = collect("dof", [BASE], DAY, DAY, partial.continuation, fetcher=dof_fetch)
    assert resumed.complete and not resumed.errors
    assert {d.official_id for d in resumed.documents} == {"DOF:10002", "DOF:10003"}


def test_unknown_empty_index_is_not_no_changes():
    batch = collect("dof", [BASE], DAY, DAY, fetcher=lambda _: FetchResult(b"<html><h1>Portal renovado</h1></html>"))
    assert not batch.complete
    assert batch.errors
    assert batch.continuation["day"] == DAY.isoformat()


def test_self_link_does_not_turn_unknown_index_into_success():
    html = f'<a href="{INDEX}">Inicio</a><p>Formato desconocido</p>'.encode()
    batch = collect('dof', [BASE], DAY, DAY, fetcher=lambda _: FetchResult(html))
    assert not batch.complete and batch.errors
    assert not batch.documents


def test_dof_note_outside_requested_period_keeps_interval_pending():
    other_day = date(2025, 6, 2)
    batch = collect('dof', [BASE], other_day, other_day, fetcher=dof_fetch)
    assert not batch.complete and not batch.documents
    assert 'fuera del periodo' in batch.errors[0]


def test_explicit_no_publication_finishes_configured_day():
    batch = collect("dof", [BASE], DAY, DAY, fetcher=lambda _: FetchResult(b"<p>No hay publicaciones</p>"))
    assert batch.complete and not batch.documents and not batch.errors


def test_normalized_official_identity_removes_navigation_noise():
    assert normalize_url("https://dof.gob.mx/nota_detalle.php?fecha=01%2F01%2F2000&codigo=10001&utm_source=x#nav") == "https://www.dof.gob.mx/nota_detalle.php?codigo=10001"
    document = extract_document("https://www.dof.gob.mx/nota_detalle.php?codigo=10001", fixture("dof_note.html"))
    noisy = fixture("dof_note.html")
    noisy.body = noisy.body.replace(b"variables", b"nueva navegacion")
    assert extract_document(document.url, noisy).content == document.content
    assert "Menú" not in document.content
    assert document.kind == "proyecto"


def test_dates_are_not_inferred_from_detection_or_arbitrary_body_date():
    document = extract_document("https://platiica.economia.gob.mx/ficha-prueba/", FetchResult(b"<article><h1>Ficha</h1><p>Plazo 01/01/2030</p></article>"))
    assert document.published_on is None
    assert document.kind == "clasificacion_pendiente"


@pytest.mark.parametrize("url", ["http://www.dof.gob.mx/index.php", "https://127.0.0.1/", "https://www.dof.gob.mx.evil.test/", "https://user:pass@www.dof.gob.mx/", "https://www.dof.gob.mx:8080/", "https://169.254.169.254/metadata"])
def test_destination_validation_rejects_arbitrary_network_access(url):
    with pytest.raises(CollectionError):
        validate_url(url)


def test_dns_private_resolution_rejected(monkeypatch):
    monkeypatch.setattr("socket.getaddrinfo", lambda *a, **kw: [(2, 1, 6, "", ("127.0.0.1", 443))])
    with pytest.raises(CollectionError):
        validate_url("https://www.dof.gob.mx/index.php", resolve_dns=True)


def test_known_document_monitors_do_not_mistake_homepage_for_discovery():
    with pytest.raises(CollectionError):
        collect("snice", ["https://www.snice.gob.mx/"], DAY, DAY, fetcher=dof_fetch)
    with pytest.raises(CollectionError):
        collect("platiica", [], DAY, DAY, fetcher=dof_fetch)


def test_known_document_monitor_keeps_unknown_publication_date():
    batch = collect("snice", ["https://www.snice.gob.mx/prueba.html"], DAY, DAY,
                    fetcher=lambda _: FetchResult(b"<main><h1>Aviso controlado</h1><p>Contenido</p></main>"))
    assert batch.complete and len(batch.documents) == 1
    assert batch.documents[0].published_on is None
    assert "no descubre" in batch.coverage


def test_pdf_unprocessable_stays_visible_as_pending_reference():
    document = extract_document("https://www.snice.gob.mx/prueba.pdf", FetchResult(b"%PDF-invalid", "application/pdf"))
    assert document.raw and document.processing_note
    assert document.content == ""


def test_robots_disallow_blocks_without_requesting_document():
    calls = []

    def respond(request):
        calls.append(str(request.url))
        return httpx.Response(200, text="User-agent: *\nDisallow: /\n")

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        fetcher = SafeFetcher(client=client, interval=0, resolve_dns=False)
        with pytest.raises(CollectionError, match="robots.txt"):
            fetcher(BASE)
    assert len(calls) == 1 and calls[0].endswith("robots.txt")


def test_robots_unavailable_fails_closed():
    with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(403))) as client:
        fetcher = SafeFetcher(client=client, interval=0, resolve_dns=False)
        with pytest.raises(CollectionError, match="no verificable"):
            fetcher(BASE)


def test_robots_html_challenge_is_not_permission():
    with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, text="<html>Verify access</html>"))) as client:
        fetcher = SafeFetcher(client=client, interval=0, resolve_dns=False)
        with pytest.raises(CollectionError, match="HTML"):
            fetcher(BASE)


def test_note_redirect_to_homepage_is_not_recorded_as_publication():
    with pytest.raises(CollectionError, match="redirigió"):
        extract_document("https://www.dof.gob.mx/nota_detalle.php?codigo=10001",
                         FetchResult(b"<main>Portada</main>", url=BASE))


def test_redirect_to_internal_or_another_agency_is_rejected():
    def respond(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        return httpx.Response(302, headers={"location": "https://www.snice.gob.mx/private"})

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        fetcher = SafeFetcher(client=client, interval=0, resolve_dns=False)
        with pytest.raises(CollectionError):
            fetcher(BASE)


def test_download_size_is_bounded():
    def respond(request):
        return httpx.Response(404) if request.url.path == "/robots.txt" else httpx.Response(200, content=b"a" * 100)

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        fetcher = SafeFetcher(client=client, interval=0, resolve_dns=False, max_bytes=20)
        with pytest.raises(CollectionError, match="límite"):
            fetcher(BASE)


def test_compressed_response_is_decoded_once():
    import gzip
    def respond(request):
        if request.url.path == '/robots.txt': return httpx.Response(404)
        return httpx.Response(200,headers={'content-encoding':'gzip','content-type':'text/html'},content=gzip.compress(b'<main>Norma controlada</main>'))
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        result = SafeFetcher(client=client,interval=0,resolve_dns=False)(BASE)
        assert result.body == b'<main>Norma controlada</main>'


def test_continuation_cannot_be_reused_for_different_period():
    batch = collect("dof", [BASE], DAY, DAY, limit=1, fetcher=dof_fetch)
    with pytest.raises(CollectionError):
        collect("dof", [BASE], DAY, date(2026, 11, 3), batch.continuation, fetcher=dof_fetch)
def test_dof_does_not_silently_ignore_additional_base_urls():
    from datetime import date
    from app.collectors import collect, CollectionError
    import pytest
    with pytest.raises(CollectionError, match="único índice"):
        collect("dof", ["https://www.dof.gob.mx/index.php", "https://dof.gob.mx/index.php"],
                date(2026, 1, 1), date(2026, 1, 1))
