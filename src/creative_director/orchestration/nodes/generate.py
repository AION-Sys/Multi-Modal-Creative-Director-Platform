"""Generate node: asset plan -> generated, stored, versioned outputs.

For each planned asset it persists an Asset (status=generating) then delegates to
`generate_version_for_asset` — the same operation the Review stage's regenerate
path uses. Modalities with no provider are reported as skipped; per-asset failures
are captured, never fatal.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from ...domain.enums import AssetStatus, Modality
from ...domain.models import Asset
from ...providers.base import ProviderRegistry
from ...repositories.base import RepositorySet
from ...storage.base import ObjectStorage
from ..operations import generate_version_for_asset
from ..state import DirectorState


def make_generate_node(
    repos: RepositorySet,
    providers: ProviderRegistry,
    storage: ObjectStorage,
) -> Callable[[DirectorState], Awaitable[dict]]:
    async def generate_node(state: DirectorState) -> dict:
        workspace_id = state.get("workspace_id")
        project_id = state.get("project_id")
        if not workspace_id or not project_id:
            return {"error": "generate_node requires workspace_id and project_id in state"}

        planned = state.get("planned_assets") or []
        asset_ids: list[str] = []
        results: list[dict] = []

        for spec in planned:
            asset = await repos.assets.create(
                Asset(
                    workspace_id=workspace_id,
                    project_id=project_id,
                    name=spec["name"],
                    modality=Modality(spec["modality"]),
                    spec=spec["spec"],
                    order=spec["order"],
                    status=AssetStatus.GENERATING,
                )
            )
            asset_ids.append(asset.id)
            results.append(
                await generate_version_for_asset(
                    repos, providers, storage, asset, workspace_id,
                    prompt=spec["spec"].get("prompt", ""),
                )
            )

        return {"asset_ids": asset_ids, "generated": results, "error": None}

    return generate_node
