"""Entity <-> Airtable field mapping.

Isolated from the repository so it can be unit-tested without any network. The
rules are intentionally mechanical and derived from the Pydantic model itself:

- dict/list fields  -> JSON-encoded into a long-text field, decoded on the way back
- everything else   -> stored as-is (Pydantic handles datetime/enum parsing)
- None values are omitted from the Airtable payload
"""

from __future__ import annotations

import json
import typing
from functools import lru_cache
from typing import TypeVar

from ...domain.models import Entity

T = TypeVar("T", bound=Entity)


@lru_cache
def json_field_names(model: type[Entity]) -> frozenset[str]:
    """Field names whose annotation is a dict or list (stored as JSON text)."""
    names: set[str] = set()
    for name, info in model.model_fields.items():
        origin = typing.get_origin(info.annotation) or info.annotation
        if origin in (dict, list):
            names.add(name)
    return frozenset(names)


def to_fields(entity: Entity) -> dict:
    """Serialize a domain entity into an Airtable `fields` dict."""
    json_fields = json_field_names(type(entity))
    raw = entity.model_dump(mode="json")  # datetimes -> ISO str, enums -> value
    fields: dict = {}
    for name, value in raw.items():
        if value is None:
            continue
        if name in json_fields:
            fields[name] = json.dumps(value)
        else:
            fields[name] = value
    return fields


def from_fields(model: type[T], fields: dict) -> T:
    """Deserialize an Airtable `fields` dict back into a domain entity."""
    json_fields = json_field_names(model)
    data: dict = {}
    for name, value in fields.items():
        if name in json_fields and isinstance(value, str):
            data[name] = json.loads(value) if value else None
        else:
            data[name] = value
    return model(**data)
