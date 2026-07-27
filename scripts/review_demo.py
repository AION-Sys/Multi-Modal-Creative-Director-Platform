"""Demonstrate the full loop in one process, keyless.

Runs a project's pipeline, lists what's awaiting review, regenerates one asset
(branching a new version), then approves it. Memory backend + stub provider +
local disk, so it needs no external accounts.

    python scripts/review_demo.py
"""

from __future__ import annotations

import asyncio

from creative_director.config import Settings
from creative_director.domain.enums import Modality
from creative_director.domain.models import Project, Workspace
from creative_director.orchestration import FakeDirector
from creative_director.providers import build_provider_registry
from creative_director.repositories.factory import build_memory_repositories
from creative_director.services import ReviewService, run_project
from creative_director.storage import LocalStorage


async def main() -> None:
    repos = build_memory_repositories()
    providers = build_provider_registry(Settings(_env_file=None, image_provider="stub"))
    storage = LocalStorage("./.data/media")
    # Critique says 'regenerate' so the loop has something to act on.
    director = FakeDirector(critique_verdict="regenerate")
    review = ReviewService(repos, providers, storage, director)

    ws = await repos.workspaces.create(Workspace(name="EverGreen Footwear"))
    proj = await repos.projects.create(
        Project(
            workspace_id=ws.id, name="Spring Capsule",
            goal="Launch a spring capsule collection for a sustainable sneaker brand.",
            target_modalities=[Modality.IMAGE, Modality.COPY],
        )
    )

    run = await run_project(director, repos, providers, storage, ws.id, proj.id)
    print(f"RUN {run['run_id']} -> {run['status']}")
    print(f"  plan: {run['plan_summary']}")
    for c in run["critiques"]:
        print(f"  critique: {c['verdict']} (score {c['score']})")

    print("\nAWAITING REVIEW:")
    items = await review.pending(ws.id, proj.id)
    for item in items:
        print(f"  {item.asset.name} ({item.asset.modality.value}) "
              f"— version {item.version.id[:8]} verdict={item.version.verdict.value}")

    # Regenerate the first asset, folding in the critique + a human note.
    target = items[0].asset
    print(f"\nREGENERATE '{target.name}' (human note: 'warmer palette')")
    out = await review.regenerate(ws.id, target.id, prompt_suffix="warmer palette")
    print(f"  new version {out['version_id'][:8]} "
          f"(parent {out['parent_version_id'][:8]}) -> {out['status']}")

    # Approve the regenerated version.
    approved = await review.approve(ws.id, out["version_id"])
    print(f"\nAPPROVE -> {approved['status']}")
    asset = await repos.assets.get(target.id, workspace_id=ws.id)
    versions = await repos.versions.list(workspace_id=ws.id, filters={"asset_id": target.id})
    print(f"  asset status: {asset.status.value}; {len(versions)} version(s) in its history")


if __name__ == "__main__":
    asyncio.run(main())
