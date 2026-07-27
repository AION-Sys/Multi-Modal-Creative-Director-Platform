"""Generation providers: pluggable interface + image providers + registry."""

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

__all__ = [
    "GenerationProvider",
    "GenerationRequest",
    "GenerationResult",
    "OpenAIImageProvider",
    "ProviderError",
    "ProviderRegistry",
    "StubImageProvider",
    "build_provider_registry",
    "generate_and_store",
    "media_key",
]
