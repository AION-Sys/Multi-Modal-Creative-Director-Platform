"""FastAPI application factory.

`create_app` accepts an injected RepositorySet/Settings (used by tests to supply
a fresh memory backend) and otherwise builds them from config. The module-level
`app` is what `uvicorn creative_director.api.app:app` serves.
"""

from __future__ import annotations

from fastapi import FastAPI

from ..config import Settings, get_settings
from ..repositories.base import RepositorySet
from ..repositories.factory import get_repository_set
from .routers import assets, projects, versions, workspaces


def create_app(
    repos: RepositorySet | None = None, settings: Settings | None = None
) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(
        title="Multi-Modal Creative Director Platform",
        version="0.1.0",
    )
    app.state.settings = settings
    app.state.repos = repos or get_repository_set(settings)

    @app.get("/health", tags=["meta"])
    async def health() -> dict:
        return {"status": "ok", "backend": settings.backend}

    app.include_router(workspaces.router)
    app.include_router(projects.router)
    app.include_router(assets.router)
    app.include_router(versions.router)
    return app


app = create_app()
