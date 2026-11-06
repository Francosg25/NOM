from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.collectors import Batch, CollectionError, Document, FetchResult
from app.collectors.platiica_catalog import SITEMAP_URL, _document, collect_catalog
from app.jobs import request_job, run_once
from app.models import Alert, Base, Publication, Source, Version, utcnow
from app.storage import LocalEvidenceStore

POST_SITEMAP = "https://platiica.economia.gob.mx/normalizacion/wp-sitemap-posts-post-1.xml"
OLD_NOM = "https://platiica.economia.gob.mx/normalizacion/nom-010-stps-1999/"
CURRENT_NOM = "https://platiica.economia.gob.mx/normalizacion/nom-037-sct2-2020/"


def _xml(entries):
    rows = "".join(
        f"<url><loc>{url}</loc>{f'<lastmod>{lastmod}</lastmod>' if lastmod else ''}</url>"
        for url, lastmod in entries
    )
    return FetchResult(
        f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{rows}</urlset>'.encode(),
        "application/xml",
    )


def _page(code, title, status, scope):
    return FetchResult(
        f"""<html><head><meta charset="utf-8"></head><body><article class="entry-content">
        <h1>{code}</h1>
        <p><strong>Clave de la Norma:</strong> {code}</p>
        <p><strong>Título de la Norma:</strong> {title}</p>
        <p><strong>Estado de la Norma:</strong> {status}</p>
        <p><strong>Fecha de publicación en el DOF:</strong> 18/2/2021</p>
        <p><strong>Producto, servicio, proceso o sistema:</strong> {scope}</p>
        <a href="https://www.dof.gob.mx/nota_detalle.php?codigo=123">DOF</a>
        </article></body></html>""".encode(),
        "text/html",
    )


def _fetcher(fail=()):
    sitemap = "https://platiica.economia.gob.mx/normalizacion/wp-sitemap.xml"
    responses = {
        sitemap: _xml([(POST_SITEMAP, None)]),
        POST_SITEMAP: _xml(
            [
                (CURRENT_NOM, "2026-01-02T10:00:00-06:00"),
                (OLD_NOM, "2025-12-01T10:00:00-06:00"),
                ("https://platiica.economia.gob.mx/normalizacion/nmx-foo-2020/", None),
            ]
        ),
        OLD_NOM: _page("NOM-010-STPS-1999", "Agentes químicos", "Cancelada", "Centros de trabajo"),
        CURRENT_NOM: _page(
            "NOM-037-SCT2-2020", "Barreras de protección", "Vigente", "Carreteras y vías urbanas"
        ),
    }

    def fetch(url):
        if url in fail:
            raise CollectionError("Error temporal controlado")
        return responses[url]

    return fetch


def test_catalog_discovers_noms_skips_nmx_and_extracts_official_fields():
    first = collect_catalog([SITEMAP_URL], None, 1, {}, fetcher=_fetcher())
    assert not first.complete and len(first.documents) == 1
    assert first.documents[0].official_id == "PLATIICA:NOM-010-STPS-1999"
    assert first.documents[0].norm_status == "Cancelada"
    assert first.documents[0].kind == "norma_no_vigente"
    assert first.continuation["discovered"] == 2
    assert first.checks[0]["sitemaps"] == 1

    second = collect_catalog(
        [SITEMAP_URL], first.continuation, 1, {}, fetcher=_fetcher()
    )
    assert second.complete and second.continuation is None
    current = second.documents[0]
    assert current.official_id == "PLATIICA:NOM-037-SCT2-2020"
    assert current.norm_status == "Vigente"
    assert current.kind == "norma_vigente"
    assert current.product_scope == "Carreteras y vías urbanas"
    assert current.published_on.isoformat() == "2021-02-18"
    assert current.source_updated_at == datetime(2026, 1, 2, 16, tzinfo=timezone.utc)
    assert "https://www.dof.gob.mx/nota_detalle.php?codigo=123" in current.links


def test_catalog_accepts_soft_hyphen_and_slash_in_official_nom_codes():
    cases = [
        ("\u00ad", "NOM-001-SAG-GAN-2015"),
        ("", "NOM-002/1-SCT/2009"),
    ]
    for soft_hyphen, expected_code in cases:
        code = f"NOM-{soft_hyphen}002/1-SCT/2009" if "/" in expected_code else (
            f"NOM-{soft_hyphen}001-{soft_hyphen}SAG-GAN-{soft_hyphen}2015"
        )
        document = _document(
            CURRENT_NOM,
            _page(code, "Official title", "Vigente", "Product scope"),
            None,
        )
        assert document.official_id == f"PLATIICA:{expected_code}"
        assert document.title == f"{expected_code} - Official title"


