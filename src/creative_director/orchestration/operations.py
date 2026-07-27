"""Single-asset operations shared by the pipeline nodes and the review loop.

Both the Generate node and the Review stage's "regenerate" path need to produce
a stored, versioned output for one asset; both the Critique node and a re-critique
need to review one Version. Keeping that logic here (one implementation each) is
what lets regeneration reuse the exact generation path — new Version, parent
link, storage write — instead of a parallel copy.
"""

from __future__ import annotations

from ..domain.enums import AssetStatus, Modality, VersionStatus, VersionVerdict
from ..domain.models import Asset, Version
from ..providers.base import GenerationRequest, ProviderError, ProviderRegistry
from ..providers.service import media_key
from ..repositories.base import RepositorySet
from ..storage.base import ObjectStorage
from .director import CritiqueRequest, DirectorAgent

# Default generation params per modality (providers ignore what they don't use).
_DEFAULT_PARAMS: dict[Modality, dict] = {
    Modality.IMAGE: {"size": "1024x1024"},
}

_MEDIA_TYPES = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "webp": "image/webp",
}


def content_type_for_ref(ref: str) -> str:
    ext = ref.rsplit(".", 1)[-1].lower() if "." in ref else ""
    return _MEDIA_TYPES.get(ext, "image/png")


async def generate_version_for_asset(
    repos: RepositorySet,
    providers: ProviderRegistry,
    storage: ObjectStorage,
    asset: Asset,
    workspace_id: str,
    *,
    prompt: str | None = None,
    params: dict | None = None,
    parent_version_id: str | None = None,
) -> dict:
    """Generate + store one output for an asset and record a Version.

    Returns a result dict: generated / skipped / failed. `parent_version_id`
    links an edit/regeneration to the version it descends from.
    """
    try:
        provider = providers.for_modality(asset.modality)
    except ProviderError:
        return {
            "asset_id": asset.id, "status": "skipped",
            "reason": f"no provider for modality '{asset.modality.value}'",
        }

    prompt = asset.spec.get("prompt", "") if prompt is None else prompt
    params = _DEFAULT_PARAMS.get(asset.modality, {}) if params is None else params

    version = await repos.versions.create(
        Version(
            workspace_id=workspace_id,
            asset_id=asset.id,
            provider=provider.name,
            prompt=prompt,
            params=params,
            parent_version_id=parent_version_id,
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
        {"output_ref": ref, "model": result.model, "status": VersionStatus.READY.value},
        workspace_id=workspace_id,
    )
    await repos.assets.update(
        asset.id, {"status": AssetStatus.REVIEW.value}, workspace_id=workspace_id
    )
    return {
        "asset_id": asset.id, "version_id": version.id, "status": "generated",
        "output_ref": ref, "provider": provider.name, "model": result.model,
        "parent_version_id": parent_version_id,
    }


async def critique_version(
    director: DirectorAgent,
    repos: RepositorySet,
    storage: ObjectStorage,
    version: Version,
    asset: Asset,
    goal: str,
) -> dict:
    """Review one Version against the brief and record the verdict on it."""
    image = image_ct = text = None
    if asset.modality == Modality.IMAGE and version.output_ref:
        image = await storage.load(version.output_ref)
        image_ct = content_type_for_ref(version.output_ref)

    critique = await director.critique(
        CritiqueRequest(
            goal=goal, asset_name=asset.name, modality=asset.modality, spec=asset.spec,
            image=image, image_content_type=image_ct, text=text,
        )
    )
    verdict = VersionVerdict.PASS if critique.verdict == "pass" else VersionVerdict.REGENERATE
    await repos.versions.update(
        version.id,
        {
            "verdict": verdict.value,
            "critique": {
                "score": critique.score,
                "notes": critique.notes,
                "suggestions": critique.suggestions,
            },
        },
        workspace_id=version.workspace_id,
    )
    return {
        "version_id": version.id, "asset_id": asset.id,
        "verdict": verdict.value, "score": critique.score,
    }
