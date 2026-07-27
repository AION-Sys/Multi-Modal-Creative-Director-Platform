"""Review loop (run_project + ReviewService), live with the keyless stack."""

import pytest

from creative_director.config import Settings
from creative_director.domain.enums import (
    AssetStatus,
    Modality,
    PipelineStatus,
    ProjectStatus,
    VersionVerdict,
)
from creative_director.domain.models import Project, Workspace
from creative_director.orchestration import FakeDirector
from creative_director.providers import build_provider_registry
from creative_director.repositories.factory import build_memory_repositories
from creative_director.services import ReviewService, run_project
from creative_director.storage import LocalStorage

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


@pytest.fixture
def repos():
    return build_memory_repositories()


@pytest.fixture
def providers():
    return build_provider_registry(Settings(_env_file=None, image_provider="stub"))


@pytest.fixture
def storage(tmp_path):
    return LocalStorage(tmp_path)


async def _run(repos, providers, storage, director):
    ws = await repos.workspaces.create(Workspace(name="Acme", brand_config={"palette": ["sage"]}))
    proj = await repos.projects.create(
        Project(
            workspace_id=ws.id, name="Launch", goal="Ship the spring line",
            target_modalities=[Modality.IMAGE, Modality.COPY],
        )
    )
    result = await run_project(director, repos, providers, storage, ws.id, proj.id)
    return ws, proj, result


async def test_run_project_records_pipeline_run_and_moves_project(repos, providers, storage):
    ws, proj, result = await _run(repos, providers, storage, FakeDirector())

    assert result["status"] == "awaiting_review"
    run = await repos.pipeline_runs.get(result["run_id"], workspace_id=ws.id)
    assert run.status == PipelineStatus.AWAITING_REVIEW
    # graph_state is JSON-safe (persisted for resumability).
    assert run.graph_state["plan_summary"]
    proj = await repos.projects.get(proj.id, workspace_id=ws.id)
    assert proj.status == ProjectStatus.REVIEW


async def test_pending_lists_image_asset_awaiting_review(repos, providers, storage):
    ws, proj, _ = await _run(repos, providers, storage, FakeDirector())
    review = ReviewService(repos, providers, storage, FakeDirector())

    items = await review.pending(ws.id, proj.id)
    # Image asset is in review; the skipped copy asset is not.
    assert len(items) == 1
    assert items[0].asset.modality == Modality.IMAGE
    assert items[0].version is not None
    assert items[0].version.verdict == VersionVerdict.PASS


async def test_approve_locks_the_asset(repos, providers, storage):
    ws, proj, _ = await _run(repos, providers, storage, FakeDirector())
    review = ReviewService(repos, providers, storage, FakeDirector())

    [item] = await review.pending(ws.id, proj.id)
    out = await review.approve(ws.id, item.version.id)
    assert out["status"] == "approved"

    asset = await repos.assets.get(item.asset.id, workspace_id=ws.id)
    assert asset.status == AssetStatus.APPROVED
    # Approved asset no longer appears as pending.
    assert await review.pending(ws.id, proj.id) == []


async def test_reject_marks_asset_rejected(repos, providers, storage):
    ws, proj, _ = await _run(repos, providers, storage, FakeDirector())
    review = ReviewService(repos, providers, storage, FakeDirector())
    [item] = await review.pending(ws.id, proj.id)

    out = await review.reject(ws.id, item.asset.id)
    assert out["status"] == "rejected"
    asset = await repos.assets.get(item.asset.id, workspace_id=ws.id)
    assert asset.status == AssetStatus.REJECTED


async def test_regenerate_branches_a_new_version(repos, providers, storage):
    # Critique says regenerate, so there's a suggestion to fold in.
    director = FakeDirector(critique_verdict="regenerate")
    ws, proj, _ = await _run(repos, providers, storage, director)
    review = ReviewService(repos, providers, storage, director)
    [item] = await review.pending(ws.id, proj.id)
    v1 = item.version

    out = await review.regenerate(ws.id, item.asset.id, prompt_suffix="more contrast")
    assert out["status"] == "generated"
    assert out["parent_version_id"] == v1.id  # branchable history

    versions = await repos.versions.list(workspace_id=ws.id, filters={"asset_id": item.asset.id})
    assert len(versions) == 2
    v2 = await repos.versions.get(out["version_id"], workspace_id=ws.id)
    # The regeneration prompt carried both the critique suggestion and the human tweak.
    assert "Adjustments from critique" in v2.prompt
    assert "more contrast" in v2.prompt
    # Real bytes were produced for the new version.
    assert (await storage.load(v2.output_ref)).startswith(PNG_SIGNATURE)


async def test_regenerate_with_recritique(repos, providers, storage):
    director = FakeDirector(critique_verdict="regenerate")
    ws, proj, _ = await _run(repos, providers, storage, director)
    review = ReviewService(repos, providers, storage, director)
    [item] = await review.pending(ws.id, proj.id)

    out = await review.regenerate(ws.id, item.asset.id, recritique=True)
    assert out["critique"]["verdict"] == "regenerate"
    v2 = await repos.versions.get(out["version_id"], workspace_id=ws.id)
    assert v2.verdict == VersionVerdict.REGENERATE


async def test_approve_unknown_version_raises(repos, providers, storage):
    from creative_director.services import ReviewError

    review = ReviewService(repos, providers, storage, FakeDirector())
    with pytest.raises(ReviewError):
        await review.approve("ws", "nope")