def test_catalog_delta_uses_sitemap_lastmod_and_does_not_refetch_unchanged_pages():
    known = {
        OLD_NOM: datetime(2025, 12, 1, 16, tzinfo=timezone.utc),
        CURRENT_NOM: datetime(2026, 1, 2, 16, tzinfo=timezone.utc),
    }
    batch = collect_catalog([SITEMAP_URL], None, 10, known, fetcher=_fetcher())
    assert batch.complete and batch.documents == []
    assert batch.checks[0]["unchanged_pages"] == 2


def test_catalog_failed_ficha_stays_in_durable_continuation():
    first = collect_catalog([SITEMAP_URL], None, 1, {}, fetcher=_fetcher(fail={OLD_NOM}))
    assert first.errors and first.continuation["cursor"] == 1
    assert first.continuation["phase"] == "fetching"
    second = collect_catalog(
        [SITEMAP_URL], first.continuation, 1, {}, fetcher=_fetcher()
    )
    assert not second.complete and len(second.documents) == 1
    assert second.continuation["phase"] == "retrying_failed"
    assert second.continuation["queue"] == [{"url": OLD_NOM, "lastmod": "2025-12-01T10:00:00-06:00"}]
    retry = collect_catalog([SITEMAP_URL], second.continuation, 1, {}, fetcher=_fetcher())
    assert retry.complete and retry.documents[0].official_id == "PLATIICA:NOM-010-STPS-1999"


def test_catalog_job_ingests_status_changes_as_new_versions(tmp_path, monkeypatch):
    from app.collectors import platiica_catalog

    engine = create_engine(f"sqlite:///{tmp_path / 'catalog-job.db'}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    storage = LocalEvidenceStore(tmp_path / "evidence")
    current = datetime(2026, 1, 2, 16, tzinfo=timezone.utc)
    changed = datetime(2026, 2, 1, 16, tzinfo=timezone.utc)
    today = utcnow().astimezone(ZoneInfo("America/Mexico_City")).date()
    with sessions() as db:
        source = Source(
            name="Catálogo PLATIICA",
            kind="platiica_catalog",
            urls=[SITEMAP_URL],
            schedule_enabled=True,
        )
        db.add(source)
        db.commit()
        source_id = source.id

        def controlled(status, modified):
            return Document(
                official_id="PLATIICA:NOM-037-SCT2-2020",
                url=CURRENT_NOM,
                title="NOM-037-SCT2-2020 - Barreras",
                content=f"Estado de la Norma: {status}\nCarreteras y vías urbanas.",
                kind="norma_vigente" if status == "Vigente" else "norma_no_vigente",
                raw=f"<html>{status}</html>".encode(),
                norm_status=status,
                product_scope="Carreteras y vías urbanas",
                source_updated_at=modified,
            )

        original = controlled("Vigente", current)
        request_job(db, source_id, "test", today, today)

        def initial_catalog(urls, continuation, limit, known_updated):
            assert known_updated == {}
            return Batch([original], True, None, "Sitemap controlado")

        monkeypatch.setattr(platiica_catalog, "collect_catalog", initial_catalog)
        first = run_once(db, storage=storage)
        assert first.status == "succeeded" and first.new_count == 1

        previous = db.get(Publication, db.scalar(select(Publication.id)))
        request_job(db, source_id, "test", today, today)

        def changed_status(urls, continuation, limit, known_updated):
            assert known_updated[CURRENT_NOM] is not None
            return Batch([controlled("Cancelada", changed)], True, None, "Sitemap controlado")

        monkeypatch.setattr(platiica_catalog, "collect_catalog", changed_status)
        second = run_once(db, storage=storage)
        assert second.status == "succeeded" and second.modified_count == 1
        db.refresh(previous)
        assert previous.norm_status == "Cancelada"
        assert previous.kind == "norma_no_vigente"
        assert db.scalar(select(func.count(Version.id))) == 2
        assert db.scalar(select(func.count(Alert.id))) == 0
    engine.dispose()
