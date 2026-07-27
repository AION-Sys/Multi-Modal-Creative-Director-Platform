"""Human-review loop: approve a Version, reject, or regenerate an Asset.

Regeneration is where the branchable-version design pays off: it produces a *new*
Version linked via `parent_version_id`, folding the critique's suggestions (and
any human tweak) into the prompt — the rejected version is never overwritten.
"""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel

from ..domain.enums import AssetStatus, VersionStatus
from ..domain.models import Asset, Version
from ..orchestration.director import DirectorAgent
from ..orchestration.operations import critique_version, generate_version_for_asset
from ..providers.base import ProviderRegistry
from ..repositories.base import RepositorySet
from ..storage.base import ObjectStorage


class ReviewError(Exception):
    pass


class ReviewItem(BaseModel):
    """An asset awaiting human review, with its latest ready Version."""

    asset: Asset
    version: Version | None


@dataclass
class ReviewService:
    repos: RepositorySet
    providers: ProviderRegistry
    storage: ObjectStorage
    director: DirectorAgent | None = None

    async def _latest_version(self, workspace_id: str, asset_id: str) -> Version | None:
        versions = await self.repos.versions.list(
            workspace_id=workspace_id, filters={"asset_id": asset_id}
        )
        return versions[-1] if versions else None

    async def _latest_ready_version(self, workspace_id: str, asset_id: str) -> Version | None:
        versions = await self.repos.versions.list(
            workspace_id=workspace_id, filters={"asset_id": asset_id}
        )
        ready = [v for v in versions if v.status == VersionStatus.READY]
        return ready[-1] if ready else None

    async def pending(
        self, workspace_id: str, project_id: str | None = None
    ) -> list[ReviewItem]:
        """Assets in `review` status, each with its latest ready Version."""
        filters = {"project_id": project_id} if project_id else None
        assets = await self.repos.assets.list(workspace_id=workspace_id, filters=filters)
        items: list[ReviewItem] = []
        for asset in assets:
            if asset.status != AssetStatus.REVIEW:
                continue
            version = await self._latest_ready_version(workspace_id, asset.id)
            items.append(ReviewItem(asset=asset, version=version))
        return items

    async def approve(self, workspace_id: str, version_id: str) -> dict:
        """Approve a Version — locks the Asset (status=approved)."""
        version = await self.repos.versions.get(version_id, workspace_id=workspace_id)
        if version is None:
            raise ReviewError(f"Version {version_id} not found")
        asset = await self.repos.assets.update(
            version.asset_id, {"status": AssetStatus.APPROVED.value},
            workspace_id=workspace_id,
        )
        if asset is None:
            raise ReviewError(f"Asset {version.asset_id} not found")
        return {"asset_id": asset.id, "version_id": version.id, "status": "approved"}

    async def reject(self, workspace_id: str, asset_id: str) -> dict:
        """Reject an Asset outright (no regeneration)."""
        asset = await self.repos.assets.update(
            asset_id, {"status": AssetStatus.REJECTED.value}, workspace_id=workspace_id
        )
        if asset is None:
            raise ReviewError(f"Asset {asset_id} not found")
        return {"asset_id": asset.id, "status": "rejected"}

    async def regenerate(
        self,
        workspace_id: str,
        asset_id: str,
        *,
        prompt_suffix: str | None = None,
        params: dict | None = None,
        recritique: bool = False,
    ) -> dict:
        """Produce a new Version for an Asset, branching from its latest one.

        Folds the prior critique's suggestions plus any human `prompt_suffix` into
        the prompt; optionally re-critiques the new Version (needs a director).
        """
        asset = await self.repos.assets.get(asset_id, workspace_id=workspace_id)
        if asset is None:
            raise ReviewError(f"Asset {asset_id} not found")

        latest = await self._latest_version(workspace_id, asset_id)
        parent_version_id = latest.id if latest else None

        prompt = asset.spec.get("prompt", "")
        suggestions = ""
        if latest is not None and latest.critique:
            suggestions = latest.critique.get("suggestions", "") or ""
        if suggestions:
            prompt = f"{prompt}\nAdjustments from critique: {suggestions}"
        if prompt_suffix:
            prompt = f"{prompt}\n{prompt_suffix}"

        await self.repos.assets.update(
            asset_id, {"status": AssetStatus.GENERATING.value}, workspace_id=workspace_id
        )
        result = await generate_version_for_asset(
            self.repos, self.providers, self.storage, asset, workspace_id,
            prompt=prompt, params=params, parent_version_id=parent_version_id,
        )

        if recritique and result.get("status") == "generated":
            if self.director is None:
                raise ReviewError("recritique requested but no director is configured")
            version = await self.repos.versions.get(
                result["version_id"], workspace_id=workspace_id
            )
            refreshed_asset = await self.repos.assets.get(asset_id, workspace_id=workspace_id)
            goal = await self._project_goal(workspace_id, refreshed_asset.project_id)
            critique = await critique_version(
                self.director, self.repos, self.storage, version, refreshed_asset, goal
            )
            result["critique"] = critique

        return result

    async def _project_goal(self, workspace_id: str, project_id: str) -> str:
        project = await self.repos.projects.get(project_id, workspace_id=workspace_id)
        return project.goal if project else ""
