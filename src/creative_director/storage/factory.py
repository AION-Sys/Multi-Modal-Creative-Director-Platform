"""Select an ObjectStorage backend from config."""

from __future__ import annotations

from ..config import Settings
from .base import ObjectStorage
from .local import LocalStorage


def get_storage(settings: Settings) -> ObjectStorage:
    if settings.storage_backend == "local":
        return LocalStorage(settings.storage_local_dir)
    raise ValueError(f"Unknown storage backend: {settings.storage_backend}")
