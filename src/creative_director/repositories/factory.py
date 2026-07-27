"""Assemble a RepositorySet for the configured backend."""

from __future__ import annotations

from ..config import Settings
from ..domain.models import Asset, PipelineRun, Project, Version, Workspace
from .base import RepositorySet
from .memory import MemoryRepository


def build_memory_repositories() -> RepositorySet:
    return RepositorySet(
        workspaces=MemoryRepository(Workspace),
        projects=MemoryRepository(Project),
        assets=MemoryRepository(Asset),
        versions=MemoryRepository(Version),
        pipeline_runs=MemoryRepository(PipelineRun),
    )


def build_airtable_repositories(settings: Settings) -> RepositorySet:
    # Imported lazily so the memory path never requires Airtable config.
    from .airtable.client import AirtableClient
    from .airtable.repository import AirtableRepository
    from .airtable.schema import TABLE_BY_MODEL_KEY

    client = AirtableClient(settings.airtable_api_key or "", settings.airtable_base_id or "")

    def repo(model_key: str, model):
        return AirtableRepository(client, TABLE_BY_MODEL_KEY[model_key].name, model)

    return RepositorySet(
        workspaces=repo("workspaces", Workspace),
        projects=repo("projects", Project),
        assets=repo("assets", Asset),
        versions=repo("versions", Version),
        pipeline_runs=repo("pipeline_runs", PipelineRun),
    )


def get_repository_set(settings: Settings) -> RepositorySet:
    if settings.backend == "airtable":
        return build_airtable_repositories(settings)
    return build_memory_repositories()
