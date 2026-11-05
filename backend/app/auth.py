from dataclasses import dataclass
from functools import lru_cache
import re
import jwt
from fastapi import Depends, Header, HTTPException
from .config import get_settings

ROLES = {"consulta": 1, "revisor": 2, "administrador": 3}


@dataclass
class Identity:
    id: str
    name: str
    role: str
    auth_mode: str


@lru_cache
def jwks_client(tenant: str):
    return jwt.PyJWKClient(
        f"https://login.microsoftonline.com/{tenant}/discovery/v2.0/keys", cache_keys=True, timeout=10
    )


def identity(authorization: str | None = Header(None), x_dev_role: str | None = Header(None)):
    settings = get_settings()
    if settings.environment in ("development", "test") and settings.dev_auth_enabled:
        role = x_dev_role or settings.dev_default_role
        if role not in ROLES:
            raise HTTPException(403, "Rol local desconocido")
        return Identity(f"dev:{role}", f"Usuario local ({role})", role, "development")
    if settings.auth_mode == "portal":
        return Identity("portal", "Lector del boletín", "consulta", "portal")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            401, "Se requiere un token de Microsoft Entra ID", headers={"WWW-Authenticate": "Bearer"}
        )
    if not re.fullmatch(r"[a-fA-F0-9-]{36}", settings.entra_tenant_id):
        raise HTTPException(503, "Autenticación Entra ID no configurada")
    try:
        token = authorization[7:]
        key = jwks_client(settings.entra_tenant_id).get_signing_key_from_jwt(token).key
        claims = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            audience=settings.entra_audience,
            issuer=f"https://login.microsoftonline.com/{settings.entra_tenant_id}/v2.0",
            options={"require": ["exp", "iat", "iss", "aud", "sub", "tid"]},
        )
        if claims["tid"] != settings.entra_tenant_id:
            raise jwt.InvalidTokenError("Tenant inválido")
        roles = [r for r in claims.get("roles", []) if r in ROLES]
        if not roles:
            raise HTTPException(403, "No hay un rol asignado a esta identidad")
        role = max(roles, key=lambda r: ROLES[r])
        return Identity(claims.get("oid", claims["sub"]), claims.get("name", claims["sub"]), role, "entra")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            401, "Token inválido o identidad no verificable", headers={"WWW-Authenticate": "Bearer"}
        )


def require_role(minimum: str):
    def check(user: Identity = Depends(identity)):
        if ROLES[user.role] < ROLES[minimum]:
            raise HTTPException(403, "Permisos insuficientes")
        return user

    return check
