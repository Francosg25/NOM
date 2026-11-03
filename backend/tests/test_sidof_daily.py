"""Controlled API contracts; live acceptance is recorded separately in the docs."""
from datetime import date, timedelta
from copy import deepcopy
import json

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app import cli, verification
from app.collectors import Batch, CollectionError, FetchResult, collect
from app.collectors.sidof import API_BASE, EDITIONS, relevant
from app.jobs import ingest_document, request_job, run_once
from app.main import validate_source_urls
from app.models import Audit, Base, Job, Publication, Source, Version, utcnow
from app.operations import schedule_due
from app.storage import LocalEvidenceStore

DAY = date(2026, 11, 2)
TITLE = 'NORMA Oficial Mexicana NOM-TEST-2026, muestra controlada'


def test_unicode_identifiers_and_nmx_remain_distinct():
    assert relevant('PROY‑NOM‑TEST‑2026')
    assert relevant('NOM–TEST–2026')
    assert not relevant('NMX‑TEST‑2026 (sustituye NOM-TEST-1987)')


def response(**fields):
    return FetchResult(json.dumps({'messageCode':200, 'response':'OK', **fields}).encode(), 'application/json')


class Service:
    def __init__(self):
        self.calls = []
        self.days, self.details = {}, {}
        self.fail = None

    def note(self, code, title=TITLE, *, edition='Matutina', day=DAY, detail_title=None, html=None):
        manifest, listing = self.days.setdefault(day, (
            {edition:None for edition in EDITIONS}, {group:[] for group in EDITIONS.values()}))
        diary = str(list(EDITIONS).index(edition) + 100)
        manifest[edition] = [{'codDiario':diary, 'codSeccion':'UNICA'}]
        listing[EDITIONS[edition]].append({'codNota':str(code), 'codDiario':diary,
            'fecha':day.strftime('%d-%m-%Y'), 'titulo':title})
        self.details[str(code)] = {'codNota':str(code), 'codDiario':diary,
            'fecha':day.strftime('%d-%m-%Y'), 'titulo':detail_title if detail_title is not None else title,
            'cadenaContenido':html if html is not None else '<h1>' + (title or '') + '</h1><p>Texto controlado.</p>'}

    def __call__(self, url):
        self.calls.append(url)
        if self.fail and url.endswith(self.fail):
            raise CollectionError('HTTP 503 controlado')
        if '/notas/nota/' in url:
            return response(Nota=self.details[url.rsplit('/', 1)[1]])
        stamp = url.rsplit('/', 1)[1]
        day = date.fromisoformat('-'.join(reversed(stamp.split('-'))))
        manifest, listing = self.days[day]
        return response(**(manifest if '/diarios/porFecha/' in url else listing))


def daily(service, start=DAY, end=DAY, cursor=None, limit=200):
    return collect('sidof', [API_BASE], start, end, cursor, limit=limit, fetcher=service)


def test_all_editions_filtered_and_original_json_preserved():
    service = Service()
    service.note(1)
    service.note(2, 'PROY-NOM-TEST-2026, proyecto controlado', edition='Vespertina')
    service.note(3, 'MODIFICACIÓN de la NOM-TEST-2020', edition='Extraordinaria')
    service.note(4, 'AVISO de cancelación de la NOM-TEST-2010')
    service.note(5, 'ACUERDO que modifica el Anexo 2.4.1')
    service.note(6, 'NMX-TEST-2026, norma mexicana de muestra')
    service.note(7, 'DECRETO de asunto sin relación con las NOM')
    batch = daily(service)
    assert batch.complete and not batch.errors
    assert [d.official_id for d in batch.documents] == ['DOF:1', 'DOF:4', 'DOF:5', 'DOF:2', 'DOF:3']
    assert {d.kind for d in batch.documents} >= {'proyecto', 'modificacion', 'cancelacion'}
    assert all(d.published_on == DAY and d.media_type == 'application/json' for d in batch.documents)
    assert json.loads(batch.documents[0].raw)['Nota']['codNota'] == '1'
    assert batch.checks[0]['notes_checked'] == 7
    assert batch.checks[0]['diary_ids'] == ['100', '101', '102']
    assert not any(url.endswith(('/6', '/7')) for url in service.calls)


def test_missing_title_resolves_from_detail_or_stays_visible_without_blocking_nom():
    service = Service()
    service.note(1, None, html='<h1>' + TITLE + '</h1><p>Contenido.</p>')
    service.note(2, None)
    service.details['2']['cadenaContenido'] = None  # image-only official reference
    service.note(3, None, html='<p>Texto sin encabezado identificable.</p>')
    service.note(4)
    batch = daily(service)
    assert batch.complete and not batch.errors
    assert [d.official_id for d in batch.documents] == ['DOF:1', 'DOF:4']
    assert [d['id'] for d in batch.checks[0]['unresolved']] == ['DOF:2', 'DOF:3']
    assert all(len(d['detail_sha256']) == 64 for d in batch.checks[0]['unresolved'])


