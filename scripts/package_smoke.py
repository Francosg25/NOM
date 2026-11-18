"""Exercise the extracted production ZIP, restart and restored evidence on Linux.

All data is synthetic and isolated. No external source is queried.
"""
import argparse
import hashlib
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path
from zipfile import ZipFile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('package', type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='nom-package-') as temp:
        root = Path(temp)
        app = root / 'app'
        with ZipFile(args.package) as archive:
            archive.extractall(app)
        # The production root requirements must be exactly the committed lock.
        assert (app / 'requirements.txt').read_bytes() == (app / 'backend/requirements.txt').read_bytes()
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        env = {**os.environ, 'PATH': str(Path(sys.executable).parent) + os.pathsep + os.environ['PATH'],
               'ENVIRONMENT': 'production', 'AUTH_MODE': 'portal', 'DEV_AUTH_ENABLED': 'false',
               'DEMO_MODE': 'false', 'MONITOR_ENABLED': 'true', 'SCHEDULER_ENABLED': 'false',
               'DATABASE_URL': 'sqlite:///' + str(root / 'live/nom.db'),
               'STORAGE_BACKEND': 'local', 'STORAGE_PATH': str(root / 'live/evidence'),
               'FRONTEND_DIST': str(app / 'frontend/dist'), 'PORT': str(port)}
        base = f'http://127.0.0.1:{port}'

        def get(path):
            with urllib.request.urlopen(base + path, timeout=3) as response:
                return response.read()

        def tariff_lookup():
            request = urllib.request.Request(base + '/api/product-search',
                data=json.dumps({'mode': 'fraccion', 'value': '8501.52.04/01'}).encode(),
                headers={'Content-Type': 'application/json'}, method='POST')
            with urllib.request.urlopen(request, timeout=3) as response:
                result = json.load(response)
            reference = result['tariff_reference']
            assert result['total'] == 0
            assert reference['document_date'] == '2026-04-02'
            assert reference['matches'][0]['nom_codes'] == ['NOM-016-ENER-2016']
            assert reference['requested_nico'] == '01'
            return reference['source_sha256']

        def command(*arguments):
            return subprocess.check_output([sys.executable, *arguments], cwd=app / 'backend',
                                           env=env, stderr=subprocess.STDOUT, text=True)

        def start():
            log = (root / 'server.log').open('a')
            process = subprocess.Popen(['bash', str(app / 'startup.sh')], env=env, stdout=log,
                                       stderr=subprocess.STDOUT)
            log.close()
            for _ in range(100):
                if process.poll() is not None:
                    raise RuntimeError((root / 'server.log').read_text())
                try:
                    if json.loads(get('/api/ready'))['status'] == 'ready':
                        return process
                except OSError:
                    pass
                time.sleep(0.1)
            stop(process)
            raise RuntimeError('Package startup did not become ready')

        def stop(process):
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)

        process = start()
        try:
            assert json.loads(get('/api/health'))['frontend']['version'] == '0.7.5'
            assert '<html' in get('/').decode()
            reference_hash = tariff_lookup()
            command('-c', "from app.db import SessionLocal; from app.jobs import ingest_document; "
                "from app.models import Source; from app.collectors import Document; "
                "from app.storage import get_storage; from sqlalchemy import select; "
                "db=SessionLocal(); source=db.scalar(select(Source).where(Source.kind=='sidof')); "
                "ingest_document(db,source,Document('PACKAGE-CONTROLLED','https://sidof.segob.gob.mx/',"
                "'Controlled package sample NOM-016-ENER-2016','Not an official publication',raw=b'package-evidence'),get_storage()); "
                "db.commit(); db.close()")
            checkpoint = json.loads(get('/api/bulletin/updates'))['cursor']
            command('-c', "from app.db import SessionLocal; from app.jobs import ingest_document; "
                "from app.models import Source; from app.collectors import Document; "
                "from app.storage import get_storage; from sqlalchemy import select; "
                "db=SessionLocal(); source=db.scalar(select(Source).where(Source.kind=='sidof')); "
                "ingest_document(db,source,Document('PACKAGE-CONTROLLED','https://sidof.segob.gob.mx/',"
                "'Controlled package sample NOM-016-ENER-2016','Not an official publication. Revised sample.',raw=b'package-evidence-revised'),get_storage()); "
                "db.commit(); db.close()")
            changes = json.loads(get('/api/bulletin/updates?after_version_id=' + str(checkpoint['version_id']) +
                                     '&anchor_hash=' + checkpoint['content_hash']))
            assert changes['new_publications'] == 0 and changes['changed_publications'] == 1
            before = json.loads(command('-m', 'app.deployment_check', '--url', base, '--version', '0.7.5',
                                        '--output', str(root / 'before.json')))
            assert before['passed'] and before['sample']['sha256'] == hashlib.sha256(b'package-evidence-revised').hexdigest()
            details = json.loads(get('/api/publications/' + str(before['sample']['publication_id']) + '?include_content=false'))
            history_path = '/api/history/publications/' + str(details['id'])
            history = json.loads(get(history_path))
            assert history['selected_norm_code'] == 'NOM-016-ENER-2016' and history['total'] == 1
            assert history['items'][0]['reference_location'] == 'title' and history['items'][0]['excerpt'] == ''
            assert json.loads(get('/api/history/coverage'))['total'] == 1
            assert len(details['versions']) == 2 and all('content' not in version for version in details['versions'])
            comparison_path = '/api/bulletin/publications/' + str(details['id']) + '/comparison?from_version_id=' + str(details['versions'][1]['id']) + '&to_version_id=' + str(details['versions'][0]['id'])
            assert json.loads(get(comparison_path))['classification'] == 'text_changed'
            reading_path = '/api/versions/' + str(before['sample']['version_id']) + '/reading'
            reading = json.loads(get(reading_path))
            assert reading['blocks'][0]['inlines'][0]['text'] == 'Not an official publication. Revised sample.'
            stop(process)
            process = start()
            after = json.loads(command('-m', 'app.deployment_check', '--url', base, '--version', '0.7.5',
                '--baseline', str(root / 'before.json'), '--output', str(root / 'after.json')))
            assert after['passed']
            assert json.loads(get(reading_path)) == reading
            assert json.loads(get(history_path)) == history
            assert json.loads(get(comparison_path))['classification'] == 'text_changed'
            assert tariff_lookup() == reference_hash
            command('-m', 'app.cli', 'backup', '--destination', str(root / 'backup'))
            command('-m', 'app.cli', 'restore', '--source', str(root / 'backup'),
                    '--destination', str(root / 'restored'))
            stop(process)
            env.update(DATABASE_URL='sqlite:///' + str(root / 'restored/nom.db'),
                       STORAGE_PATH=str(root / 'restored/evidence'))
            process = start()
            restored = json.loads(command('-m', 'app.deployment_check', '--url', base, '--version', '0.7.5',
                '--baseline', str(root / 'before.json'), '--output', str(root / 'restored.json')))
            assert restored['passed']
            assert json.loads(get(reading_path)) == reading
            assert json.loads(get(history_path)) == history
            assert json.loads(get(comparison_path))['classification'] == 'text_changed'
            assert tariff_lookup() == reference_hash
            print('PASS: production ZIP, historical references, coverage, tariff reference, reading, summary, comparison, restart and restored evidence.')
        finally:
            stop(process)


if __name__ == '__main__':
    main()
