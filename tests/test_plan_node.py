"""Plan node + director, verified in isolation (no network)."""

import pytest

from creative_director.domain.enums import Modality
from creative_director.orchestration import (
    AnthropicDirector,
    AssetPlanResult,
    DirectorError,
    FakeDirector,
    PlanBrief,
    PlannedAsset,
    build_plan_graph,
    make_plan_node,
    normalize_assets,
)

BRIEF = PlanBrief(
    goal="Launch a spring sneaker collection",
    target_modalities=[Modality.IMAGE, Modality.COPY],
    constraints={"tone": "earthy"},
    brand_config={"palette": ["sage", "clay"]},
    project_name="Spring",
    workspace_name="EverGreen",
)


async def test_fake_director_plans_requested_modalities():
    plan = await FakeDirector().plan(BRIEF)
    assert isinstance(plan, AssetPlanResult)
    modalities = {a.modality for a in plan.assets}
    assert modalities == {Modality.IMAGE, Modality.COPY}


def test_normalize_assets_shape_and_ordering():
    plan = AssetPlanResult(
        summary="s",
        assets=[
            PlannedAsset(
                name="Hero", modality=Modality.IMAGE, description="d",
                prompt="p", rationale="r",
            ),
            PlannedAsset(
                name="Caption", modality=Modality.COPY, description="d2",
                prompt="p2", rationale="r2",
            ),
        ],
    )
    normalized = normalize_assets(plan)
    assert [a["order"] for a in normalized] == [0, 1]
    assert normalized[0]["modality"] == "image"
    assert normalized[0]["spec"] == {"description": "d", "prompt": "p", "rationale": "r"}


async def test_plan_node_populates_state():
    node = make_plan_node(FakeDirector())
    update = await node({"brief": BRIEF})
    assert update["error"] is None
    assert isinstance(update["plan"], AssetPlanResult)
    assert len(update["planned_assets"]) == len(update["plan"].assets)
    assert update["planned_assets"][0]["order"] == 0


async def test_plan_node_requires_a_brief():
    node = make_plan_node(FakeDirector())
    update = await node({})
    assert "requires a PlanBrief" in update["error"]


async def test_plan_node_captures_director_failure():
    class Boom:
        async def plan(self, brief):
            raise RuntimeError("api down")

    update = await make_plan_node(Boom())({"brief": BRIEF})
    assert "planning failed" in update["error"]
    assert "api down" in update["error"]


async def test_plan_graph_runs_end_to_end():
    graph = build_plan_graph(FakeDirector())
    result = await graph.ainvoke({"brief": BRIEF})
    assert result["error"] is None
    assert result["plan"].summary
    assert result["planned_assets"]


# --- AnthropicDirector with an injected stub client (no network) ---

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


async def test_anthropic_director_sends_schema_and_brief():
    result = AssetPlanResult(
        summary="ok",
        assets=[PlannedAsset(
            name="Hero", modality=Modality.IMAGE, description="d", prompt="p", rationale="r"
        )],
    )
    client = _StubClient(result)
    director = AnthropicDirector(client=client, model="claude-opus-5")
    out = await director.plan(BRIEF)

    assert out is result
    call = client.messages.calls[0]
    assert call["model"] == "claude-opus-5"
    assert call["output_format"] is AssetPlanResult
    # The rendered brief reaches the model.
    assert "Launch a spring sneaker collection" in call["messages"][0]["content"]
    assert "image, copy" in call["messages"][0]["content"]


async def test_anthropic_director_raises_when_no_plan():
    client = _StubClient(None)
    director = AnthropicDirector(client=client)
    with pytest.raises(DirectorError):
        await director.plan(BRIEF)
