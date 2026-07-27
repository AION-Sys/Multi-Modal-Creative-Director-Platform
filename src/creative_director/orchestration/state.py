"""Shared state for the director pipeline graph.

Only the Plan stage exists today; Generate/Critique/Review will add their own
keys to this same TypedDict as they're wired in. `total=False` so each node only
needs to return the keys it produces.
"""

from __future__ import annotations

from typing import TypedDict

from .director import PlanBrief
from .schemas import AssetPlanResult


class DirectorState(TypedDict, total=False):
    # --- input ---
    brief: PlanBrief
    # --- Plan stage output ---
    plan: AssetPlanResult | None
    # Normalized asset specs, ready to become Asset rows downstream.
    planned_assets: list[dict]
    error: str | None
