"""Offline regressions against sanitized text excerpts from real captures.

    Original capture hashes and excerpt hashes are distinct. Minimal HTML was
    prepared for testing; this does not validate the original page's DOM or live
    coverage. Full raw pages are deliberately excluded from the public repository.
"""
import hashlib
import json
from datetime import date
from pathlib import Path
from types import SimpleNamespace

from app.collectors import extract_document, FetchResult
from app.matching import suggest

ROOT = Path(__file__).parent / 'fixtures' / 'official'


def test_official_captures_integrity_extraction_and_motor_proposal():
    for record in json.loads((ROOT/'provenance.json').read_text(encoding='utf-8')):
        raw=(ROOT/record['file']).read_bytes()
        assert record['fixture_type']=='sanitized_text_extract'
        assert hashlib.sha256(raw).hexdigest()==record['fixture_sha256']
        doc=extract_document(record['url'],FetchResult(raw,url=record['url']))
        assert doc.official_id==record['official_id']
        assert doc.content and doc.title.strip() and not doc.processing_note
        if record['file']=='platiica.html':
            assert doc.published_on==date(2025,6,2)
            assert doc.links
        if record['file']=='sidof.html':
            item=SimpleNamespace(keywords=[],synonyms=[],watched_norms=['NOM-014-ENER-2025'],tariff_code=None)
            assert suggest(doc.content,item)
            assert doc.published_on is None  # The source-body endpoint has no explicit publication field.
        if record['file']=='snice.html':
            assert 'Anexo 2.4.1' in doc.content and 'Normatividad' in doc.title
