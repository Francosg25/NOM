"""API behavior against a real SQLite file, without network or fabricated official data."""
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app import auth, main
from app.config import Settings
from app.db import get_db
from app.models import Alert, Audit, Base, CatalogItem, Job, Publication, Source, Version
from app.storage import LocalEvidenceStore


ADMIN = {'X-Dev-Role': 'administrador'}
REVIEWER = {'X-Dev-Role': 'revisor'}
READER = {'X-Dev-Role': 'consulta'}


@pytest.fixture
def api(tmp_path, monkeypatch):
    engine = create_engine(f'sqlite:///{tmp_path / "api.db"}', connect_args={'check_same_thread': False})
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    settings = Settings(_env_file=None, environment='test', dev_auth_enabled=True,
                        database_url=f'sqlite:///{tmp_path / "api.db"}', storage_path=str(tmp_path / 'evidence'))
    monkeypatch.setattr(auth, 'get_settings', lambda: settings)
    monkeypatch.setattr(main, 'get_settings', lambda: settings)

    def database():
        with sessions() as session:
            yield session

    main.app.dependency_overrides[get_db] = database
    store = LocalEvidenceStore(tmp_path / 'evidence')
    import app.storage
    monkeypatch.setattr(app.storage, 'get_storage', lambda: store)
    with TestClient(main.app) as client:
        yield client, sessions, settings, store
    main.app.dependency_overrides.clear()
    engine.dispose()


def seed(sessions, *, demo=False):
    with sessions() as db:
        source = Source(name='Fuente controlada', kind='dof', urls=['https://www.dof.gob.mx/index.php'])
        item = CatalogItem(name='Familia de ensayo', kind='familia', keywords=['ensayo'], is_demo=demo)
        db.add_all([source, item]); db.flush()
        pub = Publication(source_id=source.id, official_id=f'fixture-{demo}', url='https://www.dof.gob.mx/',
                          title='Muestra controlada de prueba; no es publicación oficial', is_demo=demo,
                          published_on=date(2000, 1, 1))
        db.add(pub); db.flush()
        relation = Alert(publication_id=pub.id, catalog_id=item.id, reason='Palabra de ensayo', evidence='Texto de muestra controlada')
        general = Alert(publication_id=pub.id, reason='Relevancia por evaluar', evidence='Texto completo pendiente de evaluación')
        db.add_all([relation, general]); db.commit()
        return source.id, item.id, pub.id, relation.id, general.id


def test_empty_dashboard_and_protected_routes(api):
    client, _, _, _ = api
    assert client.get('/api/health').json()['status'] == 'ok'
    dashboard = client.get('/api/dashboard', headers=READER).json()
    assert dashboard['publications_detected'] == 0
    assert dashboard['alerts_pending'] == 0
    assert dashboard['upcoming'] == []
    assert dashboard['sources'] == []
    assert client.post('/api/catalog', headers=READER, json={'name':'Familia', 'kind':'familia'}).status_code == 403
    assert client.post('/api/catalog', headers=REVIEWER, json={'name':'Familia', 'kind':'familia'}).status_code == 403
    assert client.get('/api/audit', headers=READER).status_code == 403
    assert client.get('/api/does-not-exist', headers=READER).status_code == 404


def test_sidof_publication_filter_keeps_legacy_history_available(api):
    client, sessions, _, _ = api
    seed(sessions)
    with sessions() as db:
        source = Source(name='SIDOF',kind='sidof',urls=['https://sidof.segob.gob.mx/dof/sidof'])
        db.add(source);db.flush()
        db.add(Publication(source_id=source.id,official_id='CONTROLLED-SIDOF',title='Controlled SIDOF publication',url='https://sidof.segob.gob.mx/notas/docFuente/1'))
        db.commit()
    result = client.get('/api/publications?source_kind=sidof',headers=READER).json()
    assert result['total'] == 1 and result['items'][0]['official_id'] == 'CONTROLLED-SIDOF'
    assert client.get('/api/publications',headers=READER).json()['total'] == 2


def test_partial_download_is_reported_separately_from_full_period_success(api):
    from app.collectors import Batch, Document
    from app.jobs import request_job, run_once
    client, sessions, _, store = api
    with sessions() as db:
        source = Source(name='SIDOF',kind='sidof',urls=['https://sidof.segob.gob.mx/dof/sidof'])
        db.add(source);db.commit()
        job = request_job(db,source.id,'test',date(2026,11,1),date(2026,11,2))
        document = Document('CONTROLLED-PARTIAL','https://sidof.segob.gob.mx/notas/docFuente/1',
            'Controlled publication','Saved valid text',date(2026,11,2),raw=b'controlled')
        run_once(db,job_id=job.id,storage=store,collector=lambda *a,**kw:Batch([document],False,
            {'queue':[{'day':'2026-11-01','failed':True}]},'Controlled partial',
            ['2026-11-01: SIDOF: fecha sin índice, pero sin declaración oficial de ausencia de publicación'],
            [{'day':'2026-11-02','notes_checked':1,'selected_ids':['CONTROLLED-PARTIAL'],'unresolved':[]}]))
    result = client.get('/api/dashboard',headers=READER).json()['sources'][0]
    assert result['publication_count'] == 1 and result['last_download_at']
    assert result['last_full_review_at'] is None
    assert result['pending_dates'] == ['2026-11-01']
    assert result['recent_checked_dates'] == ['2026-11-02']
    assert result['latest_check_status'] == 'partial'


def test_dashboard_exposes_catalog_import_progress(api):
    from app.jobs import request_job

    client, sessions, _, _ = api
    with sessions() as db:
        source = Source(
            name='PLATIICA',
            kind='platiica_catalog',
            urls=['https://platiica.economia.gob.mx/normalizacion/wp-sitemap.xml'],
        )
        db.add(source)
        db.flush()
        job = request_job(db, source.id, 'scheduler', date(2026, 11, 6), date(2026, 11, 6))
        job.status = 'running'
        job.reviewed_count = 40
        job.continuation = {
            'discovered': 823,
            'skipped': 12,
            'queue': [{'url': f'https://platiica.economia.gob.mx/normalizacion/nom-{index}/'} for index in range(811)],
            'cursor': 40,
            'failed': [],
        }
        db.commit()

    result = client.get('/api/dashboard', headers=READER).json()['sources'][0]
    assert result['latest_check_status'] == 'running'
    assert result['latest_check_reviewed_count'] == 40
    assert result['catalog_discovered_count'] == 823
    assert result['catalog_unchanged_count'] == 12
    assert result['pending_items'] == 771


