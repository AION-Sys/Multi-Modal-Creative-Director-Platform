"""FastAPI application factory.

`create_app` accepts injected collaborators (used by tests to supply a fresh
memory backend, a FakeDirector, etc.) and otherwise builds them from config. The
module-level `app` is what `uvicorn creative_director.api.app:app` serves.
"""

from __future__ import annotations

from fastapi import FastAPI

from ..config import Settings, get_settings
from ..orchestration.director import AnthropicDirector, DirectorAgent, FakeDirector
from ..providers.base import ProviderRegistry
from ..providers.factory import build_provider_registry
from ..repositories.base import RepositorySet
from ..repositories.factory import get_repository_set
from ..services.review import ReviewService
from ..storage.base import ObjectStorage
from ..storage.factory import get_storage
from .routers import assets, projects, review, versions, workspaces


def _default_director(settings: Settings) -> DirectorAgent:
    # Real director when a key is configured; keyless Fake otherwise so the API
    # runs end-to-end with no external accounts.
    if settings.anthropic_api_key:
        return AnthropicDirector(
            api_key=settings.anthropic_api_key, model=settings.director_model
        )
    return FakeDirector()


def create_app(
    repos: RepositorySet | None = None,
    settings: Settings | None = None,
    director: DirectorAgent | None = None,
    providers: ProviderRegistry | None = None,
    storage: ObjectStorage | None = None,
    review_service: ReviewService | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(
        title="Multi-Modal Creative Director Platform",
        version="0.1.0",
    )
    repos = repos or get_repository_set(settings)
    providers = providers or build_provider_registry(settings)
    storage = storage or get_storage(settings)
    director = director or _default_director(settings)

    app.state.settings = settings
    app.state.repos = repos
    app.state.providers = providers
    app.state.storage = storage
    app.state.director = director
    app.state.review = review_service or ReviewService(repos, providers, storage, director)

    @app.get("/health", tags=["meta"])
    async def health() -> dict:
        return {"status": "ok", "backend": settings.backend}

    app.include_router(workspaces.router)
    app.include_router(projects.router)
    app.include_router(assets.router)
    app.include_router(versions.router)
    app.include_router(review.router)
    return app


app = create_app()
