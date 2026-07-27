"""Repository interface — the seam between the app and its persistence backend.

Every backend (memory, Airtable, later Postgres) implements this same async
contract, so nothing above this layer knows or cares which one is active.
Tenant isolation is enforced here: when a `workspace_id` is supplied, reads and
writes that cross a workspace boundary return "not found" rather than leaking.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Generic, TypeVar

from ..domain.models import Asset, Entity, PipelineRun, Project, Version, Workspace

T = TypeVar("T", bound=Entity)


class RepositoryError(Exception):
    """Base class for persistence-layer failures."""


class Repository(ABC, Generic[T]):
    """CRUD contract for a single entity type."""

    @abstractmethod
    async def create(self, entity: T) -> T:
        """Persist a new entity and return it."""

    @abstractmethod
    async def get(self, id: str, *, workspace_id: str | None = None) -> T | None:
        """Fetch by id, scoped to a workspace when given. None if absent/foreign."""

    @abstractmethod
    async def list(
        self, *, workspace_id: str | None = None, filters: dict | None = None
    ) -> list[T]:
        """List entities, optionally scoped to a workspace and filtered by fields."""

    @abstractmethod
    async def update(
        self, id: str, changes: dict, *, workspace_id: str | None = None
    ) -> T | None:
        """Apply a partial update (bumps updated_at). None if absent/foreign."""

    @abstractmethod
    async def delete(self, id: str, *, workspace_id: str | None = None) -> bool:
        """Delete by id. False if absent/foreign."""


@dataclass
class RepositorySet:
    """The full set of repositories the app wires together as a unit."""

    workspaces: Repository[Workspace]
    projects: Repository[Project]
    assets: Repository[Asset]
    versions: Repository[Version]
    pipeline_runs: Repository[PipelineRun]
