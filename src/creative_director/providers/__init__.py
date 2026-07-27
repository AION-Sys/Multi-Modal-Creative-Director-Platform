"""Generation providers: pluggable interface + image providers + registry."""

from .anthropic_text import AnthropicTextProvider
from .base import (
    GenerationProvider,
    GenerationRequest,
    GenerationResult,
    ProviderError,
    ProviderRegistry,
)
from .factory import build_provider_registry
from .openai_image import OpenAIImageProvider
from .service import generate_and_store, media_key
from .stub import StubImageProvider
from .stub_text import StubTextProvider

__all__ = [
    "AnthropicTextProvider",
    "GenerationProvider",
    "GenerationRequest",
    "GenerationResult",
    "OpenAIImageProvider",
    "ProviderError",
    "ProviderRegistry",
    "StubImageProvider",
    "StubTextProvider",
    "build_provider_registry",
    "generate_and_store",
    "media_key",
]
