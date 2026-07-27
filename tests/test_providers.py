"""Provider interface, stub PNG generation, registry routing, OpenAI mapping."""

import base64

import httpx
import pytest

from creative_director.config import Settings
from creative_director.domain.enums import Modality
from creative_director.providers import (
    AnthropicTextProvider,
    GenerationRequest,
    OpenAIImageProvider,
    ProviderError,
    StubImageProvider,
    StubTextProvider,
    build_provider_registry,
    generate_and_store,
    media_key,
)
from creative_director.providers.stub import solid_png
from creative_director.storage import LocalStorage

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


async def test_stub_emits_valid_png():
    provider = StubImageProvider()
    result = await provider.generate(
        GenerationRequest(modality=Modality.IMAGE, prompt="a red bicycle", params={"size": "32x32"})
    )
    assert result.content_type == "image/png"
    assert result.ext == "png"
    assert result.data.startswith(PNG_SIGNATURE)
    assert result.metadata["width"] == 32


async def test_stub_is_deterministic_per_prompt():
    provider = StubImageProvider()
    req = GenerationRequest(modality=Modality.IMAGE, prompt="same prompt")
    a = await provider.generate(req)
    b = await provider.generate(req)
    assert a.data == b.data


def test_solid_png_is_decodable_header():
    data = solid_png(2, 2, (10, 20, 30))
    assert data.startswith(PNG_SIGNATURE)
    assert b"IHDR" in data and b"IDAT" in data and b"IEND" in data


def test_registry_defaults_to_stub_for_images():
    registry = build_provider_registry(Settings(_env_file=None, image_provider="stub"))
    provider = registry.for_modality(Modality.IMAGE)
    assert provider.name == "stub-image"
    assert registry.get("stub-image") is provider


def test_registry_routes_copy_to_a_text_provider():
    stub_reg = build_provider_registry(Settings(_env_file=None, text_provider="stub"))
    assert stub_reg.for_modality(Modality.COPY).name == "stub-text"

    anthropic_reg = build_provider_registry(
        Settings(_env_file=None, text_provider="anthropic", anthropic_api_key="sk-x")
    )
    assert anthropic_reg.for_modality(Modality.COPY).name == "anthropic-text"
    # stub stays reachable by name.
    assert anthropic_reg.get("stub-text").name == "stub-text"


async def test_stub_text_provider_emits_text_bytes():
    result = await StubTextProvider().generate(
        GenerationRequest(modality=Modality.COPY, prompt="Announce the spring line")
    )
    assert result.ext == "txt"
    assert result.content_type.startswith("text/plain")
    assert result.data.decode("utf-8") == "[stub copy] Announce the spring line"


async def test_anthropic_text_provider_decodes_and_sends_prompt():
    captured = {}

    class _Block:
        type = "text"

        def __init__(self, text):
            self.text = text

    class _Resp:
        stop_reason = "end_turn"

        def __init__(self, text):
            self.content = [_Block(text)]

    class _Messages:
        async def create(self, **kwargs):
            captured.update(kwargs)
            return _Resp("Step into spring. Lightweight, low-impact, all-day.")

    class _Client:
        messages = _Messages()

    provider = AnthropicTextProvider(client=_Client(), model="claude-opus-5")
    result = await provider.generate(
        GenerationRequest(modality=Modality.COPY, prompt="Write a hero tagline")
    )
    assert result.model == "claude-opus-5"
    assert result.data.decode("utf-8").startswith("Step into spring")
    assert captured["model"] == "claude-opus-5"
    assert captured["messages"][0]["content"] == "Write a hero tagline"


async def test_anthropic_text_provider_raises_on_refusal():
    class _Resp:
        stop_reason = "refusal"
        content = []

    class _Messages:
        async def create(self, **kwargs):
            return _Resp()

    class _Client:
        messages = _Messages()

    provider = AnthropicTextProvider(client=_Client())
    with pytest.raises(ProviderError):
        await provider.generate(GenerationRequest(modality=Modality.COPY, prompt="x"))


def test_registry_unknown_provider_raises():
    registry = build_provider_registry(Settings(_env_file=None))
    with pytest.raises(ProviderError):
        registry.get("does-not-exist")


async def test_generate_and_store_writes_real_bytes(tmp_path):
    provider = StubImageProvider()
    storage = LocalStorage(tmp_path)
    request = GenerationRequest(modality=Modality.IMAGE, prompt="hero shot")
    key = media_key("ws1", "asset1", "ver1", "png")
    ref, result = await generate_and_store(provider, storage, request, key=key)

    assert ref == "local://ws1/asset1/ver1.png"
    stored = await storage.load(ref)
    assert stored == result.data
    assert stored.startswith(PNG_SIGNATURE)


async def test_openai_provider_decodes_b64_and_sends_expected_payload():
    captured = {}
    png = solid_png(1, 1, (1, 2, 3))

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={"data": [{"b64_json": base64.b64encode(png).decode()}], "usage": {"total": 1}},
        )

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://api.openai.com"
    )
    provider = OpenAIImageProvider("sk-test", client=client)
    result = await provider.generate(
        GenerationRequest(modality=Modality.IMAGE, prompt="a cat", params={"size": "1024x1024"})
    )

    assert result.data == png
    assert result.model == "gpt-image-1"
    assert result.metadata["usage"] == {"total": 1}
    assert captured["url"].endswith("/v1/images/generations")
    assert captured["body"]["prompt"] == "a cat"
    assert captured["body"]["model"] == "gpt-image-1"
    assert captured["body"]["size"] == "1024x1024"
    await provider.aclose()


async def test_openai_provider_raises_on_error_status():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "bad key"})

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://api.openai.com"
    )
    provider = OpenAIImageProvider("sk-test", client=client)
    with pytest.raises(ProviderError):
        await provider.generate(GenerationRequest(modality=Modality.IMAGE, prompt="x"))
    await provider.aclose()