def test_known_nom_without_text_keeps_reference_and_never_claims_readable_text():
    service = Service()
    service.note(1)
    service.details['1'].update(titulo=None, cadenaContenido=None)
    batch = daily(service)
    assert batch.complete and len(batch.documents) == 1
    assert not batch.documents[0].content and batch.documents[0].processing_note
    assert batch.checks[0]['unresolved'][0]['id'] == 'DOF:1'


def test_failed_detail_keeps_successes_and_exact_retry_point():
    service = Service()
    service.note(1); service.note(2); service.note(3)
    service.fail = '/2'
    first = daily(service)
    assert not first.complete and first.errors
    assert [d.official_id for d in first.documents] == ['DOF:1']
    assert first.continuation['queue'][0]['pending'][0]['id'] == '2'
    cursor = deepcopy(first.continuation)
    service.fail = None
    second = daily(service, cursor=first.continuation)
    assert second.complete and not second.errors
    assert [d.official_id for d in second.documents] == ['DOF:2', 'DOF:3']
    assert second.checks[0]['selected_ids'] == ['DOF:1', 'DOF:2', 'DOF:3']
    assert cursor == first.continuation  # collecting cannot mutate a persisted cursor


def test_limit_continues_across_dates_without_dropping_or_repeating():
    service = Service()
    service.note(1); service.note(2)
    service.note(3, day=DAY + timedelta(days=1))
    docs, checks, cursor = [], [], None
    for _ in range(5):
        batch = daily(service, end=DAY + timedelta(days=1), cursor=cursor, limit=1)
        assert not batch.errors
        docs += batch.documents; checks += batch.checks; cursor = batch.continuation
        if batch.complete: break
    assert batch.complete and [d.official_id for d in docs] == ['DOF:3', 'DOF:1', 'DOF:2']
    assert len(checks) == 2 and [len(c['selected_ids']) for c in checks] == [1, 2]


@pytest.mark.parametrize('change', ['date', 'diary', 'identity', 'partial', 'invalid-json'])
def test_untrusted_or_incomplete_detail_does_not_advance_cursor(change):
    service = Service(); service.note(1)
    if change == 'date': service.details['1']['fecha'] = '01-11-2026'
    if change == 'diary': service.details['1']['codDiario'] = 999
    if change == 'identity': service.details['1']['codNota'] = 2
    if change == 'partial': service.details['1']['tamanioExcesivo'] = True
    fetch = service
    if change == 'invalid-json':
        fetch = lambda url: FetchResult(b'<html>Sign in</html>') if '/notas/nota/' in url else service(url)
    batch = daily(fetch)
    assert not batch.complete and batch.errors and not batch.documents
    assert batch.continuation['queue'][0]['pending'][0]['id'] == '1'


def test_unknown_empty_day_is_pending_until_official_absence_is_declared():
    def empty(url, absent=False):
        if '/diarios/porFecha/' in url: return response(**{edition:None for edition in EDITIONS})
        if '/notas/' in url: return response(**{group:[] for group in EDITIONS.values()})
        return response(FechasSinPublicacion=['02-11-2026'] if absent else [])
    pending = daily(empty)
    assert not pending.complete and pending.errors and not pending.checks
    absent = daily(lambda url: empty(url, True))
    assert absent.complete and absent.checks[0]['declared_no_publication']


def test_failed_date_does_not_block_other_dates_and_can_be_retried():
    service = Service(); service.note(1); service.note(2, day=DAY + timedelta(days=1))
    service.fail = '/diarios/porFecha/03-11-2026'
    batch = daily(service, end=DAY + timedelta(days=1))
    assert not batch.complete and batch.errors
    assert [d.official_id for d in batch.documents] == ['DOF:1']
    assert batch.continuation['queue'][0]['day'] == '2026-11-03'
    service.fail = None
    resumed = daily(service, end=DAY + timedelta(days=1), cursor=batch.continuation)
    assert resumed.complete and [d.official_id for d in resumed.documents] == ['DOF:2']


def test_failed_historical_date_cannot_freeze_new_daily_queries(state):
    db, source, store = state
    source.schedule_enabled = True; source.schedule_start = DAY - timedelta(days=6); db.commit()
    previous = request_job(db, source.id, 'scheduler', DAY - timedelta(days=6), DAY)
    cursor = {'mode':'sidof_api_v1','start':str(DAY - timedelta(days=6)),'end':str(DAY),
              'queue':[{'day':'2026-10-31', 'failed':True, 'loaded':False, 'pending':[], 'check':None}]}
    run_once(db, storage=store, collector=lambda *a, **kw: Batch([], False, cursor, 'Controlado', ['HTTP 404 controlado']))
    source.next_due_at = None; db.commit()
    current = db.get(Job, schedule_due(db, utcnow())[0])
    assert current.id != previous.id and current.continuation is None
    assert current.period_end >= DAY and (current.period_end - current.period_start).days <= 6


