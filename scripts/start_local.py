"""Launch the current compiled portal and open it only after the matching API is ready."""
from hashlib import sha256
import json
import os
from pathlib import Path
import socket
import sys
from threading import Thread
import time
from urllib.request import build_opener, ProxyHandler
import webbrowser

ROOT = Path(__file__).resolve().parents[1]


def verify_frontend(root=ROOT):
    frontend = root / 'frontend'
    manifest_path = frontend / 'dist' / 'portal-release.json'
    if not manifest_path.is_file() or not (frontend / 'dist' / 'index.html').is_file():
        raise ValueError('Falta la interfaz actual. Ejecuta ACTUALIZAR_INTERFAZ.cmd y vuelve a iniciar.')
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    files = ['index.html', 'package.json', 'package-lock.json', 'tsconfig.json', 'vite.config.ts']
    files.extend(p.relative_to(frontend).as_posix() for p in (frontend / 'src').rglob('*') if p.is_file())
    digest = sha256()
    for name in sorted(files):
        digest.update((name + '\0').encode())
        digest.update((frontend / name).read_text(encoding='utf-8').replace('\r\n', '\n').encode())
        digest.update(b'\0')
    if digest.hexdigest() != manifest.get('source_sha256'):
        raise ValueError('El codigo de la interfaz cambio, pero la compilacion es anterior. Ejecuta ACTUALIZAR_INTERFAZ.cmd antes de iniciar.')
    return manifest


def start():
    try:
        release = verify_frontend()
    except (OSError, ValueError) as exc:
        print(f'\nNo se inicio el portal: {exc}', flush=True)
        return 1
    host, port = '127.0.0.1', int(os.environ.get('NOM_LOCAL_PORT', '8000'))
    with socket.socket() as probe:
        try:
            probe.bind((host, port))
        except OSError:
            print(f'\nEl puerto {port} ya esta ocupado. Cierra el portal anterior con Ctrl+C en su consola y vuelve a ejecutar INICIAR_LOCAL.cmd. No se abrio otra version.', flush=True)
            return 1
    os.environ.update(ENVIRONMENT='development', AUTH_MODE='portal', MONITOR_ENABLED='true', SCHEDULER_ENABLED='true', FRONTEND_DIST=str(ROOT / 'frontend' / 'dist'))
    os.environ.setdefault('DEV_AUTH_ENABLED', 'true')
    os.environ.setdefault('DEV_DEFAULT_ROLE', 'administrador')
    os.chdir(ROOT / 'backend')
    sys.path.insert(0, str(ROOT / 'backend'))
    url = f'http://{host}:{port}'
    print(f'\nNOM Monitor v{release["version"]} | {url}\nEspa\u00f1ol / English esta en la parte superior. Cierra con Ctrl+C.\n', flush=True)

    def open_when_ready():
        opener = build_opener(ProxyHandler({}))  # Loopback only.
        for _ in range(120):
            try:
                with opener.open(url + '/api/health', timeout=1) as response:
                    current = json.load(response).get('frontend', {})
                if current.get('source_sha256') == release['source_sha256']:
                    webbrowser.open(url)
                    return
            except (OSError, ValueError):
                pass
            time.sleep(0.5)

    Thread(target=open_when_ready, daemon=True).start()
    import uvicorn
    uvicorn.run('app.main:app', host=host, port=port)
    return 0


if __name__ == '__main__':
    raise SystemExit(start())
