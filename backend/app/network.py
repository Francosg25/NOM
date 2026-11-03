"""Verified TLS and safe connection errors shared by collection and diagnostics."""
from dataclasses import dataclass
import os
import socket
import ssl
from urllib.request import getproxies

import certifi
import httpx


def verified_tls_context():
    # Explicit CA settings remain authoritative. Otherwise include the system
    # store (Windows CA/ROOT included) alongside HTTPX's public CA bundle.
    if os.environ.get('SSL_CERT_FILE'):
        return ssl.create_default_context(cafile=os.environ['SSL_CERT_FILE'])
    if os.environ.get('SSL_CERT_DIR'):
        return ssl.create_default_context(capath=os.environ['SSL_CERT_DIR'])
    context = ssl.create_default_context()
    context.load_verify_locations(cafile=certifi.where())
    return context


def https_proxy_configured():
    proxies = getproxies()  # Same environment/system registry route as HTTPX.
    return bool(proxies.get('https') or proxies.get('all'))


@dataclass(frozen=True)
class NetworkIssue:
    code: str
    message: str
    retryable: bool = True


def connection_issue(exc):
    chain, current = [], exc
    while current is not None and len(chain) < 8 and all(current is not item for item in chain):
        chain.append(current)
        current = current.__cause__ or current.__context__
    # Inspect to classify only. Never return raw exception text: proxy URLs can
    # include credentials, and CA paths can include personal directory names.
    detail = ' '.join(str(item) for item in chain).upper()
    if any(isinstance(item, ssl.SSLCertVerificationError) for item in chain) or 'CERTIFICATE_VERIFY_FAILED' in detail:
        return NetworkIssue('TLS_CERTIFICATE', 'No se pudo validar el certificado HTTPS con las autoridades de confianza configuradas.', False)
    if any(isinstance(item, ssl.SSLError) for item in chain) or any(s in detail for s in ('WRONG_VERSION_NUMBER', 'SSLV3_ALERT', 'TLSV1_ALERT')):
        return NetworkIssue('TLS_HANDSHAKE', 'No se pudo establecer la conexión TLS con el sitio o el proxy.', False)
    if isinstance(exc, httpx.ProxyError):
        if '407' in detail:
            return NetworkIssue('PROXY_AUTH', 'El proxy requiere autenticación que este proceso no tiene disponible.', False)
        return NetworkIssue('PROXY_CONNECT', 'No se pudo establecer la conexión a través del proxy configurado.')
    if any(isinstance(item, socket.gaierror) for item in chain):
        return NetworkIssue('DNS_ERROR', 'No se pudo resolver el nombre del sitio oficial.')
    if isinstance(exc, httpx.ConnectTimeout):
        return NetworkIssue('CONNECT_TIMEOUT', 'Se agotó el tiempo para conectar con el sitio o el proxy.')
    if isinstance(exc, httpx.ReadTimeout):
        return NetworkIssue('READ_TIMEOUT', 'La conexión se abrió, pero el sitio no respondió a tiempo.')
    if isinstance(exc, httpx.TimeoutException):
        return NetworkIssue('TIMEOUT', 'La consulta agotó el tiempo de espera.')
    return NetworkIssue('NETWORK_CONNECT', 'No se pudo completar la conexión de red con el sitio oficial.')
