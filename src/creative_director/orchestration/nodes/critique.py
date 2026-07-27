"""Self-critique node: director reviews each generated Version vs the brief.

For every successfully generated Version it loads the output (image bytes for
vision critique), asks the director for a pass/regenerate verdict, and writes
that verdict plus the critique notes back onto the Version. It only annotates —
the actual approve/regenerate loop is the Review stage (next step). Per-version
failures are captured, never fatal.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from ...domain.enums import Modality, VersionVerdict
from ...storage.base import ObjectStorage
from ..director import CritiqueRequest, DirectorAgent
from ..state import DirectorState

_MEDIA_TYPES = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "webp": "image/webp",
}


def _content_type_for_ref(ref: str) -> str:
    ext = ref.rsplit(".", 1)[-1].lower() if "." in ref else ""
    return _MEDIA_TYPES.get(ext, "image/png")


def make_critique_node(
    director: DirectorAgent,
    repos,
    storage: ObjectStorage,
) -> Callable[[DirectorState], Awaitable[dict]]:
    async def critique_node(state: DirectorState) -> dict:
        workspace_id = state.get("workspace_id")
        if not workspace_id:
            return {"error": "critique_node requires workspace_id in state"}
        brief = state.get("brief")
        goal = brief.goal if brief is not None else ""

        results: list[dict] = []
        for gen in state.get("generated", []):
            if gen.get("status") != "generated":
                continue
            version = await repos.versions.get(gen["version_id"], workspace_id=workspace_id)
            asset = await repos.assets.get(gen["asset_id"], workspace_id=workspace_id)
            if version is None or asset is None:
                continue

            image = image_ct = text = None
            if asset.modality == Modality.IMAGE and version.output_ref:
                image = await storage.load(version.output_ref)
                image_ct = _content_type_for_ref(version.output_ref)

            request = CritiqueRequest(
                goal=goal,
                asset_name=asset.name,
                modality=asset.modality,
                spec=asset.spec,
                image=image,
                image_content_type=image_ct,
                text=text,
            )
            try:
                critique = await director.critique(request)
            except Exception as exc:
                results.append({"version_id": version.id, "error": str(exc)})
                continue

            verdict = (
                VersionVerdict.PASS
                if critique.verdict == "pass"
                else VersionVerdict.REGENERATE
            )
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
                workspace_id=workspace_id,
            )
            results.append(
                {
                    "version_id": version.id,
                    "asset_id": asset.id,
                    "verdict": verdict.value,
                    "score": critique.score,
                }
            )

        return {"critiques": results, "error": None}

    return critique_node
