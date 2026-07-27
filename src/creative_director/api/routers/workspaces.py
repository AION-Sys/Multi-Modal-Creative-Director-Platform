"""Workspace CRUD (the root tenant — no workspace_id scoping)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ...domain.models import Workspace
from ...repositories.base import RepositorySet
from ..deps import get_repos, require_api_key
from ..schemas import WorkspaceCreate, WorkspaceUpdate

router = APIRouter(
    prefix="/workspaces",
    tags=["workspaces"],
    dependencies=[Depends(require_api_key)],
)


@router.post("", response_model=Workspace, status_code=201)
async def create_workspace(payload: WorkspaceCreate, repos: RepositorySet = Depends(get_repos)):
    return await repos.workspaces.create(Workspace(**payload.model_dump()))


@router.get("", response_model=list[Workspace])
async def list_workspaces(repos: RepositorySet = Depends(get_repos)):
    return await repos.workspaces.list()


@router.get("/{workspace_id}", response_model=Workspace)
async def get_workspace(workspace_id: str, repos: RepositorySet = Depends(get_repos)):
    ws = await repos.workspaces.get(workspace_id)
    if ws is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return ws


@router.patch("/{workspace_id}", response_model=Workspace)
async def update_workspace(
    workspace_id: str, payload: WorkspaceUpdate, repos: RepositorySet = Depends(get_repos)
):
    ws = await repos.workspaces.update(workspace_id, payload.model_dump(exclude_unset=True))
    if ws is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return ws


@router.delete("/{workspace_id}", status_code=204)
async def delete_workspace(workspace_id: str, repos: RepositorySet = Depends(get_repos)):
    if not await repos.workspaces.delete(workspace_id):
        raise HTTPException(status_code=404, detail="Workspace not found")
