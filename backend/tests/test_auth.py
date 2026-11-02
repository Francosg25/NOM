"""Offline security checks: real RSA signatures, claims, and production guards."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from pydantic import ValidationError

from app import auth
from app.config import Settings


TENANT = '12345678-1234-1234-1234-123456789012'
AUDIENCE = 'api://nom-monitor'


@pytest.fixture
def signing(monkeypatch):
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    settings = Settings(_env_file=None, environment='test', dev_auth_enabled=False,
                        entra_tenant_id=TENANT, entra_audience=AUDIENCE)
    monkeypatch.setattr(auth, 'get_settings', lambda: settings)
    client = SimpleNamespace(get_signing_key_from_jwt=lambda token: SimpleNamespace(key=private.public_key()))
    monkeypatch.setattr(auth, 'jwks_client', lambda tenant: client)
    now = datetime.now(timezone.utc)
    claims = dict(sub='subject-1', oid='reviewer-1', tid=TENANT, aud=AUDIENCE,
                  iss=f'https://login.microsoftonline.com/{TENANT}/v2.0',
                  iat=now, exp=now + timedelta(minutes=5), roles=['revisor'])
    return private, claims


def authenticate(private, claims):
    token = jwt.encode(claims, private, algorithm='RS256')
    return auth.identity(authorization='Bearer ' + token, x_dev_role=None)


def test_valid_signed_identity_and_role(signing):
    private, claims = signing
    identity = authenticate(private, claims)
    assert (identity.id, identity.role, identity.auth_mode) == ('reviewer-1', 'revisor', 'entra')
    claims['roles'] = ['consulta', 'administrador']
    assert authenticate(private, claims).role == 'administrador'


@pytest.mark.parametrize('change', [
    {'aud': 'api://another-app'},
    {'iss': 'https://attacker.invalid'},
    {'tid': 'different-tenant'},
    {'exp': datetime(2001, 1, 1, tzinfo=timezone.utc)},
    {'roles': ['unknown']},
])
def test_invalid_claims_rejected(signing, change):
    private, claims = signing
    claims.update(change)
    with pytest.raises(HTTPException) as error:
        authenticate(private, claims)
    assert error.value.status_code in (401, 403)


def test_bad_signature_and_unsigned_token_rejected(signing):
    _, claims = signing
    attacker = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    with pytest.raises(HTTPException) as error:
        authenticate(attacker, claims)
    assert error.value.status_code == 401
    unsigned = jwt.encode(claims, '', algorithm='none')
    with pytest.raises(HTTPException):
        auth.identity(authorization='Bearer ' + unsigned, x_dev_role='administrador')


def test_no_anonymous_or_spoofed_local_role_by_default(monkeypatch):
    monkeypatch.setattr(auth, 'get_settings', lambda: Settings(_env_file=None, dev_auth_enabled=False))
    with pytest.raises(HTTPException) as error:
        auth.identity(authorization=None, x_dev_role='administrador')
    assert error.value.status_code == 401


def test_local_auth_requires_explicit_enable(monkeypatch):
    monkeypatch.setattr(auth, 'get_settings', lambda: Settings(_env_file=None, dev_auth_enabled=True))
    assert auth.identity(authorization=None, x_dev_role='consulta').auth_mode == 'development'
    with pytest.raises(HTTPException):
        auth.identity(authorization=None, x_dev_role='superadmin')


def production_config(**overrides):
    config = dict(environment='production', database_url='postgresql+psycopg://user:password@db.example/nom?sslmode=verify-full',
                  storage_backend='azure', azure_storage_account_url='https://storage.blob.core.windows.net',
                  entra_client_id='87654321-1234-1234-1234-123456789012',
                  entra_scopes='api://nom-monitor/access_as_user',
                  entra_tenant_id=TENANT, entra_audience=AUDIENCE, dev_auth_enabled=False, demo_mode=False)
    config.update(overrides)
    return Settings(_env_file=None, **config)


@pytest.mark.parametrize('overrides', [
    {'dev_auth_enabled': True}, {'demo_mode': True},
    {'database_url': 'sqlite:///data/nom.db'},
    {'database_url': 'postgresql+psycopg://u:p@db.example/nom'},
    {'database_url': 'postgresql+psycopg://u:p@db.example/nom?sslmode=disable'},
    {'database_url': 'postgresql+psycopg://u:p@db.example/nom?sslmode=allow'},
    {'storage_backend': 'local'}, {'entra_tenant_id': ''}, {'entra_audience': ''},
])
def test_production_misconfiguration_is_rejected(overrides):
    with pytest.raises(ValidationError):
        production_config(**overrides)


def test_production_configuration_accepts_required_services():
    assert production_config().environment == 'production'


def test_production_requires_working_login_path_configuration():
    with pytest.raises(ValidationError, match='inicio de sesión'):
        production_config(entra_client_id='', entra_scopes='')
    assert production_config(entra_client_id='', entra_scopes='', entra_app_service_auth=True).environment == 'production'
