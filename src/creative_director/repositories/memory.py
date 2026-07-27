"""In-memory backend.

Backs tests and the default keyless dev run. Stores deep copies so callers can
never mutate persisted state by holding onto a returned object.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TypeVar

from ..domain.models import Entity
from .base import Repository

T = TypeVar("T", bound=Entity)


def _utcnow() -> datetime:
    return datetime.now(UTC)


class MemoryRepository(Repository[T]):
    def __init__(self, model: type[T]) -> None:
        self._model = model
        self._store: dict[str, T] = {}

    def _scoped(self, entity: T | None, workspace_id: str | None) -> T | None:
        if entity is None:
            return None
        if workspace_id is not None and getattr(entity, "workspace_id", None) != workspace_id:
            return None
        return entity

    async def create(self, entity: T) -> T:
        self._store[entity.id] = entity.model_copy(deep=True)
        return entity.model_copy(deep=True)

    async def get(self, id: str, *, workspace_id: str | None = None) -> T | None:
        entity = self._scoped(self._store.get(id), workspace_id)
        return entity.model_copy(deep=True) if entity else None

    async def list(
        self, *, workspace_id: str | None = None, filters: dict | None = None
    ) -> list[T]:
        items = list(self._store.values())
        if workspace_id is not None:
            items = [e for e in items if getattr(e, "workspace_id", None) == workspace_id]
        for key, value in (filters or {}).items():
            items = [e for e in items if getattr(e, key, None) == value]
        items.sort(key=lambda e: e.created_at)
        return [e.model_copy(deep=True) for e in items]

    async def update(
        self, id: str, changes: dict, *, workspace_id: str | None = None
    ) -> T | None:
        current = self._scoped(self._store.get(id), workspace_id)
        if current is None:
            return None
        data = current.model_dump()
        data.update(changes)
        data["updated_at"] = _utcnow()
        updated = self._model(**data)
        self._store[id] = updated
        return updated.model_copy(deep=True)

    async def delete(self, id: str, *, workspace_id: str | None = None) -> bool:
        if self._scoped(self._store.get(id), workspace_id) is None:
            return False
        del self._store[id]
        return True