def test_daily_sidof_refresh_uses_seven_days_and_exposes_check_details(api):
    from app.collectors.sidof import API_BASE
    client, sessions, _, _ = api
    with sessions() as db:
        source = Source(name='SIDOF diario controlado', kind='sidof', urls=[API_BASE])
        db.add(source); db.commit(); source_id = source.id
    result = client.post('/api/refresh', headers=READER)
    assert result.status_code == 202
    job_id = result.json()['jobs'][0]
    with sessions() as db:
        job = db.get(Job, job_id)
        assert job.source_id == source_id
        assert (job.period_end - job.period_start).days == 6
        check = {'day':str(job.period_end), 'notes_checked':35, 'selected_ids':['DOF:1'],
                 'unresolved':[{'id':'DOF:2', 'url':'https://sidof.segob.gob.mx/notas/docFuente/2'}]}
        db.add(Audit(actor='test', action='revisar_indice_diario', entity_type='job', entity_id=job_id, after=check)); db.commit()
    assert client.get(f'/api/jobs/{job_id}', headers=READER).json()['index_checks'] == [check]


def test_catalog_save_enqueues_without_scanning_archive(api):
    from app.models import Reevaluation
    from app.operations import reevaluate_batch
    from sqlalchemy import event
    client,sessions,_,_=api
    _,_,pub_id,_,_=seed(sessions)
    with sessions() as db:
        version=Version(publication_id=pub_id,content='nuevo criterio',content_hash='x')
        db.add(version);db.flush();db.get(Publication,pub_id).current_version_id=version.id;db.commit()
    queries=[]
    engine=sessions.kw['bind']
    def record(conn,cursor,statement,parameters,context,many): queries.append(statement.lower())
    event.listen(engine,'before_cursor_execute',record)
    try:
        response=client.post('/api/catalog',headers=ADMIN,json={'kind':'familia','name':'Nueva','keywords':['nuevo criterio']})
    finally: event.remove(engine,'before_cursor_execute',record)
    assert response.status_code==201
    assert not any('from publications' in sql for sql in queries)
    with sessions() as db:
        assert db.scalar(select(Reevaluation).where(Reevaluation.catalog_id==response.json()['id']))
        assert reevaluate_batch(db)['created']==1
    assert client.get('/api/reevaluations',headers=READER).json()['pending']==0


def test_search_matches_models_and_current_document_content(api):
    client,sessions,_,_=api
    _,catalog_id,pub_id,_,_=seed(sessions)
    with sessions() as db:
        db.get(CatalogItem,catalog_id).model='MODEL-UNIQUE'
        version=Version(publication_id=pub_id,content='texto-unico-interno',content_hash='x')
        db.add(version);db.flush();db.get(Publication,pub_id).current_version_id=version.id;db.commit()
    assert client.get('/api/catalog?q=MODEL-UNIQUE',headers=READER).json()['total']==1
    assert client.get('/api/publications?q=texto-unico-interno',headers=READER).json()['total']==1


def test_source_schedule_requires_valid_start_and_urls(api):
    client,_,_,_=api
    source={'kind':'sidof','name':'Referencia','urls':['https://sidof.segob.gob.mx/notas/docFuente/5758923']}
    assert client.post('/api/sources',headers=ADMIN,json={**source,'schedule_enabled':True}).status_code==422
    created=client.post('/api/sources',headers=ADMIN,json=source)
    assert created.status_code==201
    enabled=client.patch(f'/api/sources/{created.json()["id"]}',headers=ADMIN,json={'schedule_enabled':True,'schedule_start':'2025-06-02'})
    assert enabled.status_code==200 and enabled.json()['schedule_enabled']
    assert client.patch(f'/api/sources/{created.json()["id"]}',headers=READER,json={'schedule_enabled':False}).status_code==403


def test_public_auth_configuration_has_no_secrets(api):
    client,_,_,_=api
    result=client.get('/api/auth/config')
    assert result.status_code==200
    assert set(result.json())=={'tenant_id','client_id','scopes','app_service','development','mode','demo_enabled'}


def test_served_frontend_reports_release_and_revalidates_html(api, tmp_path, monkeypatch):
    import json
    client, _, settings, _ = api
    settings.frontend_dist = str(tmp_path)
    manifest = {'version':'0.3.0', 'source_sha256':'test-build'}
    (tmp_path / 'portal-release.json').write_text(json.dumps(manifest), encoding='utf-8')
    (tmp_path / 'index.html').write_text('<html lang="es">Controlled UI</html>', encoding='utf-8')
    monkeypatch.setattr(main, 'dist', tmp_path)
    health = client.get('/api/health')
    assert health.json()['frontend'] == manifest
    assert health.headers['cache-control'] == 'no-store'
    assert client.get('/').headers['cache-control'] == 'no-store'


@pytest.mark.parametrize('kind,url', [
    ('dof', 'https://sidof.segob.gob.mx/notas/5758923'),
    ('dof', 'https://www.dof.gob.mx/nota_detalle.php?codigo=5758923'),
    ('platiica', 'https://platiica.economia.gob.mx/'),
    ('snice', 'https://www.snice.gob.mx/'),
])
def test_source_form_rejects_incompatible_index_or_homepage(api, kind, url):
    client, _, _, _ = api
    assert client.post('/api/sources', headers=ADMIN, json={'name':'Fuente', 'kind':kind, 'urls':[url]}).status_code == 422


def test_publication_list_query_count_does_not_grow_with_rows(api):
    from sqlalchemy import event
    client,sessions,_,_=api
    source_id,_,_,_,_=seed(sessions)
    with sessions() as db:
        for i in range(30):
            db.add(Publication(source_id=source_id,official_id=f'perf-{i}',url='',title=f'Muestra {i}'))
        db.commit()
    engine=sessions.kw['bind'];counts=[]
    def record(*args): counts.append(1)
    event.listen(engine,'before_cursor_execute',record)
    try:
        assert client.get('/api/publications?page_size=25',headers=READER).json()['total']==31
    finally: event.remove(engine,'before_cursor_execute',record)
    assert len(counts)<=5


def test_catalog_hierarchy_incomplete_data_soft_disable_and_audit(api):
    client, sessions, _, _ = api
    family = client.post('/api/catalog', headers=ADMIN, json={'kind':'familia','name':'Ventilación'}).json()
    assert family['missing_fields'] == ['owner', 'description']
    sub = client.post('/api/catalog', headers=ADMIN, json={'kind':'subfamilia','name':'Industrial','parent_id':family['id']}).json()
    product = client.post('/api/catalog', headers=ADMIN, json={'kind':'producto','name':'Unidad configurable','parent_id':sub['id'],
                           'keywords':['ventilación'],'synonyms':['aire'],'watched_norms':['NOM-PRUEBA']}).json()
    assert set(product['missing_fields']) >= {'model', 'part_number', 'tariff_code', 'nico', 'technical'}
    bad = client.patch(f'/api/catalog/{product["id"]}', headers=ADMIN, json={'parent_id':family['id']})
    assert bad.status_code == 422
    assert client.patch(f'/api/catalog/{family["id"]}', headers=ADMIN, json={'kind':'producto'}).status_code == 422
    disabled = client.patch(f'/api/catalog/{product["id"]}', headers=ADMIN, json={'active':False})
    assert disabled.status_code == 200 and not disabled.json()['active']
    assert client.get('/api/catalog?active=true', headers=READER).json()['total'] == 2
    with sessions() as db:
        assert db.get(CatalogItem, product['id']) is not None
        changes = db.scalars(select(Audit).where(Audit.entity_type == 'catalog').order_by(Audit.id)).all()
        assert len(changes) == 4
        assert all(row.actor == 'dev:administrador' for row in changes)
        assert changes[-1].before['active'] is True and changes[-1].after['active'] is False


