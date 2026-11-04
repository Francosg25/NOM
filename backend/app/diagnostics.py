"""Read-only access test for SIDOF; does not validate NOM coverage."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import argparse
import json
import os
from pathlib import Path
import platform
import re
import sys

from .collectors import CollectionError, SafeFetcher
from .config import get_settings
from .network import certificate_failure_details, https_proxy_configured, tls_backend_selected
from .collectors.sidof import API_BASE

URLS = (
    ('SIDOF', API_BASE + '/notas/' + datetime.now(ZoneInfo('America/Mexico_City')).strftime('%d-%m-%Y')),
)


def check_url(source, url, factory=SafeFetcher):
    fetcher = None
    try:
        fetcher = factory(attempts=1)
        result = fetcher(url)
        return {'source':source, 'url':url, 'code':'ACCESS_OK', 'bytes':len(result.body),
                'message':'Se recuperó la página con HTTPS verificado y respetando robots.txt. No acredita cobertura ni aplicabilidad.'}
    except CollectionError as exc:
        message = str(exc)
        match = re.search(r'\[([A-Z_]+)\]', message)
        code = match[1] if match else 'ROBOTS_PENDING' if 'robots.txt' in message else 'SOURCE_PENDING'
        return {'source':source, 'url':url, 'code':code, 'message':message,
                'certificate_failure':certificate_failure_details(exc)}
    except Exception as exc:
        return {'source':source, 'url':url, 'code':'INTERNAL_ERROR', 'error_type':type(exc).__name__,
                'message':'No se pudo ejecutar la prueba de conexión. No se incluyen mensajes internos ni credenciales.'}
    finally:
        if fetcher:
            fetcher.close()


def run_diagnostics():
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda item: check_url(*item), URLS))
    return {'checked_at':datetime.now(timezone.utc).isoformat(), 'python':platform.python_version(),
            'system':platform.system(), 'dns_mode':get_settings().source_dns_mode,
            'https_proxy_configured':https_proxy_configured(),
            'custom_ca_configured':bool(os.environ.get('SSL_CERT_FILE') or os.environ.get('SSL_CERT_DIR')),
            'tls_backend_selected':tls_backend_selected(),
            'tls_verification':True, 'results':results,
            'scope':'Prueba de acceso a la API oficial SIDOF; no cambia la base, las fuentes, el proxy ni los certificados del equipo. No valida cobertura completa de NOM.'}


def main():
    parser = argparse.ArgumentParser(description='Diagnóstico de acceso HTTPS a las fuentes NOM')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    report = run_diagnostics()
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + '\n', encoding='utf-8')
    print(payload)
    return 0 if all(item['code'] == 'ACCESS_OK' for item in report['results']) else 2


if __name__ == '__main__':
    sys.exit(main())
