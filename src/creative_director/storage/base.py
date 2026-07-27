"""Object-storage abstraction.

Media bytes live here, never in the DB. A stored object is addressed by a
`ref` string of the form ``<scheme>://<key>`` (e.g. ``local://ws1/asset2/v3.png``)
which is exactly what gets written to ``Version.output_ref``. Swapping local disk
for S3/R2 later means adding a backend with a new scheme — refs and the interface
stay the same.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class StorageError(Exception):
    pass


class ObjectStorage(ABC):
    #: URI scheme this backend owns, e.g. "local" or "s3".
    scheme: str

    def make_ref(self, key: str) -> str:
        return f"{self.scheme}://{key}"

    def key_of(self, ref: str) -> str:
        prefix = f"{self.scheme}://"
        if not ref.startswith(prefix):
            raise StorageError(f"ref {ref!r} is not a {self.scheme} ref")
        return ref[len(prefix):]

    @abstractmethod
    async def save(
        self, key: str, data: bytes, *, content_type: str = "application/octet-stream"
    ) -> str:
        """Persist bytes under `key`; return the addressable ref."""

    @abstractmethod
    async def load(self, ref: str) -> bytes:
        """Read the bytes for a ref."""

    @abstractmethod
    async def exists(self, ref: str) -> bool: ...

    @abstractmethod
    async def delete(self, ref: str) -> bool: ...
