"""Local-disk object storage.

Writes under a base directory (``.data/media`` by default, gitignored). Keys may
contain ``/`` to namespace by workspace/asset/version; parent dirs are created as
needed. Path traversal outside the base dir is rejected.
"""

from __future__ import annotations

from pathlib import Path

from .base import ObjectStorage, StorageError


class LocalStorage(ObjectStorage):
    scheme = "local"

    def __init__(self, base_dir: str | Path) -> None:
        self._base = Path(base_dir).resolve()
        self._base.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        path = (self._base / key).resolve()
        if not path.is_relative_to(self._base):
            raise StorageError(f"key {key!r} escapes the storage root")
        return path

    async def save(
        self, key: str, data: bytes, *, content_type: str = "application/octet-stream"
    ) -> str:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return self.make_ref(key)

    async def load(self, ref: str) -> bytes:
        path = self._path(self.key_of(ref))
        if not path.exists():
            raise StorageError(f"no object at {ref}")
        return path.read_bytes()

    async def exists(self, ref: str) -> bool:
        return self._path(self.key_of(ref)).exists()

    async def delete(self, ref: str) -> bool:
        path = self._path(self.key_of(ref))
        if not path.exists():
            return False
        path.unlink()
        return True
