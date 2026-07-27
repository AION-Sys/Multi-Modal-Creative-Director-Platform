"""Run the Plan -> Generate pipeline end-to-end, keyless.

Uses the in-memory backend, the stub image provider, and local disk storage, so
it runs with no external accounts. It creates a workspace + project, plans a
brief, generates + stores real image bytes, and prints the resulting Versions.

    python scripts/pipeline_demo.py
"""

from __future__ import annotations

import asyncio
import os

from creative_director.config import Settings
from creative_director.domain.enums import Modality
from creative_director.domain.models import Project, Workspace
from creative_director.orchestration import (
    AnthropicDirector,
    FakeDirector,
    PlanBrief,
    build_pipeline_graph,
)
from creative_director.providers import build_provider_registry
from creative_director.repositories.factory import build_memory_repositories
from creative_director.storage import LocalStorage

BRIEF = PlanBrief(
    goal="Launch a spring capsule collection for a sustainable sneaker brand.",
    target_modalities=[Modality.IMAGE, Modality.COPY],
    constraints={"tone": "optimistic, earthy"},
    brand_config={"palette": ["sage", "clay", "cream"]},
    project_name="Spring Capsule",
    workspace_name="EverGreen Footwear",
)


def _director():
    settings = Settings(_env_file=None)
    if os.environ.get("ANTHROPIC_API_KEY"):
        print(f"[director: Anthropic · {settings.director_model}]")
        return AnthropicDirector(model=settings.director_model)
    print("[director: FakeDirector (no ANTHROPIC_API_KEY)]")
    return FakeDirector()


async def main() -> None:
    repos = build_memory_repositories()
    providers = build_provider_registry(Settings(_env_file=None, image_provider="stub"))
    storage = LocalStorage("./.data/media")

    ws = await repos.workspaces.create(Workspace(name=BRIEF.workspace_name))
    proj = await repos.projects.create(
        Project(workspace_id=ws.id, name=BRIEF.project_name, goal=BRIEF.goal,
                target_modalities=BRIEF.target_modalities)
    )

    graph = build_pipeline_graph(_director(), repos, providers, storage)
    result = await graph.ainvoke(
        {"brief": BRIEF, "workspace_id": ws.id, "project_id": proj.id}
    )

    print(f"\nPLAN: {result['plan'].summary}\n")
    for r in result["generated"]:
        if r["status"] == "generated":
            data = await storage.load(r["output_ref"])
            print(f"  ✅ {r['status']:<9} {r['output_ref']}  "
                  f"({len(data)} bytes, provider={r['provider']})")
        elif r["status"] == "skipped":
            print(f"  ⏭  {r['status']:<9} asset {r['asset_id']} — {r['reason']}")
        else:
            print(f"  ❌ {r['status']:<9} asset {r['asset_id']} — {r.get('error')}")

    if result.get("critiques"):
        print("\nCRITIQUE:")
        for c in result["critiques"]:
            print(f"  {c['verdict']:<10} score={c['score']}  version={c['version_id']}")

    versions = await repos.versions.list(workspace_id=ws.id)
    print(f"\n{len(versions)} Version row(s) persisted; "
          f"media under ./.data/media/")


if __name__ == "__main__":
    asyncio.run(main())