def test_alert_review_comments_confirmation_discard_and_audit_history(api):
    client, sessions, _, _ = api
    _, _, publication_id, relation_id, general_id = seed(sessions)
    endpoint = f'/api/alerts/{relation_id}'
    assert client.patch(endpoint, headers=READER, json={'status':'en_revision'}).status_code == 403
    assert client.post(endpoint + '/comments', headers=READER, json={'text':'No autorizado'}).status_code == 403
    assert client.patch(endpoint, headers=REVIEWER, json={'decision':'confirmada'}).status_code == 422
    assert client.patch(f'/api/alerts/{general_id}', headers=REVIEWER,
                        json={'decision':'confirmada','closure_reason':'No debe confirmar aplicabilidad general'}).status_code == 422
    assert client.patch(endpoint, headers=REVIEWER, json={'status':'en_revision','assigned_to':'responsable@empresa'}).status_code == 200
    comment = client.post(endpoint + '/comments', headers=REVIEWER, json={'text':'  Cotejado con la evidencia de ensayo.  '})
    assert comment.status_code == 201
    assert comment.json()['author'] == 'dev:revisor'
    assert client.post(endpoint + '/comments', headers=REVIEWER, json={'text':'   '}).status_code == 422
    confirmed = client.patch(endpoint, headers=REVIEWER, json={'status':'resuelta','decision':'confirmada',
                             'closure_reason':'Revisor confirma relación según muestra; no decide importación.'})
    assert confirmed.status_code == 200
    assert confirmed.json()['decided_by'] == 'dev:revisor' and confirmed.json()['decided_at']
    metadata = client.patch(endpoint, headers=ADMIN, json={'assigned_to':'otra-persona@empresa'})
    assert metadata.status_code == 200
    assert metadata.json()['decided_by'] == confirmed.json()['decided_by']
    assert metadata.json()['decided_at'] == confirmed.json()['decided_at']
    discarded = client.patch(endpoint, headers=ADMIN, json={'decision':'descartada','closure_reason':'Nueva revisión descarta la relación.'})
    assert discarded.status_code == 200 and discarded.json()['decided_by'] == 'dev:administrador'
    detail = client.get(endpoint, headers=READER).json()
    assert detail['evidence'] == 'Texto de muestra controlada'
    assert len(detail['comments']) == 1
    assert client.get(f'/api/publications/{publication_id}', headers=READER).json()['alerts']
    with sessions() as db:
        changes = db.scalars(select(Audit).where(Audit.action == 'revisar_relacion').order_by(Audit.id)).all()
        assert changes[-1].before['decision'] == 'confirmada'
        assert changes[-1].after['decision'] == 'descartada'
        assert changes[-1].before['decided_by'] == 'dev:revisor'


def test_manual_relation_proposal_requires_evidence_and_preserves_separation(api):
    client, sessions, _, _ = api
    _, _, pub_id, _, _ = seed(sessions)
    with sessions() as db:
        item = CatalogItem(name='Otra familia de ensayo', kind='familia')
        inactive = CatalogItem(name='Familia inactiva', kind='familia', active=False)
        demo = CatalogItem(name='Familia DEMO', kind='familia', is_demo=True)
        db.add_all([item, inactive, demo]); db.commit()
        item_id, inactive_id, demo_id = item.id, inactive.id, demo.id
    body = {'publication_id':pub_id, 'catalog_id':item_id, 'reason':'Revisión humana de alcance',
            'evidence':'Párrafo de la muestra controlada que justifica la propuesta.'}
    assert client.post('/api/alerts', headers=READER, json=body).status_code == 403
    assert client.post('/api/alerts', headers=REVIEWER, json={**body, 'evidence':' '}).status_code == 422
    assert client.post('/api/alerts', headers=REVIEWER, json={**body, 'catalog_id':inactive_id}).status_code == 422
    assert client.post('/api/alerts', headers=REVIEWER, json={**body, 'catalog_id':demo_id}).status_code == 422
    result = client.post('/api/alerts', headers=REVIEWER, json=body)
    assert result.status_code == 201
    assert result.json()['decision'] == 'propuesta' and result.json()['decided_by'] is None
    assert result.json()['evidence'] == body['evidence']
    assert client.post('/api/alerts', headers=REVIEWER, json=body).status_code == 409
    with sessions() as db:
        event = db.scalar(select(Audit).where(Audit.action == 'proponer_relacion'))
        assert event.actor == 'dev:revisor' and event.after['evidence'] == body['evidence']


@pytest.mark.parametrize('url', ['http://169.254.169.254/latest/meta-data/', 'https://127.0.0.1/',
                                'https://www.dof.gob.mx.attacker.invalid/', 'https://user:pass@www.dof.gob.mx/',
                                'https://www.dof.gob.mx:8443/', 'file:///etc/passwd', 'https://www.snice.gob.mx/'])
def test_source_rejects_arbitrary_network_destinations(api, url):
    client, _, _, _ = api
    response = client.post('/api/sources', headers=ADMIN, json={'name':'Fuente', 'kind':'dof', 'urls':[url]})
    assert response.status_code == 422


@pytest.mark.parametrize('field', ['urls', 'frequency_hours', 'active', 'coverage'])
def test_source_null_fields_are_validation_errors(api, field):
    client, _, _, _ = api
    assert client.post('/api/sources', headers=ADMIN, json={'name':'Fuente','kind':'dof',field:None}).status_code == 422


