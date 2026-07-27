"""Run the pipeline for a project, then review its output.

Endpoints:
  POST /workspaces/{ws}/projects/{pid}/run          run plan->generate->critique
  GET  /workspaces/{ws}/review?project_id=...        assets awaiting review
  POST /workspaces/{ws}/versions/{vid}/approve       approve (locks the asset)
  POST /workspaces/{ws}/assets/{aid}/regenerate      branch a new version
  POST /workspaces/{ws}/assets/{aid}/reject          reject the asset
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from ...providers.base import ProviderRegistry
from ...repositories.base import RepositorySet
from ...services.pipeline import PipelineError, run_project
from ...services.review import ReviewError, ReviewItem, ReviewService
from ...storage.base import ObjectStorage
from ..deps import (
    get_director,
    get_providers,
    get_repos,
    get_review,
    get_storage,
    require_api_key,
)
from ..schemas import RegenerateRequest

router = APIRouter(tags=["review"], dependencies=[Depends(require_api_key)])


@router.post("/workspaces/{workspace_id}/projects/{project_id}/run")
async def run_pipeline(
    workspace_id: str,
    project_id: str,
    repos: RepositorySet = Depends(get_repos),
    providers: ProviderRegistry = Depends(get_providers),
    storage: ObjectStorage = Depends(get_storage),
    director=Depends(get_director),
):
    try:
        return await run_project(director, repos, providers, storage, workspace_id, project_id)
    except PipelineError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/workspaces/{workspace_id}/review", response_model=list[ReviewItem])
async def list_review(
    workspace_id: str,
    project_id: str | None = Query(default=None),
    review: ReviewService = Depends(get_review),
):
    return await review.pending(workspace_id, project_id)


@router.post("/workspaces/{workspace_id}/versions/{version_id}/approve")
async def approve(
    workspace_id: str, version_id: str, review: ReviewService = Depends(get_review)
):
    try:
        return await review.approve(workspace_id, version_id)
    except ReviewError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/workspaces/{workspace_id}/assets/{asset_id}/regenerate")
async def regenerate(
    workspace_id: str,
    asset_id: str,
    payload: RegenerateRequest | None = None,
    review: ReviewService = Depends(get_review),
):
    payload = payload or RegenerateRequest()
    try:
        return await review.regenerate(
            workspace_id, asset_id,
            prompt_suffix=payload.prompt_suffix,
            params=payload.params,
            recritique=payload.recritique,
        )
    except ReviewError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/workspaces/{workspace_id}/assets/{asset_id}/reject")
async def reject(
    workspace_id: str, asset_id: str, review: ReviewService = Depends(get_review)
):
    try:
        return await review.reject(workspace_id, asset_id)
    except ReviewError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
