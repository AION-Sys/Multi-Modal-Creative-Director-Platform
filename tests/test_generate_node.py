"""Generate node + Plan->Generate pipeline, live with the keyless stub provider."""

import pytest

from creative_director.config import Settings
from creative_director.domain.enums import AssetStatus, Modality, VersionStatus
from creative_director.domain.models import Project, Workspace
from creative_director.orchestration import (
    FakeDirector,
    PlanBrief,
    build_pipeline_graph,
    make_generate_node,
)
from creative_director.providers import build_provider_registry
from creative_director.providers.base import (
    GenerationProvider,
    GenerationResult,
    ProviderError,
    ProviderRegistry,
)
from creative_director.repositories.factory import build_memory_repositories
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


async def _workspace_and_project(repos):
    ws = await repos.workspaces.create(Workspace(name="Acme"))
    proj = await repos.projects.create(
        Project(workspace_id=ws.id, name="Launch", goal="Ship the spring line")
    )
    return ws, proj


def _planned(modality: str, order: int) -> dict:
    return {
        "name": f"{modality} asset",
        "modality": modality,
        "order": order,
        "spec": {"description": "d", "prompt": "a red bicycle", "rationale": "r"},
    }


async def test_generate_creates_version_and_stores_real_bytes(repos, providers, storage):
    ws, proj = await _workspace_and_project(repos)
    node = make_generate_node(repos, providers, storage)

    update = await node(
        {
            "workspace_id": ws.id,
            "project_id": proj.id,
            "planned_assets": [_planned("image", 0)],
        }
    )

    assert update["error"] is None
    [result] = update["generated"]
    assert result["status"] == "generated"
    assert result["provider"] == "stub-image"

    # Asset persisted and advanced to review.
    asset = await repos.assets.get(result["asset_id"], workspace_id=ws.id)
    assert asset.status == AssetStatus.REVIEW
    assert asset.modality == Modality.IMAGE

    # Version persisted, ready, with a resolvable output_ref.
    version = await repos.versions.get(result["version_id"], workspace_id=ws.id)
    assert version.status == VersionStatus.READY
    assert version.output_ref == result["output_ref"]

    # The stored bytes are a real PNG.
    data = await storage.load(version.output_ref)
    assert data.startswith(PNG_SIGNATURE)


async def test_generate_skips_modality_without_a_provider(repos, providers, storage):
    ws, proj = await _workspace_and_project(repos)
    node = make_generate_node(repos, providers, storage)

    update = await node(
        {
            "workspace_id": ws.id,
            "project_id": proj.id,
            "planned_assets": [_planned("image", 0), _planned("copy", 1)],
        }
    )

    by_status = {r["status"] for r in update["generated"]}
    assert by_status == {"generated", "skipped"}
    copy_result = next(r for r in update["generated"] if r["status"] == "skipped")
    assert "no provider" in copy_result["reason"]
    # Both assets were still persisted.
    assert len(update["asset_ids"]) == 2
    # No version was created for the skipped copy asset.
    copy_asset_id = copy_result["asset_id"]
    assert await repos.versions.list(workspace_id=ws.id, filters={"asset_id": copy_asset_id}) == []


async def test_generate_requires_workspace_and_project(repos, providers, storage):
    node = make_generate_node(repos, providers, storage)
    update = await node({"planned_assets": [_planned("image", 0)]})
    assert "requires workspace_id and project_id" in update["error"]


async def test_generation_failure_marks_version_failed(repos, storage):
    ws, proj = await _workspace_and_project(repos)

    class FailingImage(GenerationProvider):
        name = "failing-image"
        modality = Modality.IMAGE

        async def generate(self, request) -> GenerationResult:
            raise ProviderError("provider exploded")

    registry = ProviderRegistry()
    registry.register(FailingImage())
    node = make_generate_node(repos, registry, storage)

    update = await node(
        {
            "workspace_id": ws.id,
            "project_id": proj.id,
            "planned_assets": [_planned("image", 0)],
        }
    )
    [result] = update["generated"]
    assert result["status"] == "failed"
    assert "provider exploded" in result["error"]

    version = await repos.versions.get(result["version_id"], workspace_id=ws.id)
    assert version.status == VersionStatus.FAILED
    assert version.output_ref is None


async def test_full_pipeline_plan_then_generate(repos, providers, storage):
    ws, proj = await _workspace_and_project(repos)
    graph = build_pipeline_graph(FakeDirector(), repos, providers, storage)

    result = await graph.ainvoke(
        {
            "brief": PlanBrief(
                goal="Launch spring line",
                target_modalities=[Modality.IMAGE, Modality.COPY],
            ),
            "workspace_id": ws.id,
            "project_id": proj.id,
        }
    )

    assert result["error"] is None
    # Plan produced two assets; generate produced one image version + one skip.
    assert len(result["planned_assets"]) == 2
    statuses = sorted(r["status"] for r in result["generated"])
    assert statuses == ["generated", "skipped"]

    # An image Version exists in the store with real bytes.
    generated = next(r for r in result["generated"] if r["status"] == "generated")
    data = await storage.load(generated["output_ref"])
    assert data.startswith(PNG_SIGNATURE)