def test_persistent_job_request_no_in_memory_execution_and_duplicates(api):
    client, sessions, _, _ = api
    source_id, _, _, _, _ = seed(sessions)
    body = {'source_id':source_id,'period_start':'2020-01-01','period_end':'2020-01-02'}
    assert client.post('/api/jobs', headers=READER, json=body).status_code == 403
    first = client.post('/api/jobs', headers=REVIEWER, json=body)
    assert first.status_code == 202 and first.json()['status'] == 'queued'
    second = client.post('/api/jobs', headers=REVIEWER, json=body)
    assert second.json()['id'] == first.json()['id']
    assert client.get('/api/jobs/' + first.json()['id'], headers=READER).json()['runs'] == []
    # New sessions see the durable job; no network work was launched in the request.
    with sessions() as db:
        from app.models import Job
        assert db.get(Job, first.json()['id']).status == 'queued'
    assert client.post('/api/jobs', headers=REVIEWER, json={**body,'period_end':'2019-12-31'}).status_code == 422


def test_job_detail_retains_observed_version_after_later_updates(api):
    from app.collectors import Batch, Document
    from app.jobs import request_job, run_once
    client, sessions, _, store = api
    source_id, _, _, _, _ = seed(sessions)
    day = date(2025, 6, 2)
    with sessions() as db:
        first = request_job(db, source_id, 'tester', day, day)
        ids = [first.id]
        for content in ('Contenido A', 'Contenido B'):
            doc = Document('DOF:10001', 'https://www.dof.gob.mx/nota_detalle.php?codigo=10001',
                'Muestra de ensayo', content, day, raw=content.encode())
            run_once(db, storage=store, collector=lambda *a, **kw: Batch([doc], True, None, 'Cobertura controlada'))
            if content == 'Contenido A':
                ids.append(request_job(db, source_id, 'tester', day, day).id)
    first = client.get(f'/api/jobs/{ids[0]}', headers=READER).json()
    second = client.get(f'/api/jobs/{ids[1]}', headers=READER).json()
    assert first['coverage'] == 'Cobertura controlada'
    assert first['documents'][0]['official_id'] == 'DOF:10001'
    assert first['documents'][0]['version_id'] != second['documents'][0]['version_id']
    old_version = first['documents'][0]['version_id']
    assert client.get(f'/api/versions/{old_version}/evidence', headers=READER).content == b'Contenido A'


def test_verified_effective_dates_only_and_detection_vs_publication(api):
    client, sessions, _, _ = api
    _, _, pub_id, _, _ = seed(sessions)
    endpoint = f'/api/publications/{pub_id}'
    future = (date.today() + timedelta(days=15)).isoformat()
    initial = client.get(endpoint, headers=READER).json()
    assert initial['detected_at'] and initial['published_on'] == '2000-01-01'
    assert initial['recently_published'] is False
    assert client.patch(endpoint, headers=READER, json={'effective_on':future}).status_code == 403
    assert client.patch(endpoint, headers=REVIEWER, json={'effective_on':future}).status_code == 200
    assert client.get('/api/dashboard', headers=READER).json()['upcoming'] == []
    assert client.patch(endpoint, headers=REVIEWER, json={'effective_verified':True}).status_code == 422
    verified = client.patch(endpoint, headers=REVIEWER, json={'effective_verified':True,'effective_evidence':'Artículo transitorio de la muestra controlada.'})
    assert verified.status_code == 200
    assert len(client.get('/api/dashboard', headers=READER).json()['upcoming']) == 1
    assert client.patch(endpoint, headers=REVIEWER, json={'effective_verified':None}).status_code == 422
    assert client.patch(endpoint, headers=REVIEWER, json={'effective_on':None}).status_code == 200
    assert client.get('/api/dashboard', headers=READER).json()['upcoming'] == []
    with sessions() as db:
        evidence = db.scalar(select(Audit).where(Audit.action == 'evidencia_vigencia'))
        assert evidence.after['evidence'] == 'Artículo transitorio de la muestra controlada.'


def test_demo_records_explicitly_separated_from_official_counts_and_queries(api):
    client, sessions, settings, _ = api
    seed(sessions, demo=False)
    seed(sessions, demo=True)
    summary = client.get('/api/dashboard', headers=READER).json()
    assert summary['official_count'] == 1 and summary['demo_count'] == 1
    assert summary['alerts_pending'] == 2
    official = client.get('/api/publications', headers=READER).json()
    demos = client.get('/api/publications?is_demo=true', headers=READER).json()
    assert official['total'] == 1 and official['items'][0]['is_demo'] is False
    assert demos['total'] == 1 and demos['items'][0]['is_demo'] is True
    assert client.get('/api/alerts?is_demo=true', headers=READER).json()['total'] == 2
    assert client.post('/api/catalog', headers=ADMIN, json={'kind':'familia','name':'DEMO','is_demo':True}).status_code == 422
    settings.demo_mode = True
    assert client.post('/api/catalog', headers=ADMIN, json={'kind':'familia','name':'DEMO','is_demo':True}).status_code == 201


def test_evidence_download_requires_identity_and_cannot_execute_html(api):
    client, sessions, settings, store = api
    _, _, pub_id, _, _ = seed(sessions)
    raw = b'<script>controlled fixture, never execute</script>'
    key = store.put(raw, 'text/html')
    with sessions() as db:
        version = Version(publication_id=pub_id, sequence=1, content='Controlled fixture',
                          content_hash='a' * 64, evidence_key=key, media_type='text/html')
        db.add(version); db.commit(); version_id = version.id
    response = client.get(f'/api/versions/{version_id}/evidence', headers=READER)
    assert response.status_code == 200 and response.content == raw
    assert response.headers['content-type'] == 'application/octet-stream'
    assert response.headers['content-disposition'].startswith('attachment;')
    assert response.headers['x-content-type-options'] == 'nosniff'
    settings.dev_auth_enabled = False
    assert client.get(f'/api/versions/{version_id}/evidence', headers=ADMIN).status_code == 200


def test_open_portal_refreshes_fixed_sources_without_editing_them(api):
    client, sessions, settings, _ = api
    settings.dev_auth_enabled = False
    source_id, _, _, _, _ = seed(sessions)
    assert client.get('/api/me').json()['role'] == 'consulta'
    assert client.get('/api/publications').status_code == 200
    assert client.patch(f'/api/sources/{source_id}', headers=ADMIN, json={'active':False}).status_code == 403
    first = client.post('/api/refresh')
    assert first.status_code == 202 and len(first.json()['jobs']) == 1
    assert client.post('/api/refresh').json()['jobs'] == first.json()['jobs']
    with sessions() as db:
        job = db.get(Job, first.json()['jobs'][0])
        assert job.period_start == job.period_end
        job.status, job.active_key = 'succeeded', None
        db.commit()
    assert client.post('/api/refresh').json()['recent_sources'] == 1


