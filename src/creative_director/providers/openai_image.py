"""OpenAI image provider (gpt-image-1).

Calls the OpenAI Images API, which returns base64-encoded image bytes. The HTTP
client is injectable so the request/response handling can be unit-tested against
a mock transport without a live key.
"""

from __future__ import annotations

import base64

import httpx

from ..domain.enums import Modality
from .base import GenerationProvider, GenerationRequest, GenerationResult, ProviderError

_BASE_URL = "https://api.openai.com"
# Params we forward to the API if present in the request.
_PASSTHROUGH = ("size", "quality", "background", "output_format", "moderation")


class OpenAIImageProvider(GenerationProvider):
    name = "openai-image"
    modality = Modality.IMAGE

    def __init__(
        self,
        api_key: str,
        *,
        model: str = "gpt-image-1",
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not api_key and client is None:
            raise ProviderError("OpenAI API key is required")
        self._model = model
        self._client = client or httpx.AsyncClient(
            base_url=_BASE_URL,
            timeout=120.0,
            headers={"Authorization": f"Bearer {api_key}"},
        )

    async def generate(self, request: GenerationRequest) -> GenerationResult:
        payload: dict = {"model": self._model, "prompt": request.prompt, "n": 1}
        for key in _PASSTHROUGH:
            if key in request.params:
                payload[key] = request.params[key]

        resp = await self._client.post("/v1/images/generations", json=payload)
        if not resp.is_success:
            raise ProviderError(f"OpenAI images {resp.status_code}: {resp.text}")

        body = resp.json()
        try:
            entry = body["data"][0]
            data = base64.b64decode(entry["b64_json"])
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError(f"Unexpected OpenAI response shape: {body}") from exc

        fmt = str(payload.get("output_format", "png")).lower()
        ext = "jpg" if fmt in ("jpeg", "jpg") else fmt
        content_type = f"image/{'jpeg' if ext == 'jpg' else ext}"
        metadata = {"prompt": request.prompt}
        if "revised_prompt" in entry:
            metadata["revised_prompt"] = entry["revised_prompt"]
        if "usage" in body:
            metadata["usage"] = body["usage"]

        return GenerationResult(
            data=data,
            content_type=content_type,
            ext=ext,
            model=self._model,
            metadata=metadata,
        )

    async def aclose(self) -> None:
        await self._client.aclose()
