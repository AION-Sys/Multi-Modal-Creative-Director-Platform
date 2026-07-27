"""Project CRUD, scoped under a workspace."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ...domain.models import Project
from ...repositories.base import RepositorySet
from ..deps import get_repos, require_api_key
from ..schemas import ProjectCreate, ProjectUpdate

router = APIRouter(
    prefix="/workspaces/{workspace_id}/projects",
    tags=["projects"],
    dependencies=[Depends(require_api_key)],
)


async def _require_workspace(workspace_id: str, repos: RepositorySet) -> None:
    if await repos.workspaces.get(workspace_id) is None:
        raise HTTPException(status_code=404, detail="Workspace not found")


@router.post("", response_model=Project, status_code=201)
async def create_project(
    workspace_id: str, payload: ProjectCreate, repos: RepositorySet = Depends(get_repos)
):
    await _require_workspace(workspace_id, repos)
    project = Project(workspace_id=workspace_id, **payload.model_dump())
    return await repos.projects.create(project)


@router.get("", response_model=list[Project])
async def list_projects(workspace_id: str, repos: RepositorySet = Depends(get_repos)):
    return await repos.projects.list(workspace_id=workspace_id)


@router.get("/{project_id}", response_model=Project)
async def get_project(
    workspace_id: str, project_id: str, repos: RepositorySet = Depends(get_repos)
):
    project = await repos.projects.get(project_id, workspace_id=workspace_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.patch("/{project_id}", response_model=Project)
async def update_project(
    workspace_id: str,
    project_id: str,
    payload: ProjectUpdate,
    repos: RepositorySet = Depends(get_repos),
):
    project = await repos.projects.update(
        project_id, payload.model_dump(exclude_unset=True), workspace_id=workspace_id
    )
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.delete("/{project_id}", status_code=204)
async def delete_project(
    workspace_id: str, project_id: str, repos: RepositorySet = Depends(get_repos)
):
    if not await repos.projects.delete(project_id, workspace_id=workspace_id):
        raise HTTPException(status_code=404, detail="Project not found")