def test_bulletin_orders_by_official_date_and_filters_real_changes(api):
    client, sessions, _, _ = api
    source_id, _, original_id, _, _ = seed(sessions)
    with sessions() as db:
        old = db.get(Publication, original_id)
        unknown = Publication(source_id=source_id, official_id='undated', url='', title='Sin fecha')
        newest = Publication(source_id=source_id, official_id='recent', url='', title='Reciente', published_on=main.mexico_today())
        db.add_all([unknown, newest]); db.flush()
        version = Version(publication_id=newest.id, sequence=2, content='Un extracto\n con espacios', content_hash='a')
        db.add(version); db.flush(); newest.current_version_id = version.id
        ids = [newest.id, old.id, unknown.id]; db.commit()
    result = client.get('/api/publications?sort=published').json()['items']
    assert [item['id'] for item in result] == ids
    assert result[0]['excerpt'] == 'Un extracto con espacios' and result[0]['has_previous_versions']
    assert result[0]['has_changes'] is True
    assert client.get(f'/api/publications?published_since={main.mexico_today()}').json()['total'] == 1
    assert client.get('/api/publications?changes_only=true').json()['total'] == 1


@pytest.mark.parametrize('status,seconds,allowed', [
    ('failed', 120, True), ('partial', 120, True), ('interrupted', 120, True),
    ('failed', 20, False), ('succeeded', 120, False),
])
def test_failed_source_can_retry_after_a_minute_but_success_keeps_cooldown(api, status, seconds, allowed):
    from app.models import utcnow
    client, sessions, _, _ = api
    seed(sessions)
    previous_id = client.post('/api/refresh').json()['jobs'][0]
    with sessions() as db:
        previous = db.get(Job, previous_id)
        previous.status, previous.active_key = status, None
        previous.requested_at = utcnow() - timedelta(seconds=seconds + 600)
        previous.finished_at = utcnow() - timedelta(seconds=seconds)
        # A successful check keeps the existing 15-minute request cooldown.
        if status == 'succeeded':
            previous.requested_at = utcnow() - timedelta(seconds=seconds)
        db.commit()
    result = client.post('/api/refresh').json()
    assert bool(result['jobs']) is allowed
    if allowed:
        assert previous_id not in result['jobs']
    else:
        assert result['recent_sources'] == 1


def test_product_search_supports_mexican_tariff_codes_and_descriptions(api):
    client, sessions, _, _ = api
    with sessions() as db:
        source = Source(
            name='SIDOF controlado',
            kind='sidof',
            urls=['https://sidof.segob.gob.mx/dof/sidof'],
        )
        db.add(source)
        db.flush()
        publications = [
            Publication(
                source_id=source.id,
                official_id='CONTROLLED-TARIFF',
                url='https://sidof.segob.gob.mx/notas/docFuente/1',
                title='Publicación controlada de seguridad eléctrica',
                kind='norma_definitiva',
                published_on=date(2026, 1, 2),
            ),
            Publication(
                source_id=source.id,
                official_id='CONTROLLED-DESCRIPTION',
                url='https://sidof.segob.gob.mx/notas/docFuente/2',
                title='Publicación controlada de motores',
                kind='proyecto',
                published_on=date(2026, 1, 3),
            ),
        ]
        db.add_all(publications)
        db.flush()
        versions = [
            Version(
                publication_id=publications[0].id,
                content='Fracción arancelaria: 8501.10.01. La disposición contiene requisitos.',
                content_hash='controlled-tariff',
            ),
            Version(
                publication_id=publications[1].id,
                content='Requisitos para motor eléctrico de corriente continua utilizado en actuadores.',
                content_hash='controlled-description',
            ),
        ]
        db.add_all(versions)
        db.flush()
        for publication, version in zip(publications, versions):
            publication.current_version_id = version.id
        db.commit()

    tariff = client.post('/api/product-search', json={
        'mode': 'fraccion', 'value': '8501.10.01',
    })
    assert tariff.status_code == 200
    assert tariff.json()['total'] == 1
    assert tariff.json()['searched_publications'] == 2
    assert tariff.json()['results'][0]['match']['type'] == 'fraccion_exacta'
    assert '8501.10.01' in tariff.json()['results'][0]['match']['evidence']

    description = client.post('/api/product-search', json={
        'mode': 'descripcion', 'value': 'motor eléctrico corriente continua',
    })
    assert description.status_code == 200
    assert description.json()['total'] == 1
    assert description.json()['results'][0]['publication']['official_id'] == 'CONTROLLED-DESCRIPTION'
    assert description.json()['results'][0]['match']['matched_terms'] == [
        'motor', 'electrico', 'corriente', 'continua',
    ]

    invalid = client.post('/api/product-search', json={
        'mode': 'fraccion', 'value': '8501.10',
    })
    assert invalid.status_code == 422


def test_product_search_includes_only_current_platiica_norms_and_reports_sync(api):
    client, sessions, _, _ = api
    with sessions() as db:
        source = Source(
            name='Catálogo PLATIICA',
            kind='platiica_catalog',
            urls=['https://platiica.economia.gob.mx/normalizacion/wp-sitemap.xml'],
            schedule_enabled=True,
        )
        db.add(source)
        db.flush()
        publications = [
            Publication(
                source_id=source.id,
                official_id='PLATIICA:NOM-037-SCT2-2020',
                url='https://platiica.economia.gob.mx/normalizacion/nom-037-sct2-2020/',
                title='NOM-037-SCT2-2020 - Barreras de protección',
                kind='norma_vigente',
                norm_status='Vigente',
                product_scope='Carreteras y vías urbanas',
            ),
            Publication(
                source_id=source.id,
                official_id='PLATIICA:NOM-010-STPS-1999',
                url='https://platiica.economia.gob.mx/normalizacion/nom-010-stps-1999/',
                title='NOM-010-STPS-1999 - Agentes químicos',
                kind='norma_no_vigente',
                norm_status='Cancelada',
                product_scope='Centros de trabajo',
            ),
            Publication(
                source_id=source.id,
                official_id='PLATIICA:NOM-UNKNOWN',
                url='https://platiica.economia.gob.mx/normalizacion/nom-unknown/',
                title='NOM pendiente',
                kind='norma_no_vigente',
                norm_status='Estado no informado',
            ),
        ]
        db.add_all(publications)
        db.flush()
        for index, publication in enumerate(publications):
            version = Version(
                publication_id=publication.id,
                content='Barreras de protección para carreteras y vías urbanas.',
                content_hash=f'platiica-fixture-{index}',
            )
            db.add(version)
            db.flush()
            publication.current_version_id = version.id
        db.add(
            Job(
                id='platiica-succeeded',
                source_id=source.id,
                requested_by='scheduler',
                period_start=date(2026, 1, 3),
                period_end=date(2026, 1, 3),
                status='succeeded',
            )
        )
        db.commit()

    response = client.post('/api/product-search', json={
        'mode': 'descripcion', 'value': 'barreras carreteras',
    })
    assert response.status_code == 200
    result = response.json()
    assert result['total'] == 1
    assert result['searched_publications'] == 1
    assert result['results'][0]['publication']['official_id'] == 'PLATIICA:NOM-037-SCT2-2020'
    assert result['results'][0]['publication']['norm_status'] == 'Vigente'
    assert result['results'][0]['publication']['product_scope'] == 'Carreteras y vías urbanas'
    assert result['catalog'] == {
        'records': 3,
        'current_norms': 1,
        'unresolved_status': 1,
        'missing_product_scope': 1,
        'synchronized': True,
        'last_job_status': 'succeeded',
        'last_checked_at': None,
        'pending_pages': 0,
    }


