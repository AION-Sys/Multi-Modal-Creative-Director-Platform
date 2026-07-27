"""Generate node: asset plan -> generated, stored, versioned outputs.

For each planned asset this node:
  1. persists an Asset row (status=generating),
  2. routes it to the provider registered for its modality,
  3. generates bytes, writes them to object storage,
  4. records an immutable Version (output_ref, provider, model) and moves the
     asset to `review`.

Modalities with no registered provider yet (copy/video/audio) are left planned
and reported as skipped — that's the pluggable interface doing its job, not an
error. Per-asset failures are captured on the Version and in the result list so
one bad generation never sinks the whole run.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from ...domain.enums import AssetStatus, Modality, VersionStatus
from ...domain.models import Asset, Version
from ...providers.base import GenerationRequest, ProviderError, ProviderRegistry
from ...providers.service import media_key
from ...repositories.base import RepositorySet
from ...storage.base import ObjectStorage
from ..state import DirectorState

# Default generation params per modality (providers ignore what they don't use).
_DEFAULT_PARAMS: dict[Modality, dict] = {
    Modality.IMAGE: {"size": "1024x1024"},
}


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
            modality = Modality(spec["modality"])
            asset = await repos.assets.create(
                Asset(
                    workspace_id=workspace_id,
                    project_id=project_id,
                    name=spec["name"],
                    modality=modality,
                    spec=spec["spec"],
                    order=spec["order"],
                    status=AssetStatus.GENERATING,
                )
            )
            asset_ids.append(asset.id)

            try:
                provider = providers.for_modality(modality)
            except ProviderError:
                results.append(
                    {"asset_id": asset.id, "status": "skipped",
                     "reason": f"no provider for modality '{modality.value}'"}
                )
                continue

            results.append(
                await _generate_one(repos, storage, provider, asset, spec, workspace_id)
            )

        return {"asset_ids": asset_ids, "generated": results, "error": None}

    return generate_node


async def _generate_one(
    repos: RepositorySet,
    storage: ObjectStorage,
    provider,
    asset: Asset,
    spec: dict,
    workspace_id: str,
) -> dict:
    prompt = spec["spec"].get("prompt", "")
    params = _DEFAULT_PARAMS.get(asset.modality, {})
    # Record the attempt as a pending Version before doing the work.
    version = await repos.versions.create(
        Version(
            workspace_id=workspace_id,
            asset_id=asset.id,
            provider=provider.name,
            prompt=prompt,
            params=params,
            status=VersionStatus.PENDING,
        )
    )
    try:
        result = await provider.generate(
            GenerationRequest(modality=asset.modality, prompt=prompt, params=params)
        )
        key = media_key(workspace_id, asset.id, version.id, result.ext)
        ref = await storage.save(key, result.data, content_type=result.content_type)
    except Exception as exc:
        await repos.versions.update(
            version.id, {"status": VersionStatus.FAILED.value}, workspace_id=workspace_id
        )
        return {"asset_id": asset.id, "version_id": version.id,
                "status": "failed", "error": str(exc)}

    await repos.versions.update(
        version.id,
        {
            "output_ref": ref,
            "model": result.model,
            "status": VersionStatus.READY.value,
        },
        workspace_id=workspace_id,
    )
    await repos.assets.update(
        asset.id, {"status": AssetStatus.REVIEW.value}, workspace_id=workspace_id
    )
    return {
        "asset_id": asset.id,
        "version_id": version.id,
        "status": "generated",
        "output_ref": ref,
        "provider": provider.name,
        "model": result.model,
    }
