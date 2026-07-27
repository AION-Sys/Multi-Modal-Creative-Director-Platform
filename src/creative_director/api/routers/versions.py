"""Version CRUD, scoped under a workspace (filterable by asset).

Versions are immutable outputs: they can be created and their review metadata
(critique/verdict/status/output_ref) updated, but there is no destructive edit —
regeneration produces a *new* version linked via parent_version_id.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from ...domain.models import Version
from ...repositories.base import RepositorySet
from ..deps import get_repos, require_api_key
from ..schemas import VersionCreate, VersionUpdate

router = APIRouter(
    prefix="/workspaces/{workspace_id}/versions",
    tags=["versions"],
    dependencies=[Depends(require_api_key)],
)


@router.post("", response_model=Version, status_code=201)
async def create_version(
    workspace_id: str, payload: VersionCreate, repos: RepositorySet = Depends(get_repos)
):
    # The parent asset must exist inside this workspace.
    if await repos.assets.get(payload.asset_id, workspace_id=workspace_id) is None:
        raise HTTPException(status_code=404, detail="Asset not found in workspace")
    version = Version(workspace_id=workspace_id, **payload.model_dump())
    return await repos.versions.create(version)


@router.get("", response_model=list[Version])
async def list_versions(
    workspace_id: str,
    asset_id: str | None = Query(default=None),
    repos: RepositorySet = Depends(get_repos),
):
    filters = {"asset_id": asset_id} if asset_id else None
    return await repos.versions.list(workspace_id=workspace_id, filters=filters)


@router.get("/{version_id}", response_model=Version)
async def get_version(
    workspace_id: str, version_id: str, repos: RepositorySet = Depends(get_repos)
):
    version = await repos.versions.get(version_id, workspace_id=workspace_id)
    if version is None:
        raise HTTPException(status_code=404, detail="Version not found")
    return version


@router.patch("/{version_id}", response_model=Version)
async def update_version(
    workspace_id: str,
    version_id: str,
    payload: VersionUpdate,
    repos: RepositorySet = Depends(get_repos),
):
    version = await repos.versions.update(
        version_id, payload.model_dump(exclude_unset=True), workspace_id=workspace_id
    )
    if version is None:
        raise HTTPException(status_code=404, detail="Version not found")
    return version
