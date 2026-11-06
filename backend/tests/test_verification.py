"""Acceptance must observe the current run, not reuse a historical inventory."""
from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import verification
from app.collectors import Batch, Document
from app.jobs import ingest_document, run_once
from app.models import Base, Source
from app.storage import LocalEvidenceStore

DAY = date(2025, 6, 2)


@pytest.fixture
def state(tmp_path):
    engine = create_engine(f'sqlite:///{tmp_path / "acceptance.db"}')
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine, expire_on_commit=False)() as db:
        source = Source(name='Controlado', kind='dof', urls=['https://www.dof.gob.mx/index.php'])
        db.add(source)
        db.commit()
        yield db, source, LocalEvidenceStore(tmp_path / 'evidence')
    engine.dispose()


def document(published=DAY):
    return Document('DOF:10001', 'https://www.dof.gob.mx/nota_detalle.php?codigo=10001',
                    'Muestra controlada', 'Texto de ensayo', published, raw=b'Texto de ensayo')


def controlled_collection(monkeypatch, documents):
    collector = lambda *args, **kwargs: Batch(documents, True, None, 'Muestra controlada')
    monkeypatch.setattr(verification, 'run_once', lambda *args, **kwargs: run_once(*args, collector=collector, **kwargs))


def test_historical_document_cannot_satisfy_current_inventory(state, monkeypatch):
    db, source, store = state
    ingest_document(db, source, document(), store)
    db.commit()
    controlled_collection(monkeypatch, [])
    report = verification.verify_sources(db, store, DAY, DAY, {'dof': ['DOF:10001']})
    assert not report['passed'] and not report['coverage_verified']
    assert report['sources'][0]['observed_ids'] == []
    assert report['sources'][0]['missing_ids'] == ['DOF:10001']
    assert not report['sources'][0]['evidence']


def test_repeat_observes_same_version_and_verifies_evidence_independently(state, monkeypatch):
    db, _, store = state
    controlled_collection(monkeypatch, [document()])
    first = verification.verify_sources(db, store, DAY, DAY, {'dof': ['DOF:10001']})
    second = verification.verify_sources(db, store, DAY, DAY, {'dof': ['DOF:10001']})
    assert first['passed'] and second['passed']
    assert second['sources'][0]['versions_added'] == 0
    assert first['sources'][0]['evidence'] == second['sources'][0]['evidence']
    assert first['sources'][0]['jobs'][0]['id'] != second['sources'][0]['jobs'][0]['id']


def test_download_without_manual_inventory_is_not_coverage_acceptance(state, monkeypatch):
    db, _, store = state
    controlled_collection(monkeypatch, [document()])
    report = verification.verify_sources(db, store, DAY, DAY)
    assert report['technical_passed']
    assert not report['passed'] and not report['coverage_verified']


def test_empty_inventory_only_passes_an_observed_complete_empty_day(state, monkeypatch):
    db, _, store = state
    controlled_collection(monkeypatch, [])
    assert verification.verify_sources(db, store, DAY, DAY, {'dof': []})['passed']


def test_unknown_date_cannot_pass_as_a_day_without_publications(state, monkeypatch):
    db, _, store = state
    controlled_collection(monkeypatch, [document(None)])
    report = verification.verify_sources(db, store, DAY, DAY, {'dof': []})
    assert not report['passed']
    assert report['sources'][0]['unknown_publication_dates'] == ['DOF:10001']


def test_tampered_evidence_fails_acceptance(state, monkeypatch):
    db, _, store = state
    controlled_collection(monkeypatch, [document()])
    monkeypatch.setattr(store, 'read', lambda _: b'corrupto')
    report = verification.verify_sources(db, store, DAY, DAY, {'dof': ['DOF:10001']})
    assert not report['passed']
    assert not report['sources'][0]['evidence'][0]['integrity']


@pytest.mark.parametrize('expected', [[], {'dof': 'DOF:10001'}, {'dof': [None]}, {'dof': [' ']}, {'DOF': []}])
def test_malformed_inventory_is_rejected(expected):
    with pytest.raises(ValueError):
        verification.validate_expected(expected)


def test_official_platiica_inventory_key_is_supported():
    expected = {'platiica_catalog': ['PLATIICA:NOM-037-SCT2-2020']}
    assert verification.validate_expected(expected) == expected


def test_catalog_coverage_requires_and_matches_an_independent_current_nom_inventory(tmp_path, monkeypatch):
    from app.collectors import Batch, Document, platiica_catalog

    engine = create_engine(f'sqlite:///{tmp_path / "catalog-acceptance.db"}')
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine, expire_on_commit=False)() as db:
        source = Source(
            name='PLATIICA',
            kind='platiica_catalog',
            urls=['https://platiica.economia.gob.mx/normalizacion/wp-sitemap.xml'],
        )
        db.add(source)
        db.commit()
        doc = Document(
            'PLATIICA:NOM-037-SCT2-2020',
            'https://platiica.economia.gob.mx/normalizacion/nom-037-sct2-2020/',
            'NOM-037-SCT2-2020 - Barreras',
            'Estado de la Norma: Vigente\nProducto, servicio, proceso o sistema: Carreteras',
            raw=b'<html>official-fixture</html>',
            norm_status='Vigente',
            product_scope='Carreteras',
        )
        monkeypatch.setattr(
            platiica_catalog,
            'collect_catalog',
            lambda *args, **kwargs: Batch([doc], True, None, 'Sitemap controlado'),
        )
        report = verification.verify_sources(
            db,
            LocalEvidenceStore(tmp_path / 'catalog-evidence'),
            DAY,
            DAY,
            {'platiica_catalog': [doc.official_id]},
        )
        assert report['passed'] and report['coverage_verified']
        assert report['sources'][0]['catalog_current_ids'] == [doc.official_id]
        assert report['sources'][0]['inventory_matches']
    engine.dispose()
