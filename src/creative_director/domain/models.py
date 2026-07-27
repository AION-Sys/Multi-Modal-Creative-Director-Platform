"""Domain models — the confirmed data model.

Design notes (migration safety):
- Every entity carries a self-minted UUID `id`. Relationships reference *these*
  UUIDs as plain strings, never Airtable's internal `rec...` record IDs. This is
  what lets the whole dataset move to Postgres without rewiring foreign keys.
- Every non-root entity carries `workspace_id` for multi-tenant isolation.
- Media never lives in the DB: `Version.output_ref` is an object-storage key
  (e.g. "local://..." today, "s3://..." later).
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from pydantic import BaseModel, Field

from .enums import (
    AssetStatus,
    Modality,
    PipelineNode,
    PipelineStatus,
    ProjectStatus,
    VersionStatus,
    VersionVerdict,
    WorkspaceKind,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return str(uuid4())


class Entity(BaseModel):
    """Common fields for every persisted record."""

    id: str = Field(default_factory=_new_id)
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class Workspace(Entity):
    """Top-level tenant: a personal space or a client workspace."""

    name: str
    kind: WorkspaceKind = WorkspaceKind.PERSONAL
    # Brand/style config: palette, tone, fonts, do/don't lists, etc.
    brand_config: dict = Field(default_factory=dict)


class Project(Entity):
    """A brief within a workspace."""

    workspace_id: str
    name: str
    goal: str
    # Free-form/structured brand + style constraints for this brief.
    constraints: dict = Field(default_factory=dict)
    target_modalities: list[Modality] = Field(default_factory=list)
    status: ProjectStatus = ProjectStatus.DRAFT


class Asset(Entity):
    """A planned piece of content within a project."""

    workspace_id: str
    project_id: str
    name: str
    modality: Modality
    # What to make: prompt seeds, dimensions, duration, format, etc.
    spec: dict = Field(default_factory=dict)
    status: AssetStatus = AssetStatus.PLANNED
    # Ordering within the asset plan.
    order: int = 0


class Version(Entity):
    """An immutable generation/edit output tied to an Asset.

    Versions are never overwritten. Edits and regenerations create new versions
    that point back via `parent_version_id`, forming a branchable history.
    """

    workspace_id: str
    asset_id: str
    provider: str = ""
    model: str = ""
    prompt: str = ""
    params: dict = Field(default_factory=dict)
    # Object-storage reference to the produced media/text; None until ready.
    output_ref: str | None = None
    # Parent in the edit/regeneration chain (None for a root version).
    parent_version_id: str | None = None
    # Director self-critique result: {"notes": str, "score": float, ...}.
    critique: dict = Field(default_factory=dict)
    verdict: VersionVerdict = VersionVerdict.PENDING
    status: VersionStatus = VersionStatus.PENDING


class PipelineRun(Entity):
    """Persisted director-pipeline state, so a project can resume mid-flight.

    Backs the LangGraph checkpointer and is the record that the resume and
    human-review endpoints act on.
    """

    workspace_id: str
    project_id: str
    current_node: PipelineNode = PipelineNode.PLAN
    status: PipelineStatus = PipelineStatus.RUNNING
    # Serialized graph state (JSON-safe).
    graph_state: dict = Field(default_factory=dict)
    error: str | None = None