def test_tariff_lookup_returns_dated_annex_relation_without_code_in_nom_text(api):
    client, sessions, _, _ = api
    with sessions() as db:
        source = Source(name='PLATIICA controlado', kind='platiica_catalog', urls=[])
        db.add(source); db.flush()
        pub = Publication(source_id=source.id, official_id='PLATIICA:NOM-016-ENER-2016',
                          title='NOM-016-ENER-2016, motores eléctricos', url='https://platiica.economia.gob.mx/',
                          norm_status='Vigente', kind='norma_vigente')
        wrong_year = Publication(source_id=source.id, official_id='PLATIICA:NOM-016-ENER-2099',
                          title='NOM-016-ENER-2099, muestra con año distinto', url='https://platiica.economia.gob.mx/',
                          norm_status='Vigente', kind='norma_vigente')
        db.add_all([pub, wrong_year]); db.flush()
        for item in (pub, wrong_year):
            version = Version(publication_id=item.id, content='Requisitos de motores sin números arancelarios.', content_hash=f'controlled-{item.id}')
            db.add(version); db.flush(); item.current_version_id = version.id
        db.commit()
        correct_id = pub.id
    result = client.post('/api/product-search', json={'mode': 'fraccion', 'value': '8501.52.04/01'}).json()
    assert result['total'] == 0  # A documented relationship is not a textual match.
    reference = result['tariff_reference']
    assert reference['document_date'] == '2026-04-02' and reference['requested_nico'] == '01'
    assert reference['matches'][0]['nom_codes'] == ['NOM-016-ENER-2016']
    assert [item['id'] for item in reference['saved_norms']] == [correct_id]
    missing = client.post('/api/product-search', json={'mode': 'fraccion', 'value': '00000000'}).json()
    assert missing['tariff_reference']['available'] and missing['tariff_reference']['matches'] == []


def test_product_search_handles_digit_breaks_product_scope_and_exact_nico(api):
    client, sessions, _, _ = api
    with sessions() as db:
        source = Source(name='SIDOF controlado', kind='sidof', urls=[])
        db.add(source); db.flush()
        pub = Publication(source_id=source.id, official_id='CONTROLLED-SPLIT-CODE',
            title='Muestra controlada', url='https://sidof.segob.gob.mx/',
            product_scope='Materiales cerámicos para ensayo', kind='acuerdo')
        db.add(pub); db.flush()
        version = Version(publication_id=pub.id, content='Referencia 8 5 0 1. 5 2. 0 4 01. Otros números: 8 de 50 y 152 y 04.', content_hash='split-code')
        db.add(version); db.flush(); pub.current_version_id = version.id; db.commit()
    base = client.post('/api/product-search', json={'mode': 'fraccion', 'value': '8501–52–04'}).json()
    assert base['total'] == 1 and base['results'][0]['match']['type'] == 'fraccion_base'
    exact = client.post('/api/product-search', json={'mode': 'fraccion', 'value': '8501520401'}).json()
    assert exact['total'] == 1 and exact['results'][0]['match']['type'] == 'fraccion_exacta'
    wrong_nico = client.post('/api/product-search', json={'mode': 'fraccion', 'value': '8501520402'}).json()
    assert wrong_nico['results'][0]['match']['type'] == 'fraccion_base'
    description = client.post('/api/product-search', json={'mode': 'descripcion', 'value': 'cerámicos'}).json()
    assert description['total'] == 1 and description['tariff_reference'] is None


def test_alerts_can_be_filtered_for_a_tracked_product(api):
    client, sessions, _, _ = api
    _, catalog_id, _, _, _ = seed(sessions)
    result = client.get(f'/api/alerts?catalog_id={catalog_id}', headers=READER)
    assert result.status_code == 200
    assert result.json()['total'] == 1
    assert result.json()['items'][0]['catalog_id'] == catalog_id


def test_verified_calendar_run_clears_old_warning_without_calling_absence_an_index(api):
    from app.collectors import Batch
    from app.jobs import request_job, run_once

    client, sessions, _, store = api
    with sessions() as db:
        source = Source(name='SIDOF', kind='sidof', urls=['https://sidof.segob.gob.mx/dof/sidof'])
        db.add(source)
        db.commit()
        start, end = date(2026, 11, 7), date(2026, 11, 8)
        job = request_job(db, source.id, 'scheduler', start, end)
        run_once(db, job_id=job.id, storage=store, collector=lambda *a, **kw: Batch(
            [], False, {'queue': [{'day': str(start)}, {'day': str(end)}]}, 'Controlled unavailable', ['HTTP 404']))
        job = request_job(db, source.id, 'scheduler', start, end)
        checks = [{'day': str(day), 'declared_no_publication': True, 'absence_basis': 'sidof_portal_calendar',
                   'notes_checked': 0, 'selected_ids': [], 'unresolved': []} for day in (start, end)]
        run_once(db, job_id=job.id, storage=store, collector=lambda *a, **kw: Batch(
            [], True, None, 'Controlled verified calendar', checks=checks))
    result = client.get('/api/dashboard', headers=READER).json()['sources'][0]
    assert result['last_error'] is None and result['latest_check_status'] == 'succeeded'
    assert result['pending_dates'] == [] and result['recent_checked_dates'] == []
    assert result['confirmed_absence_dates'] == ['2026-11-08', '2026-11-07']


def test_reading_uses_original_inline_structure_without_mutating_saved_versions(api):
    import json

    client, sessions, _, store = api
    _, _, pub_id, _, _ = seed(sessions)
    html = '<body><p>La regulaci<span>ó</span>n conserva 40 N/mm<sup>2</sup>.</p><table><tr><td>Tipo</td><td>Valor</td></tr><tr><td>CPC</td><td>30</td></tr></table></body>'
    raw = json.dumps({'Nota': {'cadenaContenido': html}}, ensure_ascii=False).encode()
    key = store.put(raw, 'application/json')
    with sessions() as db:
        version = Version(publication_id=pub_id, sequence=1, content='La regulaci\nó\nn conserva 40 N/mm\n2.',
                          content_hash='reading-fixture', evidence_key=key, media_type='application/json')
        db.add(version)
        db.commit()
        version_id = version.id
    response = client.get(f'/api/versions/{version_id}/reading', headers=READER)
    assert response.status_code == 200
    reading = response.json()
    assert reading['version_id'] == version_id and reading['format'] == 'structured'
    assert reading['blocks'][1]['type'] == 'table'
    from app.reading import inline_text
    assert inline_text(reading['blocks'][0]['inlines']) == 'La regulación conserva 40 N/mm2.'
    with sessions() as db:
        version = db.get(Version, version_id)
        assert version.content == 'La regulaci\nó\nn conserva 40 N/mm\n2.' and version.content_hash == 'reading-fixture'
    assert client.get(f'/api/versions/{version_id}/evidence', headers=READER).content == raw
    assert client.get('/api/versions/999999/reading', headers=READER).status_code == 404


