"""Regression tests for durable work, inherited rules and opt-in automation."""
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import sessionmaker

from app.collectors import Document, Batch, extract_document, FetchResult
from app.jobs import ingest_document, run_once
from app.matching import suggest
from app.models import Base, CatalogItem, Source, Alert, Publication, Job, Reevaluation, Version, utcnow
from app.operations import enqueue_reevaluation, reevaluate_batch, schedule_due, advance_schedule
from app.pilot import seed_catalog
from app.storage import LocalEvidenceStore


@pytest.fixture
def state(tmp_path):
    engine = create_engine(f'sqlite:///{tmp_path / "operations.db"}')
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine, expire_on_commit=False)() as db:
        source = Source(name='Controlado',kind='dof',urls=['https://www.dof.gob.mx/index.php'])
        db.add(source); db.commit()
        yield db, source, LocalEvidenceStore(tmp_path / 'evidence')
    engine.dispose()


def doc(id='one', text='Documento de prueba: motores eléctricos NOM-014-ENER-2025', links=None):
    return Document(id,'https://www.dof.gob.mx/nota_detalle.php?codigo=1','Muestra controlada',text,
                    date(2025,6,2),raw=text.encode(),links=links or [])


def test_catalogue_edits_are_durable_bounded_and_keep_decisions(state):
    db, source, store = state
    for i in range(3): ingest_document(db,source,doc(str(i)),store)
    db.commit()
    family = CatalogItem(kind='familia',name='Familia',keywords=['motores eléctricos'])
    db.add(family); db.flush()
    enqueue_reevaluation(db,family.id,'admin'); db.commit()
    assert db.scalar(select(func.count(Alert.id)).where(Alert.catalog_id == family.id)) == 0
    first = reevaluate_batch(db,limit=1)
    assert first['processed'] == first['created'] == 1 and not first['complete']
    task = db.scalar(select(Reevaluation)); assert task.cursor > 0
    db.expire_all()  # persisted cursor survives a new view/session
    relation = db.scalar(select(Alert).where(Alert.catalog_id == family.id))
    relation.decision='descartada';relation.status='resuelta';relation.closure_reason='Revisión controlada';db.commit()
    enqueue_reevaluation(db,family.id,'admin2');db.commit()
    while (r := reevaluate_batch(db,limit=2)) and not r['complete']: pass
    db.refresh(relation)
    assert relation.decision == 'descartada'
    assert db.scalar(select(func.count(Alert.id)).where(Alert.catalog_id == family.id)) == 3
    assert reevaluate_batch(db) is None


def test_unattended_sidof_cycles_recheck_without_duplicates_and_advance_to_next_day(state, monkeypatch):
    from app import jobs, operations
    from app.collectors.sidof import API_BASE
    db, source, store = state
    clock = {'now':datetime(2026,10,29,18,tzinfo=timezone.utc)}
    monkeypatch.setattr(jobs,'utcnow',lambda:clock['now'])
    monkeypatch.setattr(operations,'utcnow',lambda:clock['now'])
    source.kind='sidof';source.urls=[API_BASE];source.schedule_enabled=True
    source.schedule_start=date(2026,10,23);source.frequency_hours=1;db.commit()
    original=Document('CONTROLLED-OLD','https://sidof.segob.gob.mx/notas/docFuente/1',
        'Existing publication','Unchanged content',date(2026,10,29),raw=b'original')
    added=Document('CONTROLLED-NEW','https://sidof.segob.gob.mx/notas/docFuente/2',
        'Next day publication','New content',date(2026,10,30),raw=b'new')
    def collect(*args,**kwargs):
        return Batch([original] + ([added] if clock['now'].day == 30 else []),False,
            {'queue':[{'day':'2026-10-28','failed':True}]},'Controlled daily check',['2026-10-28: HTTP 404'])
    first = db.get(Job,schedule_due(db,clock['now'])[0])
    run_once(db,job_id=first.id,collector=collect,storage=store)
    assert first.new_count == 1 and first.requested_by == 'scheduler'
    assert schedule_due(db,clock['now']) == []
    clock['now'] += timedelta(hours=1)
    repeated = db.get(Job,schedule_due(db,clock['now'])[0])
    run_once(db,job_id=repeated.id,collector=collect,storage=store)
    assert repeated.new_count == repeated.modified_count == 0
    clock['now'] += timedelta(days=1)
    tomorrow = db.get(Job,schedule_due(db,clock['now'])[0])
    assert tomorrow.period_end == date(2026,10,30) and tomorrow.continuation is None
    run_once(db,job_id=tomorrow.id,collector=collect,storage=store)
    assert tomorrow.new_count == 1 and tomorrow.status == 'partial'
    assert db.scalar(select(func.count(Publication.id))) == 2
    assert db.scalar(select(func.count(Version.id))) == 2


