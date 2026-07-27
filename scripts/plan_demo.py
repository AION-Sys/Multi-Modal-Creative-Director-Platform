"""Run the Plan node in isolation against a couple of test briefs.

Uses the real Anthropic director when ANTHROPIC_API_KEY is set, otherwise the
keyless FakeDirector — so you can eyeball plan quality with a key, or just verify
the graph wiring without one.

    python scripts/plan_demo.py
"""

from __future__ import annotations

import asyncio
import os

from creative_director.config import get_settings
from creative_director.domain.enums import Modality
from creative_director.orchestration import (
    AnthropicDirector,
    FakeDirector,
    PlanBrief,
    build_plan_graph,
)

TEST_BRIEFS = [
    PlanBrief(
        goal="Launch a spring capsule collection for a sustainable sneaker brand.",
        target_modalities=[Modality.IMAGE, Modality.COPY],
        constraints={"tone": "optimistic, earthy", "audience": "eco-conscious Gen Z"},
        brand_config={"palette": ["sage", "clay", "cream"], "voice": "warm, direct"},
        project_name="Spring Capsule",
        workspace_name="EverGreen Footwear",
    ),
    PlanBrief(
        goal="Promote a weekend jazz festival in a coastal city.",
        target_modalities=[Modality.IMAGE],
        constraints={"tone": "sophisticated, nocturnal"},
        brand_config={"palette": ["midnight blue", "gold"]},
        project_name="Coastal Jazz Nights",
        workspace_name="Harbor Arts",
    ),
]


def _make_director():
    settings = get_settings()
    if os.environ.get("ANTHROPIC_API_KEY") or settings.anthropic_api_key:
        print(f"[using AnthropicDirector · model={settings.director_model}]\n")
        return AnthropicDirector(
            api_key=settings.anthropic_api_key, model=settings.director_model
        )
    print("[no ANTHROPIC_API_KEY — using FakeDirector]\n")
    return FakeDirector()


async def main() -> None:
    graph = build_plan_graph(_make_director())
    for brief in TEST_BRIEFS:
        result = await graph.ainvoke({"brief": brief})
        print("=" * 72)
        print(f"BRIEF: {brief.goal}")
        if result.get("error"):
            print(f"  ERROR: {result['error']}")
            continue
        plan = result["plan"]
        print(f"SUMMARY: {plan.summary}\n")
        for asset in result["planned_assets"]:
            print(f"  [{asset['order']}] {asset['name']}  ({asset['modality']})")
            print(f"      desc:   {asset['spec']['description']}")
            print(f"      prompt: {asset['spec']['prompt']}")
            print(f"      why:    {asset['spec']['rationale']}")
        print()


if __name__ == "__main__":
    asyncio.run(main())