def test_missing_reading_evidence_falls_back_to_saved_content(api):
    client, sessions, _, store = api
    _, _, pub_id, _, _ = seed(sessions)
    key = store.put(b'temporary test evidence', 'text/html')
    with sessions() as db:
        version = Version(publication_id=pub_id, sequence=1, content='Texto conservado. 3.5. CPC.',
                          content_hash='reading-missing', evidence_key=key, media_type='text/html')
        db.add(version)
        db.commit()
        version_id = version.id
    (store.root / key).unlink()
    result = client.get(f'/api/versions/{version_id}/reading', headers=READER)
    assert result.status_code == 200 and result.json()['format'] == 'plain'
    assert result.json()['blocks'][0]['inlines'][0]['text'] == 'Texto conservado. 3.5. CPC.'


def test_publication_delivers_its_formatted_latest_version_and_runtime_identifies_the_reader(api):
    import json

    client, sessions, _, store = api
    _, _, pub_id, _, _ = seed(sessions)
    raw = json.dumps({'Nota': {'cadenaContenido': '<p>La regulaci<span>ó</span>n es legible.</p>'}}).encode()
    key = store.put(raw, 'application/json')
    with sessions() as db:
        for number in [1, 2]:
            db.add(Version(publication_id=pub_id, sequence=number, content='La regulaci\nó\nn es legible.',
                           content_hash=f'reader-inline-{number}', evidence_key=key, media_type='text/html; charset=UTF-8'))
        db.commit()
    response = client.get(f'/api/publications/{pub_id}', headers=READER)
    assert response.status_code == 200
    latest, previous = response.json()['versions']
    assert latest['reading']['version_id'] == latest['id'] and latest['reading']['format'] == 'structured'
    assert 'reading' not in previous
    from app.reading import inline_text
    assert inline_text(latest['reading']['blocks'][0]['inlines']) == 'La regulación es legible.'
    health = client.get('/api/health').json()
    assert health['backend'] == {'version': '0.7.4', 'document_reader': 'modal-v2'}
    policy = response.headers['content-security-policy']
    assert "img-src 'self' data: https://sidof.segob.gob.mx;" in policy
    assert "script-src 'self';" in policy and "connect-src 'self';" in policy


def test_reader_metadata_does_not_download_or_format_historical_documents(api, monkeypatch):
    client, sessions, _, store = api
    _, _, pub_id, _, _ = seed(sessions)
    raw = b'<p>Controlled preserved evidence.</p>'
    key = store.put(raw, 'text/html')
    with sessions() as db:
        for number in range(1, 13):
            version = Version(publication_id=pub_id, sequence=number, content='Controlled text. ' * 2000,
                              content_hash=str(number), evidence_key=key, media_type='text/html')
            db.add(version)
            db.flush()
        db.get(Publication, pub_id).current_version_id = version.id
        db.commit()
    monkeypatch.setattr(store, 'read', lambda _: pytest.fail('Metadata must not read evidence'))
    response = client.get(f'/api/publications/{pub_id}?include_content=false', headers=READER)
    assert response.status_code == 200
    result = response.json()
    assert len(result['versions']) == 12
    assert all('content' not in version and 'reading' not in version for version in result['versions'])
    assert len(response.content) < 10000
    assert result['versions'][0]['sequence'] == 12
    assert result['has_changes'] is True
    assert all(version['evidence_url'] for version in result['versions'])


def test_job_summaries_leave_the_saved_import_queue_available_in_detail(api):
    client, sessions, _, _ = api
    source_id, *_ = seed(sessions)
    queue = [{'url': 'https://controlled.invalid/record/' + str(i)} for i in range(823)]
    with sessions() as db:
        db.add(Job(id='controlled-heavy-queue', source_id=source_id, requested_by='test', status='partial',
                   period_start=date(2026, 11, 1), period_end=date(2026, 11, 11),
                   continuation={'queue': queue}, error_count=2, error='Controlled pending dates'))
        db.commit()
    response = client.get('/api/jobs?summary=true', headers=READER)
    assert response.status_code == 200 and len(response.content) < 2000
    summary = response.json()['items'][0]
    assert 'continuation' not in summary
    assert summary['status'] == 'partial' and summary['error_count'] == 2
    assert summary['error'] == 'Controlled pending dates'
    assert client.get('/api/jobs/controlled-heavy-queue', headers=READER).json()['continuation']['queue'] == queue


def test_dashboard_reads_index_coverage_without_loading_full_audit_documents(api):
    from sqlalchemy import event

    client, sessions, _, _ = api
    with sessions() as db:
        source = Source(name='Controlled SIDOF', kind='sidof', urls=[])
        db.add(source)
        db.flush()
        db.add(Job(id='controlled-coverage', source_id=source.id, requested_by='test', status='succeeded',
                   period_start=date(2026, 11, 6), period_end=date(2026, 11, 8)))
        db.add_all([Audit(actor='test', entity_type='job', entity_id='controlled-coverage',
                         action='revisar_indice_diario', after={'day': day, 'declared_no_publication': absent,
                         'recovered_references': [{'text': 'Controlled saved detail. ' * 2000}]})
                    for day, absent in [('2026-11-06', False), ('2026-11-07', True), ('2026-11-08', True)]])
        db.commit()
    loaded = []
    def audit_loaded(record, _):
        loaded.append(record.id)
    event.listen(Audit, 'load', audit_loaded)
    try:
        response = client.get('/api/dashboard', headers=READER)
    finally:
        event.remove(Audit, 'load', audit_loaded)
    assert response.status_code == 200
    source = response.json()['sources'][0]
    assert source['recent_checked_dates'] == ['2026-11-06']
    assert source['confirmed_absence_dates'] == ['2026-11-08', '2026-11-07']
    assert loaded == []


def bulletin_record(db, source, name, content='Controlled saved text.', demo=False):
    publication = Publication(source_id=source.id, official_id=name, title=name,
                              url='https://sidof.segob.gob.mx/', published_on=date(2000, 1, 1), is_demo=demo)
    db.add(publication); db.flush()
    bulletin_version(db, publication, content)
    return publication


