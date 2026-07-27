"""Self-critique node + director.critique, live with the keyless FakeDirector."""

import pytest

from creative_director.config import Settings
from creative_director.domain.enums import Modality, VersionVerdict
from creative_director.domain.models import Project, Workspace
from creative_director.orchestration import (
    AnthropicDirector,
    CritiqueRequest,
    CritiqueResult,
    FakeDirector,
    PlanBrief,
    build_pipeline_graph,
    make_critique_node,
    make_generate_node,
)
from creative_director.providers import build_provider_registry
from creative_director.repositories.factory import build_memory_repositories
from creative_director.storage import LocalStorage


@pytest.fixture
def repos():
    return build_memory_repositories()


@pytest.fixture
def providers():
    return build_provider_registry(Settings(_env_file=None, image_provider="stub"))


@pytest.fixture
def storage(tmp_path):
    return LocalStorage(tmp_path)


async def _generate_one_image(repos, providers, storage):
    ws = await repos.workspaces.create(Workspace(name="Acme"))
    proj = await repos.projects.create(
        Project(workspace_id=ws.id, name="Launch", goal="Ship the spring line")
    )
    gen = make_generate_node(repos, providers, storage)
    state = {
        "workspace_id": ws.id,
        "project_id": proj.id,
        "planned_assets": [
            {"name": "Hero", "modality": "image", "order": 0,
             "spec": {"description": "d", "prompt": "a red bicycle", "rationale": "r"}}
        ],
    }
    out = await gen(state)
    return ws, proj, {**state, **out}


async def test_critique_marks_version_pass(repos, providers, storage):
    ws, _, state = await _generate_one_image(repos, providers, storage)
    node = make_critique_node(FakeDirector(), repos, storage)

    brief = PlanBrief(goal="Ship it", target_modalities=[Modality.IMAGE])
    update = await node({**state, "brief": brief})

    assert update["error"] is None
    [critique] = update["critiques"]
    assert critique["verdict"] == "pass"

    version = await repos.versions.get(critique["version_id"], workspace_id=ws.id)
    assert version.verdict == VersionVerdict.PASS
    assert version.critique["score"] == 0.9
    assert "notes" in version.critique


async def test_critique_marks_version_regenerate(repos, providers, storage):
    ws, _, state = await _generate_one_image(repos, providers, storage)
    node = make_critique_node(FakeDirector(critique_verdict="regenerate"), repos, storage)

    update = await node(state)
    [critique] = update["critiques"]
    assert critique["verdict"] == "regenerate"

    version = await repos.versions.get(critique["version_id"], workspace_id=ws.id)
    assert version.verdict == VersionVerdict.REGENERATE
    assert version.critique["suggestions"]  # non-empty guidance on regenerate


async def test_critique_only_reviews_generated_results(repos, providers, storage):
    ws = await repos.workspaces.create(Workspace(name="Acme"))
    node = make_critique_node(FakeDirector(), repos, storage)
    # A skipped result carries no version to critique.
    update = await node(
        {"workspace_id": ws.id, "generated": [{"asset_id": "a", "status": "skipped"}]}
    )
    assert update["critiques"] == []


async def test_critique_requires_workspace(repos, storage):
    node = make_critique_node(FakeDirector(), repos, storage)
    update = await node({"generated": []})
    assert "requires workspace_id" in update["error"]


async def test_critique_node_passes_image_bytes_to_director(repos, providers, storage):
    ws, _, state = await _generate_one_image(repos, providers, storage)

    seen = {}

    class Recorder:
        async def critique(self, request: CritiqueRequest) -> CritiqueResult:
            seen["image_len"] = len(request.image) if request.image else 0
            seen["modality"] = request.modality
            return CritiqueResult(verdict="pass", score=1.0, notes="ok", suggestions="")

    await make_critique_node(Recorder(), repos, storage)(state)
    assert seen["image_len"] > 0  # real PNG bytes reached the director
    assert seen["modality"] == Modality.IMAGE


async def test_full_pipeline_plan_generate_critique(repos, providers, storage):
    ws = await repos.workspaces.create(Workspace(name="Acme"))
    proj = await repos.projects.create(
        Project(workspace_id=ws.id, name="Launch", goal="Ship spring line")
    )
    graph = build_pipeline_graph(FakeDirector(), repos, providers, storage)

    result = await graph.ainvoke(
        {
            "brief": PlanBrief(goal="Ship spring line",
                               target_modalities=[Modality.IMAGE, Modality.COPY]),
            "workspace_id": ws.id,
            "project_id": proj.id,
        }
    )
    assert result["error"] is None
    # One image was generated and therefore critiqued; copy was skipped.
    assert len(result["critiques"]) == 1
    assert result["critiques"][0]["verdict"] == "pass"


# --- AnthropicDirector.critique with an injected stub client (no network) ---

class _StubMessages:
    def __init__(self, result):
        self._result = result
        self.calls = []

    async def parse(self, **kwargs):
        self.calls.append(kwargs)

        class _Resp:
            parsed_output = self._result
            stop_reason = "end_turn"

        return _Resp()


class _StubClient:
    def __init__(self, result):
        self.messages = _StubMessages(result)


async def test_anthropic_director_critique_sends_image_and_schema():
    result = CritiqueResult(verdict="pass", score=0.8, notes="good", suggestions="")
    client = _StubClient(result)
    director = AnthropicDirector(client=client, model="claude-opus-5")

    out = await director.critique(
        CritiqueRequest(
            goal="Ship it", asset_name="Hero", modality=Modality.IMAGE,
            spec={"prompt": "a red bicycle"},
            image=b"\x89PNG-fake-bytes", image_content_type="image/png",
        )
    )
    assert out is result
    call = client.messages.calls[0]
    assert call["output_format"] is CritiqueResult
    blocks = call["messages"][0]["content"]
    assert any(b.get("type") == "image" for b in blocks)
    assert any(b.get("type") == "text" for b in blocks)
