"""Private evidence storage. Keys are content addressed and never public URLs."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Protocol

_KEY = re.compile(r"^sha256/[0-9a-f]{2}/[0-9a-f]{64}\.bin$")


def check_key(key: str) -> str:
    if not _KEY.fullmatch(key):
        raise ValueError("Identificador de evidencia inválido")
    return key


class EvidenceStore(Protocol):
    def put(self, raw: bytes, media_type: str) -> str: ...
    def read(self, key: str) -> bytes: ...


class LocalEvidenceStore:
    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def put(self, raw: bytes, media_type: str = "application/octet-stream") -> str:
        digest = hashlib.sha256(raw).hexdigest()
        key = f"sha256/{digest[:2]}/{digest}.bin"
        target = self.root / key
        target.parent.mkdir(parents=True, exist_ok=True)
        # Content-addressed writes are idempotent. Existing evidence is never overwritten.
        try:
            with target.open("xb") as stream:
                stream.write(raw)
        except FileExistsError:
            if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
                raise ValueError("La evidencia almacenada no coincide con su hash")
        return key

    def read(self, key: str) -> bytes:
        return (self.root / check_key(key)).read_bytes()


class AzureBlobEvidenceStore:
    def __init__(self, account_url: str, container: str):
        # Optional Azure SDKs are loaded only for the production adapter.
        from azure.identity import DefaultAzureCredential
        from azure.storage.blob import BlobServiceClient

        self.client = BlobServiceClient(account_url, credential=DefaultAzureCredential())
        self.container = self.client.get_container_client(container)

    def put(self, raw: bytes, media_type: str = "application/octet-stream") -> str:
        from azure.core.exceptions import ResourceExistsError
        from azure.storage.blob import ContentSettings

        digest = hashlib.sha256(raw).hexdigest()
        key = f"sha256/{digest[:2]}/{digest}.bin"
        try:
            self.container.upload_blob(
                key,
                raw,
                overwrite=False,
                content_settings=ContentSettings(content_type=media_type),
                metadata={"sha256": digest},
            )
        except ResourceExistsError:
            # Existing content-addressed object must have the expected integrity.
            existing = self.read(key)
            if hashlib.sha256(existing).hexdigest() != digest:
                raise ValueError("La evidencia Blob no coincide con su hash")
        return key

    def read(self, key: str) -> bytes:
        return self.container.download_blob(check_key(key)).readall()


def get_storage(settings=None) -> EvidenceStore:
    if settings is None:
        from .config import get_settings

        settings = get_settings()
    if settings.storage_backend == "azure":
        return AzureBlobEvidenceStore(settings.azure_storage_account_url, settings.azure_storage_container)
    return LocalEvidenceStore(settings.storage_path)