def test_ancestor_rules_reach_products_with_traceable_origin(state):
    db, source, store = state
    f=CatalogItem(kind='familia',name='Motores',watched_norms=['NOM-014-ENER-2025'])
    db.add(f);db.flush()
    s=CatalogItem(kind='subfamilia',name='CA',parent_id=f.id)
    db.add(s);db.flush()
    p=CatalogItem(kind='producto',name='Ficha incompleta',parent_id=s.id)
    db.add(p);db.commit()
    ingest_document(db,source,doc(),store);db.commit()
    relation=db.scalar(select(Alert).where(Alert.catalog_id==p.id))
    assert relation and 'heredada de familia: Motores' in relation.reason
    assert relation.decision=='propuesta'
    enqueue_reevaluation(db,f.id,'admin');db.commit()
    assert set(db.scalars(select(Reevaluation.catalog_id)))=={f.id,s.id,p.id}


def test_link_change_is_a_new_version_even_with_same_text(state):
    db, source, store=state
    ingest_document(db,source,doc(links=['https://www.snice.gob.mx/old.pdf']),store);db.commit()
    ingest_document(db,source,doc(links=['https://www.snice.gob.mx/new.pdf']),store);db.commit()
    assert db.scalar(select(func.count(Version.id)))==2
    assert db.scalars(select(Version).order_by(Version.sequence)).all()[-1].links==['https://www.snice.gob.mx/new.pdf']


def test_schedule_opt_in_dedup_backlog_and_partial_resume(state):
    db,source,store=state
    now=utcnow();today=now.date()
    assert schedule_due(db,now)==[]
    source.schedule_enabled=True;source.schedule_start=today-timedelta(days=400);db.commit()
    ids=schedule_due(db,now);assert len(ids)==1
    job=db.get(Job,ids[0]);assert (job.period_end-job.period_start).days==365
    assert schedule_due(db,now)==[]
    collector=lambda *a,**kw:Batch([],False,{'remaining':True},'Controlado')
    partial=run_once(db,collector=collector,storage=store)
    advance_schedule(db,partial)
    ids=schedule_due(db,utcnow()+timedelta(seconds=1));assert len(ids)==1
    resumed=db.get(Job,ids[0]);assert resumed.period_start==job.period_start and resumed.continuation==partial.continuation
    # Failure backs off, rather than hammering the remote site.
    def fail(*a,**kw): raise ValueError('Fallo controlado')
    failed=run_once(db,collector=fail,storage=store);advance_schedule(db,failed)
    assert schedule_due(db,utcnow())==[]
    assert source.last_error


def test_scheduling_missing_configuration_is_visible(state):
    db,source,_=state
    source.schedule_enabled=True;db.commit()
    assert schedule_due(db)==[]
    assert 'configure URLs' in source.last_error


def test_public_pilot_catalogue_idempotent_no_invented_part_or_owner(state):
    db,_,_=state
    assert seed_catalog(db)==11
    assert seed_catalog(db)==0
    products=db.scalars(select(CatalogItem).where(CatalogItem.kind=='producto')).all()
    assert len(products)==4
    assert all(not p.part_number and not p.tariff_code and not p.owner for p in products)
    assert all(p.technical['catalog_status']=='borrador_publico' for p in products)


def test_norm_typography_and_version_are_respected():
    item=SimpleNamespace(keywords=[],synonyms=[],watched_norms=['NOM-014-ENER-2025'],tariff_code='')
    for text in ['NOM014ENER2025','NOM‑014‑ENER‑2025','NOM\u00ad014\u00adENER\u00ad2025']:
        assert suggest(text,item)
    assert not suggest('NOM-014-ENER-2004',item)


def test_explicit_platiica_date_and_sidof_identity():
    d=extract_document('https://platiica.economia.gob.mx/normalizacion/nom-014-ener-2025/',
        FetchResult(b'<main><h1>NOM</h1>Fecha de publicaci\xc3\xb3n en el DOF: 2/6/2025</main>'))
    assert d.published_on==date(2025,6,2)
    d=extract_document('https://sidof.segob.gob.mx/notas/docFuente/5758923',
        FetchResult(b'<html><body><h1>NORMA Oficial Mexicana</h1>Contenido controlado</body></html>'))
    assert d.official_id=='DOF:5758923' and not d.processing_note
    assert d.published_on is None


def test_wrong_reference_does_not_replace_official_evidence(state):
    from app.jobs import request_job
    db,source,store=state
    source.expected_terms=['NOM-014-ENER-2025'];db.commit()
    request_job(db,source.id,'tester',date(2025,6,2),date(2025,6,2))
    job=run_once(db,storage=store,collector=lambda *a,**kw:Batch([doc(text='Portal genérico sin referencia')],True,None,'Controlado'))
    assert job.status=='failed' and 'Referencia esperada' in job.error
    assert db.scalar(select(func.count(Publication.id)))==0
