"""Object storage abstraction: local disk now, S3/R2 later behind one interface."""

from .base import ObjectStorage, StorageError
from .factory import get_storage
from .local import LocalStorage

__all__ = ["LocalStorage", "ObjectStorage", "StorageError", "get_storage"]
