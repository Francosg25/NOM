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
            assert json.loads(get('/api/health'))['frontend']['version'] == '0.6.0'
            assert '<html' in get('/').decode()
            command('-c', "from app.db import SessionLocal; from app.jobs import ingest_document; "
                "from app.models import Source; from app.collectors import Document; "
                "from app.storage import get_storage; from sqlalchemy import select; "
                "db=SessionLocal(); source=db.scalar(select(Source).where(Source.kind=='sidof')); "
                "ingest_document(db,source,Document('PACKAGE-CONTROLLED','https://sidof.segob.gob.mx/',"
                "'Controlled package sample','Not an official publication',raw=b'package-evidence'),get_storage()); "
                "db.commit(); db.close()")
            before = json.loads(command('-m', 'app.deployment_check', '--url', base, '--version', '0.6.0',
                                        '--output', str(root / 'before.json')))
            assert before['passed'] and before['sample']['sha256'] == hashlib.sha256(b'package-evidence').hexdigest()
            stop(process)
            process = start()
            after = json.loads(command('-m', 'app.deployment_check', '--url', base, '--version', '0.6.0',
                '--baseline', str(root / 'before.json'), '--output', str(root / 'after.json')))
            assert after['passed']
            command('-m', 'app.cli', 'backup', '--destination', str(root / 'backup'))
            command('-m', 'app.cli', 'restore', '--source', str(root / 'backup'),
                    '--destination', str(root / 'restored'))
            stop(process)
            env.update(DATABASE_URL='sqlite:///' + str(root / 'restored/nom.db'),
                       STORAGE_PATH=str(root / 'restored/evidence'))
            process = start()
            restored = json.loads(command('-m', 'app.deployment_check', '--url', base, '--version', '0.6.0',
                '--baseline', str(root / 'before.json'), '--output', str(root / 'restored.json')))
            assert restored['passed']
            print('PASS: production ZIP, real startup.sh, monitor readiness, restart and restored evidence.')
        finally:
            stop(process)


if __name__ == '__main__':
    main()
