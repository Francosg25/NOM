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
    settings = Settings(_env_file=None, environment='test', dev_auth_enabled=False, auth_mode='entra',
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


def test_open_portal_is_read_only_and_ignores_spoofed_role(monkeypatch):
    monkeypatch.setattr(auth, 'get_settings', lambda: Settings(_env_file=None, dev_auth_enabled=False))
    user = auth.identity(authorization=None, x_dev_role='administrador')
    assert (user.role, user.auth_mode) == ('consulta', 'portal')
    with pytest.raises(HTTPException) as error:
        auth.require_role('administrador')(user)
    assert error.value.status_code == 403


def test_optional_entra_requires_an_identity(monkeypatch):
    settings = Settings(_env_file=None, auth_mode='entra', entra_tenant_id=TENANT, entra_audience=AUDIENCE)
    monkeypatch.setattr(auth, 'get_settings', lambda: settings)
    with pytest.raises(HTTPException) as error:
        auth.identity(authorization=None, x_dev_role='administrador')
    assert error.value.status_code == 401


def test_local_auth_requires_explicit_enable(monkeypatch):
    monkeypatch.setattr(auth, 'get_settings', lambda: Settings(_env_file=None, dev_auth_enabled=True))
    assert auth.identity(authorization=None, x_dev_role='consulta').auth_mode == 'development'
    with pytest.raises(HTTPException):
        auth.identity(authorization=None, x_dev_role='superadmin')


def production_config(**overrides):
    config = dict(environment='production', database_url='sqlite:////home/nom-monitor/nom.db',
                  storage_backend='local', storage_path='/home/nom-monitor/evidence',
                  auth_mode='portal', dev_auth_enabled=False, demo_mode=False)
    config.update(overrides)
    return Settings(_env_file=None, **config)


@pytest.mark.parametrize('overrides', [
    {'dev_auth_enabled': True}, {'demo_mode': True},
    {'auth_mode': 'entra'}, {'storage_backend': 'azure'},
])
def test_production_misconfiguration_is_rejected(overrides):
    with pytest.raises(ValidationError):
        production_config(**overrides)


def test_production_portal_needs_no_cloud_database_blob_or_login():
    settings = production_config()
    assert settings.environment == 'production' and settings.auth_mode == 'portal'
    assert settings.database_url.startswith('sqlite:') and settings.storage_backend == 'local'
    assert not settings.entra_tenant_id and not settings.azure_storage_account_url


def test_cloud_adapters_remain_optional():
    assert production_config(auth_mode='entra', entra_tenant_id=TENANT,
        entra_audience=AUDIENCE, entra_app_service_auth=True).auth_mode == 'entra'
    assert production_config(storage_backend='azure',
        azure_storage_account_url='https://storage.blob.core.windows.net').storage_backend == 'azure'
