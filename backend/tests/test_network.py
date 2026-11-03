"""Corporate certificate support and useful errors without credentials in reports."""
import socket
import ssl

import httpx
import pytest

from app import network
from app.collectors import CollectionError, SafeFetcher, validate_url
from app.diagnostics import check_url


BASE = 'https://www.dof.gob.mx/index.php'


def test_default_tls_context_keeps_system_store_and_verifies_hosts(monkeypatch):
    for key in ('SSL_CERT_FILE', 'SSL_CERT_DIR'):
        monkeypatch.delenv(key, raising=False)
    original = ssl.create_default_context
    calls = []
    def context(**kwargs):
        calls.append(kwargs)
        return original(**kwargs)
    monkeypatch.setattr(network.ssl, 'create_default_context', context)
    result = network.verified_tls_context()
    assert calls == [{}]  # No cafile override: system certificates are loaded.
    assert result.verify_mode == ssl.CERT_REQUIRED and result.check_hostname
    assert result.cert_store_stats()['x509_ca'] > 0


def test_bad_explicit_ca_is_not_silently_ignored(monkeypatch, tmp_path):
    private_path = tmp_path / 'PRIVATE-CA-PATH.pem'
    monkeypatch.setenv('SSL_CERT_FILE', str(private_path))
    with pytest.raises(CollectionError, match='TLS_CONFIGURATION') as error:
        SafeFetcher(resolve_dns=False)
    assert str(private_path) not in str(error.value)


@pytest.mark.parametrize('exception, code', [
    (httpx.ConnectError('CERTIFICATE_VERIFY_FAILED https://user:PRIVATE_SECRET@proxy.test'), 'TLS_CERTIFICATE'),
    (httpx.ProxyError('407 Proxy Authentication Required user:PRIVATE_SECRET'), 'PROXY_AUTH'),
    (httpx.ProxyError('Proxy unavailable user:PRIVATE_SECRET'), 'PROXY_CONNECT'),
    (httpx.ConnectTimeout('PRIVATE_SECRET'), 'CONNECT_TIMEOUT'),
    (httpx.ReadTimeout('PRIVATE_SECRET'), 'READ_TIMEOUT'),
])
def test_collection_errors_are_classified_and_do_not_expose_exception_text(exception, code):
    calls = []
    def respond(request):
        calls.append(request)
        raise exception
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        fetcher = SafeFetcher(client=client, interval=0, resolve_dns=False, attempts=1)
        with pytest.raises(CollectionError, match=code) as error:
            fetcher(BASE)
    assert 'PRIVATE_SECRET' not in str(error.value)
    assert len(calls) == 1


def test_certificate_failure_does_not_repeat_three_times():
    calls = []
    def respond(request):
        calls.append(request)
        raise httpx.ConnectError('CERTIFICATE_VERIFY_FAILED')
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        with pytest.raises(CollectionError, match='TLS_CERTIFICATE'):
            SafeFetcher(client=client, interval=0, resolve_dns=False)(BASE)
    assert len(calls) == 1


def test_dns_failure_retains_its_category_without_private_details(monkeypatch):
    def fail(*args, **kwargs):
        raise socket.gaierror('PRIVATE_DNS_DETAIL')
    monkeypatch.setattr(socket, 'getaddrinfo', fail)
    with pytest.raises(CollectionError, match='DNS_ERROR') as error:
        validate_url(BASE, resolve_dns=True)
    assert 'PRIVATE_DNS_DETAIL' not in str(error.value)


def test_system_proxy_is_recognized_for_proxy_dns(monkeypatch):
    from app.config import Settings
    import app.config
    monkeypatch.setattr(network, 'getproxies', lambda: {'https':'http://user:PRIVATE_SECRET@proxy.test:8080'})
    monkeypatch.setattr(app.config, 'get_settings', lambda: Settings(_env_file=None, source_dns_mode='proxy'))
    with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(404))) as client:
        fetcher = SafeFetcher(client=client)
        assert fetcher.resolve_dns is False


def test_unexpected_diagnostic_error_is_sanitized():
    class Broken:
        def __init__(self, **kwargs):
            raise RuntimeError('https://user:PRIVATE_SECRET@proxy.test')
    report = check_url('DOF', BASE, factory=Broken)
    assert report['code'] == 'INTERNAL_ERROR'
    assert 'PRIVATE_SECRET' not in str(report)


def test_diagnostic_report_writes_json_without_proxy_or_ca_values(monkeypatch, tmp_path, capsys):
    import json
    from app import diagnostics
    monkeypatch.setenv('HTTPS_PROXY', 'http://user:PRIVATE_SECRET@proxy.test:8080')
    monkeypatch.setenv('SSL_CERT_FILE', 'PRIVATE_CA_PATH.pem')
    monkeypatch.setattr(diagnostics, 'check_url', lambda source,url: {'source':source, 'url':url, 'code':'ACCESS_OK'})
    output = tmp_path / 'diagnostic.json'
    monkeypatch.setattr('sys.argv', ['diagnostics', '--output', str(output)])
    assert diagnostics.main() == 0
    report = json.loads(output.read_text(encoding='utf-8'))
    assert len(report['results']) == 4
    assert report['tls_verification'] and report['custom_ca_configured']
    assert 'PRIVATE_SECRET' not in str(report) and 'PRIVATE_CA_PATH' not in str(report)
    assert json.loads(capsys.readouterr().out) == report
