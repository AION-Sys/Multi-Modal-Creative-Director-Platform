"""Asset CRUD, scoped under a workspace (filterable by project)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from ...domain.models import Asset
from ...repositories.base import RepositorySet
from ..deps import get_repos, require_api_key
from ..schemas import AssetCreate, AssetUpdate

router = APIRouter(
    prefix="/workspaces/{workspace_id}/assets",
    tags=["assets"],
    dependencies=[Depends(require_api_key)],
)


@router.post("", response_model=Asset, status_code=201)
async def create_asset(
    workspace_id: str, payload: AssetCreate, repos: RepositorySet = Depends(get_repos)
):
    # The parent project must exist inside this workspace.
    if await repos.projects.get(payload.project_id, workspace_id=workspace_id) is None:
        raise HTTPException(status_code=404, detail="Project not found in workspace")
    asset = Asset(workspace_id=workspace_id, **payload.model_dump())
    return await repos.assets.create(asset)


@router.get("", response_model=list[Asset])
async def list_assets(
    workspace_id: str,
    project_id: str | None = Query(default=None),
    repos: RepositorySet = Depends(get_repos),
):
    filters = {"project_id": project_id} if project_id else None
    return await repos.assets.list(workspace_id=workspace_id, filters=filters)


@router.get("/{asset_id}", response_model=Asset)
async def get_asset(
    workspace_id: str, asset_id: str, repos: RepositorySet = Depends(get_repos)
):
    asset = await repos.assets.get(asset_id, workspace_id=workspace_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    return asset


@router.patch("/{asset_id}", response_model=Asset)
async def update_asset(
    workspace_id: str,
    asset_id: str,
    payload: AssetUpdate,
    repos: RepositorySet = Depends(get_repos),
):
    asset = await repos.assets.update(
        asset_id, payload.model_dump(exclude_unset=True), workspace_id=workspace_id
    )
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    return asset


@router.delete("/{asset_id}", status_code=204)
async def delete_asset(
    workspace_id: str, asset_id: str, repos: RepositorySet = Depends(get_repos)
):
    if not await repos.assets.delete(asset_id, workspace_id=workspace_id):
        raise HTTPException(status_code=404, detail="Asset not found")
