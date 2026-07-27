"""The director agent — the Anthropic-backed planner, behind a small interface.

`DirectorAgent` is the seam the Plan node depends on. `AnthropicDirector` is the
real implementation (Claude via structured outputs); `FakeDirector` lets the node
and graph be tested end-to-end with no API key. The Anthropic client is
injectable so `AnthropicDirector` can be unit-tested against a stub client too.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol

from ..domain.enums import Modality
from .schemas import AssetPlanResult, CritiqueResult

if TYPE_CHECKING:  # avoid importing the SDK unless the real director is used
    from anthropic import AsyncAnthropic


@dataclass(frozen=True)
class PlanBrief:
    """Everything the director needs to turn a brief into an asset plan."""

    goal: str
    target_modalities: list[Modality]
    constraints: dict = field(default_factory=dict)
    brand_config: dict = field(default_factory=dict)
    project_name: str = ""
    workspace_name: str = ""


@dataclass(frozen=True)
class CritiqueRequest:
    """One generated output to be reviewed against the brief.

    For images, `image` carries the bytes (vision critique); for copy, `text`
    carries the generated text. `spec` is the Asset's spec (description/prompt/
    rationale) so the director judges against what was asked for.
    """

    goal: str
    asset_name: str
    modality: Modality
    spec: dict
    image: bytes | None = None
    image_content_type: str | None = None
    text: str | None = None


class DirectorError(Exception):
    pass


class DirectorAgent(Protocol):
    async def plan(self, brief: PlanBrief) -> AssetPlanResult:
        ...

    async def critique(self, request: CritiqueRequest) -> CritiqueResult:
        ...


_SYSTEM_PROMPT = (
    "You are a creative director. Given a brief (a goal plus brand/style "
    "constraints) you produce a concrete asset plan: the specific pieces of "
    "content that, together, achieve the goal. For each asset give a clear name, "
    "its modality, a short description of what it is and where it's used, a "
    "self-contained generation prompt that already bakes in the brand/style "
    "constraints, and a one-line rationale tying it to the goal. Only plan assets "
    "in the requested modalities. Prefer a focused plan of high-impact assets over "
    "an exhaustive one."
)


_CRITIQUE_SYSTEM = (
    "You are a creative director reviewing a generated asset against its brief. "
    "Judge whether the output satisfies the goal and the asset's spec (its intended "
    "description, the generation prompt, and its rationale). Return a verdict of "
    "'pass' if it's good enough to move to human review, or 'regenerate' if it "
    "should be redone. Give an honest quality score, concise notes on what works "
    "and what doesn't, and — only when regenerating — concrete prompt/param "
    "adjustments to try next."
)


def _render_critique(request: CritiqueRequest) -> str:
    spec = request.spec or {}
    lines = [
        f"Goal: {request.goal}",
        f"Asset: {request.asset_name} ({request.modality.value})",
        f"Intended description: {spec.get('description', '')}",
        f"Generation prompt used: {spec.get('prompt', '')}",
        f"Rationale: {spec.get('rationale', '')}",
    ]
    if request.image is not None:
        lines.append("\nThe generated image is attached. Review it against the above.")
    if request.text:
        lines.append("\nReview the generated copy provided below against the above.")
    return "\n".join(lines)


def _render_brief(brief: PlanBrief) -> str:
    modalities = ", ".join(m.value for m in brief.target_modalities) or "(unspecified)"
    lines = [
        f"Goal: {brief.goal}",
        f"Target modalities: {modalities}",
    ]
    if brief.workspace_name:
        lines.append(f"Workspace: {brief.workspace_name}")
    if brief.project_name:
        lines.append(f"Project: {brief.project_name}")
    if brief.constraints:
        lines.append(f"Constraints: {brief.constraints}")
    if brief.brand_config:
        lines.append(f"Brand/style config: {brief.brand_config}")
    lines.append(
        "\nProduce the asset plan now. Every asset's modality must be one of the "
        "target modalities above."
    )
    return "\n".join(lines)


class AnthropicDirector:
    """Real director: Claude via structured outputs (schema-constrained plan)."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str = "claude-opus-5",
        max_tokens: int = 8000,
        client: AsyncAnthropic | None = None,
    ) -> None:
        self._model = model
        self._max_tokens = max_tokens
        if client is not None:
            self._client = client
        else:
            from anthropic import AsyncAnthropic

            # AsyncAnthropic resolves credentials from the env when api_key is None.
            self._client = AsyncAnthropic(api_key=api_key) if api_key else AsyncAnthropic()

    async def plan(self, brief: PlanBrief) -> AssetPlanResult:
        response = await self._client.messages.parse(
            model=self._model,
            max_tokens=self._max_tokens,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": _render_brief(brief)}],
            output_format=AssetPlanResult,
        )
        parsed = response.parsed_output
        if parsed is None:
            raise DirectorError(
                f"Director returned no parseable plan (stop={response.stop_reason})"
            )
        return parsed

    async def critique(self, request: CritiqueRequest) -> CritiqueResult:
        import base64

        content: list[dict] = [{"type": "text", "text": _render_critique(request)}]
        if request.image is not None:
            content.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": request.image_content_type or "image/png",
                        "data": base64.b64encode(request.image).decode(),
                    },
                }
            )
        if request.text:
            content.append({"type": "text", "text": f"Generated copy:\n{request.text}"})

        response = await self._client.messages.parse(
            model=self._model,
            max_tokens=self._max_tokens,
            system=_CRITIQUE_SYSTEM,
            messages=[{"role": "user", "content": content}],
            output_format=CritiqueResult,
        )
        parsed = response.parsed_output
        if parsed is None:
            raise DirectorError(
                f"Director returned no parseable critique (stop={response.stop_reason})"
            )
        return parsed


class FakeDirector:
    """Deterministic director for tests/keyless demos.

    Emits one image asset plus one asset per other requested modality, so the
    Plan node and graph can be exercised without any network call.
    """

    def __init__(
        self, *, per_modality: int = 1, critique_verdict: str = "pass"
    ) -> None:
        self._per_modality = per_modality
        self._critique_verdict = critique_verdict

    async def plan(self, brief: PlanBrief) -> AssetPlanResult:
        from .schemas import PlannedAsset

        modalities = brief.target_modalities or [Modality.IMAGE]
        assets: list[PlannedAsset] = []
        for modality in modalities:
            for i in range(self._per_modality):
                suffix = f" {i + 1}" if self._per_modality > 1 else ""
                assets.append(
                    PlannedAsset(
                        name=f"{modality.value.title()} asset{suffix}",
                        modality=modality,
                        description=f"A {modality.value} asset supporting: {brief.goal}",
                        prompt=f"{brief.goal} — {modality.value}, styled per brand constraints.",
                        rationale=f"Advances the goal via the {modality.value} channel.",
                    )
                )
        return AssetPlanResult(
            summary=f"Plan of {len(assets)} asset(s) for: {brief.goal}",
            assets=assets,
        )

    async def critique(self, request: CritiqueRequest) -> CritiqueResult:
        passed = self._critique_verdict == "pass"
        return CritiqueResult(
            verdict="pass" if passed else "regenerate",
            score=0.9 if passed else 0.4,
            notes=f"Reviewed '{request.asset_name}' against the goal.",
            suggestions="" if passed else "Increase contrast and tighten to the brand palette.",
        )
