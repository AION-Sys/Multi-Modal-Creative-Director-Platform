"""Shared FastAPI dependencies: static API-key auth and repository access.

Both read from `app.state`, which `create_app` populates. That keeps the app
free of module-level singletons and lets tests inject a fresh memory backend.
"""

from __future__ import annotations

from fastapi import Header, HTTPException, Request

from ..repositories.base import RepositorySet


def get_repos(request: Request) -> RepositorySet:
    return request.app.state.repos


async def require_api_key(
    request: Request, x_api_key: str | None = Header(default=None)
) -> None:
    expected = request.app.state.settings.app_api_key
    if not x_api_key or x_api_key != expected:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
