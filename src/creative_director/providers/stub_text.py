"""Keyless stub copy provider.

Emits deterministic UTF-8 text derived from the prompt, so the copy modality runs
and is tested end-to-end (generate -> store -> critique) with no API key.
"""

from __future__ import annotations

from ..domain.enums import Modality
from .base import GenerationProvider, GenerationRequest, GenerationResult


class StubTextProvider(GenerationProvider):
    name = "stub-text"
    modality = Modality.COPY

    async def generate(self, request: GenerationRequest) -> GenerationResult:
        text = f"[stub copy] {request.prompt}".strip()
        return GenerationResult(
            data=text.encode("utf-8"),
            content_type="text/plain; charset=utf-8",
            ext="txt",
            model="stub",
            metadata={"prompt": request.prompt, "chars": len(text)},
        )
