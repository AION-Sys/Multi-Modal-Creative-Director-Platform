"""Plan node: brief -> asset plan.

The node is a thin wrapper: it hands the brief to the director agent and
normalizes the returned plan into asset specs the rest of the pipeline (and the
Asset table) can consume. It's a factory closing over the director so the node
stays a plain `state -> update` callable, and so tests can inject a FakeDirector.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from ..director import DirectorAgent, PlanBrief
from ..schemas import AssetPlanResult
from ..state import DirectorState


def normalize_assets(plan: AssetPlanResult) -> list[dict]:
    """Flatten a plan into ordered, storage-ready asset specs.

    Each entry mirrors the Asset domain model's shape: name, modality, order, and
    a `spec` dict carrying the generation details.
    """
    normalized: list[dict] = []
    for order, asset in enumerate(plan.assets):
        normalized.append(
            {
                "name": asset.name,
                "modality": asset.modality.value,
                "order": order,
                "spec": {
                    "description": asset.description,
                    "prompt": asset.prompt,
                    "rationale": asset.rationale,
                },
            }
        )
    return normalized


def make_plan_node(
    director: DirectorAgent,
) -> Callable[[DirectorState], Awaitable[dict]]:
    async def plan_node(state: DirectorState) -> dict:
        brief = state.get("brief")
        if not isinstance(brief, PlanBrief):
            return {"error": "plan_node requires a PlanBrief in state['brief']"}
        try:
            plan = await director.plan(brief)
        except Exception as exc:  # surface as state, don't crash the graph
            return {"error": f"planning failed: {exc}"}
        return {
            "plan": plan,
            "planned_assets": normalize_assets(plan),
            "error": None,
        }

    return plan_node