def test_wrong_api_configuration_and_foreign_cursor_rejected():
    for urls in [[API_BASE + '/notas/02-11-2026'], [API_BASE, API_BASE], ['https://sidofqa.segob.gob.mx/dof/sidof']]:
        with pytest.raises(CollectionError):
            collect('sidof', urls, DAY, DAY, fetcher=lambda _: None)
    with pytest.raises(HTTPException): validate_source_urls('sidof', [API_BASE + '/notas'])
    with pytest.raises(CollectionError): daily(Service(), cursor={'mode':'html', 'start':str(DAY), 'end':str(DAY)})


@pytest.fixture
def state(tmp_path):
    engine = create_engine(f'sqlite:///{tmp_path / "daily.db"}')
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine, expire_on_commit=False)() as db:
        source = Source(name='SIDOF controlado', kind='sidof', urls=[API_BASE])
        db.add(source); db.commit()
        yield db, source, LocalEvidenceStore(tmp_path / 'evidence')
    engine.dispose()


def test_job_audits_repeat_evidence_and_unresolved_coverage(state, monkeypatch):
    db, source, store = state
    service = Service(); service.note(1); service.note(2, None)
    service.details['2']['cadenaContenido'] = None
    collector = lambda *args, **kwargs: daily(service)
    monkeypatch.setattr(verification, 'run_once', lambda *args, **kwargs: run_once(*args, collector=collector, **kwargs))
    first = verification.verify_sources(db, store, DAY, DAY, {'sidof':['DOF:1']})
    second = verification.verify_sources(db, store, DAY, DAY, {'sidof':['DOF:1']})
    assert first['technical_passed'] and second['technical_passed']
    assert not first['coverage_verified'] and not first['passed']
    assert second['sources'][0]['versions_added'] == 0
    assert second['sources'][0]['unresolved_ids'] == ['DOF:2']
    assert second['sources'][0]['evidence'] == first['sources'][0]['evidence']
    assert db.scalar(select(func.count(Publication.id))) == 1
    assert db.scalar(select(func.count(Version.id))) == 1
    assert db.scalar(select(func.count(Audit.id)).where(Audit.action == 'revisar_indice_diario')) == 2


def test_empty_inventory_without_checked_dates_is_not_daily_acceptance(state, monkeypatch):
    db, _, store = state
    monkeypatch.setattr(verification, 'run_once', lambda *args, **kwargs: run_once(*args,
        collector=lambda *a, **kw: Batch([], True, None, 'Controlado sin índice'), **kwargs))
    report = verification.verify_sources(db, store, DAY, DAY, {'sidof':[]})
    assert not report['technical_passed'] and not report['coverage_verified']
    assert report['sources'][0]['missing_index_dates'] == [str(DAY)]


def test_upgrade_preserves_history_disabled_schedule_and_custom_settings(state):
    db, source, store = state
    source.urls = ['https://sidof.segob.gob.mx/notas/docFuente/5758923']
    source.expected_terms = ['NOM-014-ENER-2025']
    source.schedule_enabled = False
    source.schedule_start = DAY - timedelta(days=30)
    source.frequency_hours = 6
    service = Service(); service.note(1)
    doc = daily(service).documents[0]
    ingest_document(db, source, doc, store); db.commit()
    assert cli.upgrade_sidof_source(db)
    assert source.urls == [API_BASE] and source.frequency_hours == 6
    assert not source.schedule_enabled and source.schedule_start == DAY - timedelta(days=30)
    assert db.scalar(select(func.count(Publication.id))) == 1
    assert not cli.upgrade_sidof_source(db)
    source.urls = ['https://sidof.segob.gob.mx/notas/docFuente/9999999']
    source.expected_terms = ['NOM-014-ENER-2025']; db.commit()
    assert not cli.upgrade_sidof_source(db) and source.urls[0].endswith('9999999')


def test_configuration_change_starts_new_period_without_obsolete_cursor(state):
    db, source, store = state
    source.schedule_enabled = True; source.schedule_start = DAY
    source.urls = ['https://sidof.segob.gob.mx/notas/docFuente/5758923']; db.commit()
    previous = request_job(db, source.id, 'scheduler', DAY, DAY)
    run_once(db, storage=store, collector=lambda *a, **kw: Batch([], False, {'old':True}, 'Controlado'))
    source.urls = [API_BASE]; source.next_due_at = None; db.commit()
    current = db.get(Job, schedule_due(db, utcnow())[0])
    assert current.id != previous.id and current.continuation is None
    assert current.period_start == DAY