def bulletin_version(db, publication, content):
    current = db.get(Version, publication.current_version_id) if publication.current_version_id else None
    version = Version(publication_id=publication.id, sequence=current.sequence + 1 if current else 1,
                      content=content, content_hash=str(len(content)) + str(current.id if current else 0))
    db.add(version); db.flush()
    publication.current_version_id = version.id
    return version


def test_visit_summary_separates_saved_arrivals_catalogue_imports_and_changed_documents(api):
    client, sessions, _, _ = api
    with sessions() as db:
        sidof = Source(name='SIDOF', kind='sidof', urls=[])
        catalog = Source(name='PLATIICA', kind='platiica_catalog', urls=[])
        db.add_all([sidof, catalog]); db.flush()
        old = bulletin_record(db, sidof, 'Already saved SIDOF')
        old_catalog = bulletin_record(db, catalog, 'Already saved catalogue')
        db.commit()
        old_id, sidof_id, catalog_id, old_catalog_id = old.id, sidof.id, catalog.id, old_catalog.id
    first = client.get('/api/bulletin/updates', headers=READER).json()
    assert first['first_visit'] and first['new_publications'] == 0 and first['new_catalog'] == 0
    cursor = first['cursor']
    with sessions() as db:
        old = db.get(Publication, old_id)
        bulletin_version(db, old, 'Version two.')
        bulletin_version(db, old, 'Version three.')
        sidof, catalog = db.get(Source, sidof_id), db.get(Source, catalog_id)
        new = bulletin_record(db, sidof, 'Old official publication found today')
        bulletin_version(db, new, 'Updated after initial capture.')
        bulletin_record(db, catalog, 'Imported catalogue record')
        bulletin_version(db, db.get(Publication, old_catalog_id), 'New catalogue copy.')
        bulletin_record(db, sidof, 'Demonstration only', demo=True)
        db.commit()
        new_id = new.id
    params = {'after_version_id': cursor['version_id'], 'anchor_hash': cursor['content_hash']}
    summary = client.get('/api/bulletin/updates', headers=READER, params=params).json()
    assert not summary['first_visit'] and not summary['reset']
    assert summary['new_publications'] == 1 and summary['changed_publications'] == 1
    assert summary['new_catalog'] == 1 and summary['changed_catalog'] == 1
    for update_type, expected in [('new', new_id), ('changed', old_id)]:
        listing = client.get('/api/publications', headers=READER, params={
            'source_kind': 'sidof', 'update_type': update_type, 'after_version_id': cursor['version_id'],
        }).json()
        assert listing['total'] == 1 and listing['items'][0]['id'] == expected
        assert listing['items'][0]['published_on'] == '2000-01-01'


def test_visit_summary_reads_metadata_only_and_recovers_from_an_unknown_cursor(api):
    from sqlalchemy import event
    client, sessions, _, _ = api
    with sessions() as db:
        source = Source(name='SIDOF', kind='sidof', urls=[])
        db.add(source); db.flush()
        bulletin_record(db, source, 'Large saved document', 'Long technical text. ' * 10000)
        db.commit()
    statements = []
    def capture(_connection, _cursor, statement, _parameters, _context, _many):
        statements.append(statement.lower())
    engine = sessions.kw['bind']
    event.listen(engine, 'before_cursor_execute', capture)
    try:
        result = client.get('/api/bulletin/updates', headers=READER,
                            params={'after_version_id': 9999, 'anchor_hash': 'unknown'})
    finally:
        event.remove(engine, 'before_cursor_execute', capture)
    assert result.status_code == 200 and result.json()['reset']
    assert result.json()['new_publications'] == 0
    assert len(result.content) < 2000
    import re
    assert not any(re.search(r'\bversions\.content\b', statement) for statement in statements)
    assert client.get('/api/publications?update_type=new', headers=READER).status_code == 422


def test_visit_summary_keeps_a_partial_check_distinct_from_the_last_completed_check(api):
    from datetime import datetime
    from app.models import SourceRun
    client, sessions, _, _ = api
    with sessions() as db:
        source = Source(name='SIDOF', kind='sidof', urls=[])
        db.add(source); db.flush()
        for number, status in [(1, 'succeeded'), (2, 'partial')]:
            day = date(2026, 11, number)
            job = Job(id=f'visit-{number}', source_id=source.id, status=status, requested_by='test',
                      period_start=day, period_end=day)
            db.add(job); db.flush()
            db.add(SourceRun(job_id=job.id, source_id=source.id, status=status,
                             period_start=day, period_end=day, finished_at=datetime(2026, 11, number)))
        db.commit()
    result = client.get('/api/bulletin/updates', headers=READER).json()
    assert result['latest_check']['status'] == 'partial'
    assert result['last_complete_check']['status'] == 'succeeded'
    assert result['last_complete_check']['period_end'] == '2026-11-01'


def test_comparison_is_paginated_and_never_combines_versions_of_different_publications(api):
    client, sessions, _, _ = api
    with sessions() as db:
        source = Source(name='SIDOF', kind='sidof', urls=[])
        db.add(source); db.flush()
        pub = bulletin_record(db, source, 'Comparison fixture', ' '.join(f'Requisito {n}: 40 kg.' for n in range(35)))
        old_id = pub.current_version_id
        newer = bulletin_version(db, pub, ' '.join(f'Requisito {n}: 50 kg.' for n in range(35)))
        other = bulletin_record(db, source, 'Another publication')
        db.commit()
        publication_id, new_id, other_version = pub.id, newer.id, other.current_version_id
    path = f'/api/bulletin/publications/{publication_id}/comparison'
    params = {'from_version_id': old_id, 'to_version_id': new_id, 'page_size': 2}
    page_one = client.get(path, headers=READER, params=params)
    assert page_one.status_code == 200
    first = page_one.json()
    from sqlalchemy import event
    statements = []
    def capture(_connection, _cursor, statement, _parameters, _context, _many):
        statements.append(statement.lower())
    engine = sessions.kw['bind']
    event.listen(engine, 'before_cursor_execute', capture)
    try:
        second = client.get(path, headers=READER, params={**params, 'page': 2}).json()
    finally:
        event.remove(engine, 'before_cursor_execute', capture)
    import re
    assert not any(re.search(r'\bversions\.content\b', statement) for statement in statements)
    assert first['classification'] == 'text_changed' and first['total'] > 2
    assert len(first['items']) == len(second['items']) == 2
    assert first['items'] != second['items']
    assert client.get(path, headers=READER, params={**params, 'from_version_id': other_version}).status_code == 404
    assert client.get(path, headers=READER, params={'from_version_id': new_id, 'to_version_id': old_id}).status_code == 422
