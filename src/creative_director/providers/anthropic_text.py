"""Anthropic copy provider — Claude writes marketing copy for a copy asset.

Same GenerationProvider contract as the image providers: prompt in, bytes out
(UTF-8 text here). The async client is injectable so request/response handling is
unit-testable without a live key.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..domain.enums import Modality
from .base import GenerationProvider, GenerationRequest, GenerationResult, ProviderError

if TYPE_CHECKING:
    from anthropic import AsyncAnthropic

_SYSTEM = (
    "You are a brand copywriter. Write the requested copy, reflecting any "
    "brand/style constraints described in the prompt. Return only the copy "
    "itself — no preamble, no surrounding quotation marks, no explanation."
)


class AnthropicTextProvider(GenerationProvider):
    name = "anthropic-text"
    modality = Modality.COPY

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str = "claude-opus-5",
        max_tokens: int = 2000,
        client: AsyncAnthropic | None = None,
    ) -> None:
        self._model = model
        self._max_tokens = max_tokens
        if client is not None:
            self._client = client
        else:
            from anthropic import AsyncAnthropic

            self._client = AsyncAnthropic(api_key=api_key) if api_key else AsyncAnthropic()

    async def generate(self, request: GenerationRequest) -> GenerationResult:
        response = await self._client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            system=_SYSTEM,
            messages=[{"role": "user", "content": request.prompt}],
        )
        if getattr(response, "stop_reason", None) == "refusal":
            raise ProviderError("copy generation refused by the model")
        text = "".join(
            block.text for block in response.content if getattr(block, "type", None) == "text"
        ).strip()
        if not text:
            raise ProviderError("copy generation returned no text")
        return GenerationResult(
            data=text.encode("utf-8"),
            content_type="text/plain; charset=utf-8",
            ext="txt",
            model=self._model,
            metadata={"prompt": request.prompt, "chars": len(text)},
        )

    async def aclose(self) -> None:
        await self._client.aclose()
