"""Pluggable generation-provider interface.

A provider turns a `GenerationRequest` into raw bytes plus metadata — it does not
touch storage or the DB (that's the generation service's job). Every provider
declares the single `Modality` it serves, so the registry can route an asset to
the right provider. Adding video/audio/text later means writing a new provider
class and registering it; nothing else changes.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from ..domain.enums import Modality


@dataclass(frozen=True)
class GenerationRequest:
    modality: Modality
    prompt: str
    params: dict = field(default_factory=dict)


@dataclass(frozen=True)
class GenerationResult:
    data: bytes
    content_type: str
    ext: str  # file extension without dot, e.g. "png"
    model: str = ""
    # Provider-reported extras: revised prompt, seed, raw params echoed back, etc.
    metadata: dict = field(default_factory=dict)


class ProviderError(Exception):
    pass


class GenerationProvider(ABC):
    #: Stable identifier stored on Version.provider, e.g. "openai-image".
    name: str
    #: The modality this provider produces.
    modality: Modality

    @abstractmethod
    async def generate(self, request: GenerationRequest) -> GenerationResult:
        ...


class ProviderRegistry:
    """Holds providers and routes by name or by modality (first registered wins
    as the modality default unless overridden)."""

    def __init__(self) -> None:
        self._by_name: dict[str, GenerationProvider] = {}
        self._default_by_modality: dict[Modality, str] = {}

    def register(self, provider: GenerationProvider, *, default: bool = False) -> None:
        self._by_name[provider.name] = provider
        if default or provider.modality not in self._default_by_modality:
            self._default_by_modality[provider.modality] = provider.name

    def get(self, name: str) -> GenerationProvider:
        try:
            return self._by_name[name]
        except KeyError:
            raise ProviderError(f"No provider named {name!r}") from None

    def for_modality(self, modality: Modality) -> GenerationProvider:
        name = self._default_by_modality.get(modality)
        if name is None:
            raise ProviderError(f"No provider registered for modality {modality!r}")
        return self._by_name[name]

    def names(self) -> list[str]:
        return sorted(self._by_name)
