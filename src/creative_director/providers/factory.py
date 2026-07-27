"""Build the ProviderRegistry from config.

Keyless stub providers are always registered (stub-image for IMAGE, stub-text for
COPY), so every wired modality runs offline. When IMAGE_PROVIDER=openai /
TEXT_PROVIDER=anthropic, the real provider is registered as that modality's
default; the stub stays reachable by name.
"""

from __future__ import annotations

from ..config import Settings
from .anthropic_text import AnthropicTextProvider
from .base import ProviderRegistry
from .openai_image import OpenAIImageProvider
from .stub import StubImageProvider
from .stub_text import StubTextProvider


def build_provider_registry(settings: Settings) -> ProviderRegistry:
    registry = ProviderRegistry()
    registry.register(StubImageProvider())
    registry.register(StubTextProvider())
    if settings.image_provider == "openai":
        registry.register(
            OpenAIImageProvider(settings.openai_api_key or ""), default=True
        )
    if settings.text_provider == "anthropic":
        registry.register(
            AnthropicTextProvider(
                api_key=settings.anthropic_api_key, model=settings.text_model
            ),
            default=True,
        )
    return registry
