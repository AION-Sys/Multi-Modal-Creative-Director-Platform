"""Build the ProviderRegistry from config.

The stub image provider is always registered (keyless, name "stub-image"). When
IMAGE_PROVIDER=openai, the OpenAI provider is registered as the image default so
`registry.for_modality(IMAGE)` routes to it; the stub stays reachable by name.
"""

from __future__ import annotations

from ..config import Settings
from .base import ProviderRegistry
from .openai_image import OpenAIImageProvider
from .stub import StubImageProvider


def build_provider_registry(settings: Settings) -> ProviderRegistry:
    registry = ProviderRegistry()
    registry.register(StubImageProvider())
    if settings.image_provider == "openai":
        registry.register(
            OpenAIImageProvider(settings.openai_api_key or ""), default=True
        )
    return registry
