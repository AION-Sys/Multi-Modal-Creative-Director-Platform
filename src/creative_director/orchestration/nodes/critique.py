"""Self-critique node: director reviews each generated Version vs the brief.

Delegates the per-Version review to `critique_version` (shared with the Review
stage's re-critique). Annotation only — the approve/regenerate loop is the Review
stage. Per-Version failures are captured, never fatal.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from ...storage.base import ObjectStorage
from ..director import DirectorAgent
from ..operations import critique_version
from ..state import DirectorState


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
            try:
                results.append(
                    await critique_version(director, repos, storage, version, asset, goal)
                )
            except Exception as exc:
                results.append({"version_id": version.id, "error": str(exc)})

        return {"critiques": results, "error": None}

    return critique_node
