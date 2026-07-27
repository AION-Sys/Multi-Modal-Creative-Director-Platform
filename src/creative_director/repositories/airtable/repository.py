"""Airtable-backed repository.

Implements the same `Repository[T]` contract as the memory backend. Our UUID
`id` is the canonical key: mutating operations first resolve it to Airtable's
internal record id via `find_by_uuid`, keeping the rest of the app UUID-only.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TypeVar

from ...domain.models import Entity
from ..base import Repository
from .client import AirtableClient
from .mapping import from_fields, to_fields

T = TypeVar("T", bound=Entity)


def _utcnow_iso() -> str:
    return datetime.now(UTC).isoformat()


class AirtableRepository(Repository[T]):
    def __init__(self, client: AirtableClient, table: str, model: type[T]) -> None:
        self._client = client
        self._table = table
        self._model = model

    def _decode(self, record: dict) -> T:
        return from_fields(self._model, record.get("fields", {}))

    def _scoped(self, entity: T | None, workspace_id: str | None) -> T | None:
        if entity is None:
            return None
        if workspace_id is not None and getattr(entity, "workspace_id", None) != workspace_id:
            return None
        return entity

    async def create(self, entity: T) -> T:
        record = await self._client.create_record(self._table, to_fields(entity))
        return self._decode(record)

    async def get(self, id: str, *, workspace_id: str | None = None) -> T | None:
        record = await self._client.find_by_uuid(self._table, id)
        return self._scoped(self._decode(record) if record else None, workspace_id)

    async def list(
        self, *, workspace_id: str | None = None, filters: dict | None = None
    ) -> list[T]:
        formula = self._build_formula(workspace_id, filters)
        records = await self._client.list_records(self._table, filter_by_formula=formula)
        items = [self._decode(r) for r in records]
        items.sort(key=lambda e: e.created_at)
        return items

    async def update(
        self, id: str, changes: dict, *, workspace_id: str | None = None
    ) -> T | None:
        record = await self._client.find_by_uuid(self._table, id)
        if record is None or self._scoped(self._decode(record), workspace_id) is None:
            return None
        changes = {**changes, "updated_at": _utcnow_iso()}
        updated = await self._client.update_record(
            self._table, record["id"], _encode_changes(self._model, changes)
        )
        return self._decode(updated)

    async def delete(self, id: str, *, workspace_id: str | None = None) -> bool:
        record = await self._client.find_by_uuid(self._table, id)
        if record is None or self._scoped(self._decode(record), workspace_id) is None:
            return False
        return await self._client.delete_record(self._table, record["id"])

    @staticmethod
    def _build_formula(workspace_id: str | None, filters: dict | None) -> str | None:
        clauses: list[str] = []
        if workspace_id is not None:
            clauses.append(f"{{workspace_id}}='{workspace_id}'")
        for key, value in (filters or {}).items():
            clauses.append(f"{{{key}}}='{value}'")
        if not clauses:
            return None
        if len(clauses) == 1:
            return clauses[0]
        return "AND(" + ", ".join(clauses) + ")"


def _encode_changes(model: type[Entity], changes: dict) -> dict:
    """JSON-encode any dict/list fields present in a partial-update payload."""
    import json as _json

    from .mapping import json_field_names  # local import to avoid cycle noise

    json_fields = json_field_names(model)
    encoded: dict = {}
    for name, value in changes.items():
        if name in json_fields and not isinstance(value, str):
            encoded[name] = _json.dumps(value)
        else:
            encoded[name] = value
    return encoded
