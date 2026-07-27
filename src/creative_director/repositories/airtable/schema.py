"""Airtable schema, defined as data.

This is the single source of truth for the Airtable base layout. `bootstrap.py`
reads it to create tables; the repository reads it to know table names. Because
it's plain data derived from the domain enums, the same definitions translate
directly into a Postgres DDL generator later.

Field-type choices reflect the migration-safety decisions:
- `id` is the primary field (our UUID), never Airtable's internal rec-id.
- Relationships (`workspace_id`, `project_id`, ...) are plain text UUIDs, so they
  survive a backend swap. (Airtable link fields could be layered on later purely
  for human browsability without changing the canonical FK.)
- dict/list fields are stored as JSON in long-text fields.
- Enums become single-select fields whose choices come straight from Python.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ...domain.enums import (
    AssetStatus,
    Modality,
    PipelineNode,
    PipelineStatus,
    ProjectStatus,
    StrEnum,
    VersionStatus,
    VersionVerdict,
    WorkspaceKind,
)


@dataclass(frozen=True)
class FieldSpec:
    name: str
    type: str
    options: dict | None = None

    def to_airtable(self) -> dict:
        payload: dict = {"name": self.name, "type": self.type}
        if self.options is not None:
            payload["options"] = self.options
        return payload


@dataclass(frozen=True)
class TableSpec:
    name: str
    model_key: str  # matches RepositorySet attribute: workspaces/projects/...
    fields: list[FieldSpec] = field(default_factory=list)

    def to_airtable(self) -> dict:
        return {"name": self.name, "fields": [f.to_airtable() for f in self.fields]}


def _select(name: str, enum: type[StrEnum]) -> FieldSpec:
    return FieldSpec(
        name=name,
        type="singleSelect",
        options={"choices": [{"name": choice.value} for choice in enum]},
    )


def _text(name: str) -> FieldSpec:
    return FieldSpec(name=name, type="singleLineText")


def _long(name: str) -> FieldSpec:
    """Long text, also used to hold JSON-encoded dict/list fields."""
    return FieldSpec(name=name, type="multilineText")


def _number(name: str) -> FieldSpec:
    return FieldSpec(name=name, type="number", options={"precision": 0})


# Common to every table. `id` is first == Airtable primary field.
_COMMON = [_text("id"), _text("created_at"), _text("updated_at")]


TABLES: list[TableSpec] = [
    TableSpec(
        name="Workspaces",
        model_key="workspaces",
        fields=[
            *_COMMON,
            _text("name"),
            _select("kind", WorkspaceKind),
            _long("brand_config"),
        ],
    ),
    TableSpec(
        name="Projects",
        model_key="projects",
        fields=[
            *_COMMON,
            _text("workspace_id"),
            _text("name"),
            _long("goal"),
            _long("constraints"),
            _long("target_modalities"),
            _select("status", ProjectStatus),
        ],
    ),
    TableSpec(
        name="Assets",
        model_key="assets",
        fields=[
            *_COMMON,
            _text("workspace_id"),
            _text("project_id"),
            _text("name"),
            _select("modality", Modality),
            _long("spec"),
            _select("status", AssetStatus),
            _number("order"),
        ],
    ),
    TableSpec(
        name="Versions",
        model_key="versions",
        fields=[
            *_COMMON,
            _text("workspace_id"),
            _text("asset_id"),
            _text("provider"),
            _text("model"),
            _long("prompt"),
            _long("params"),
            _text("output_ref"),
            _text("parent_version_id"),
            _long("critique"),
            _select("verdict", VersionVerdict),
            _select("status", VersionStatus),
        ],
    ),
    TableSpec(
        name="PipelineRuns",
        model_key="pipeline_runs",
        fields=[
            *_COMMON,
            _text("workspace_id"),
            _text("project_id"),
            _select("current_node", PipelineNode),
            _select("status", PipelineStatus),
            _long("graph_state"),
            _long("error"),
        ],
    ),
]

TABLE_BY_MODEL_KEY: dict[str, TableSpec] = {t.model_key: t for t in TABLES}
