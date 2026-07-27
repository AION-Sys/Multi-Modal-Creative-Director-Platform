"""Request bodies for the CRUD API.

Separate from the domain models so clients can't set server-managed fields
(id, timestamps) and so partial updates use `exclude_unset` semantics. Path
parameters supply workspace_id, so it never appears in a request body.
"""

from __future__ import annotations

from pydantic import BaseModel

from ..domain.enums import (
    AssetStatus,
    Modality,
    ProjectStatus,
    VersionStatus,
    VersionVerdict,
    WorkspaceKind,
)


# --- Workspace ---
class WorkspaceCreate(BaseModel):
    name: str
    kind: WorkspaceKind = WorkspaceKind.PERSONAL
    brand_config: dict = {}


class WorkspaceUpdate(BaseModel):
    name: str | None = None
    kind: WorkspaceKind | None = None
    brand_config: dict | None = None


# --- Project ---
class ProjectCreate(BaseModel):
    name: str
    goal: str
    constraints: dict = {}
    target_modalities: list[Modality] = []
    status: ProjectStatus = ProjectStatus.DRAFT


class ProjectUpdate(BaseModel):
    name: str | None = None
    goal: str | None = None
    constraints: dict | None = None
    target_modalities: list[Modality] | None = None
    status: ProjectStatus | None = None


# --- Asset ---
class AssetCreate(BaseModel):
    project_id: str
    name: str
    modality: Modality
    spec: dict = {}
    status: AssetStatus = AssetStatus.PLANNED
    order: int = 0


class AssetUpdate(BaseModel):
    name: str | None = None
    modality: Modality | None = None
    spec: dict | None = None
    status: AssetStatus | None = None
    order: int | None = None


# --- Version ---
class VersionCreate(BaseModel):
    asset_id: str
    provider: str = ""
    model: str = ""
    prompt: str = ""
    params: dict = {}
    output_ref: str | None = None
    parent_version_id: str | None = None
    critique: dict = {}
    verdict: VersionVerdict = VersionVerdict.PENDING
    status: VersionStatus = VersionStatus.PENDING


class VersionUpdate(BaseModel):
    # Versions are immutable outputs; the review loop still needs to record the
    # critique/verdict/status and finalize output_ref, so those stay updatable.
    output_ref: str | None = None
    critique: dict | None = None
    verdict: VersionVerdict | None = None
    status: VersionStatus | None = None
