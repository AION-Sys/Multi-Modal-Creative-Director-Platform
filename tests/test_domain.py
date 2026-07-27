"""Smoke tests proving the scaffold imports and the domain model behaves."""

from creative_director.config import Settings
from creative_director.domain import (
    Asset,
    Modality,
    PipelineRun,
    Project,
    Version,
    VersionStatus,
    VersionVerdict,
    Workspace,
    WorkspaceKind,
)


def test_entities_get_unique_uuid_ids():
    a = Workspace(name="A")
    b = Workspace(name="B")
    assert a.id != b.id
    # UUIDs, not Airtable rec-ids.
    assert not a.id.startswith("rec")


def test_workspace_defaults():
    ws = Workspace(name="Personal")
    assert ws.kind == WorkspaceKind.PERSONAL
    assert ws.brand_config == {}
    assert ws.created_at.tzinfo is not None  # timezone-aware UTC


def test_project_asset_version_relationships():
    ws = Workspace(name="Acme", kind=WorkspaceKind.CLIENT)
    proj = Project(
        workspace_id=ws.id,
        name="Launch campaign",
        goal="Announce the spring line",
        target_modalities=[Modality.IMAGE, Modality.COPY],
    )
    asset = Asset(
        workspace_id=ws.id,
        project_id=proj.id,
        name="Hero image",
        modality=Modality.IMAGE,
    )
    version = Version(workspace_id=ws.id, asset_id=asset.id)

    assert proj.workspace_id == ws.id
    assert asset.project_id == proj.id
    assert version.asset_id == asset.id
    # Immutable-output defaults.
    assert version.status == VersionStatus.PENDING
    assert version.verdict == VersionVerdict.PENDING
    assert version.output_ref is None
    assert version.parent_version_id is None


def test_version_branching_chain():
    root = Version(workspace_id="w1", asset_id="a1")
    edit = Version(workspace_id="w1", asset_id="a1", parent_version_id=root.id)
    assert edit.parent_version_id == root.id


def test_pipeline_run_defaults():
    run = PipelineRun(workspace_id="w1", project_id="p1")
    assert run.current_node.value == "plan"
    assert run.status.value == "running"
    assert run.graph_state == {}


def test_settings_defaults_to_memory_backend():
    s = Settings(_env_file=None)
    assert s.backend == "memory"
    assert s.image_provider == "stub"


def test_enum_values_are_portable_strings():
    # Values must be plain lowercase strings for portable storage.
    assert Modality.IMAGE.value == "image"
    assert WorkspaceKind.CLIENT == "client"
