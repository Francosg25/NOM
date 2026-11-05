from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, model_validator
from typing import Literal


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore", hide_input_in_errors=True)
    environment: str = "development"
    auth_mode: Literal["portal", "entra"] = "portal"
    database_url: str = Field("sqlite:///./data/nom.db", repr=False)
    dev_auth_enabled: bool = False
    dev_default_role: str = "consulta"
    entra_tenant_id: str = ""
    entra_audience: str = ""
    entra_client_id: str = ""
    entra_scopes: str = ""
    entra_app_service_auth: bool = False
    scheduler_enabled: bool = False
    monitor_enabled: bool = False
    source_dns_mode: Literal["local", "proxy"] = "local"
    storage_backend: Literal["local", "azure"] = "local"
    storage_path: str = "./data/evidence"
    azure_storage_account_url: str = ""
    azure_storage_container: str = "nom-evidence"
    demo_mode: bool = False
    frontend_dist: str = "../frontend/dist"

    @model_validator(mode="after")
    def validate_production(self):
        if self.environment not in ("development", "test", "production"):
            raise ValueError("ENVIRONMENT debe ser development, test o production")
        if self.dev_default_role not in ("consulta", "revisor", "administrador"):
            raise ValueError("DEV_DEFAULT_ROLE inválido")
        if self.auth_mode == "entra" and bool(self.entra_client_id) != bool(self.entra_scopes):
            raise ValueError("ENTRA_CLIENT_ID y ENTRA_SCOPES se configuran juntos")
        if self.auth_mode == "entra" and (not self.entra_tenant_id or not self.entra_audience):
            raise ValueError("Inicio de sesión requiere ENTRA_TENANT_ID y ENTRA_AUDIENCE")
        if self.storage_backend == "azure" and not self.azure_storage_account_url:
            raise ValueError("Configura AZURE_STORAGE_ACCOUNT_URL al elegir almacenamiento Azure")
        if self.environment == "production":
            if self.dev_auth_enabled or self.demo_mode:
                raise ValueError("Autenticación local y demostraciones prohibidas en producción")
        return self


@lru_cache
def get_settings():
    return Settings()
