"""Generation service: the seam that ties a provider to object storage.

Providers emit bytes; storage persists them; this coordinates the two and hands
back the `output_ref` that goes on a Version. The Generate node (Step 6) drives
this; keeping it here means that node stays a thin orchestration wrapper.
"""

from __future__ import annotations

from ..storage.base import ObjectStorage
from .base import GenerationProvider, GenerationRequest, GenerationResult


def media_key(workspace_id: str, asset_id: str, version_id: str, ext: str) -> str:
    """Namespaced storage key for a generated output."""
    return f"{workspace_id}/{asset_id}/{version_id}.{ext}"


async def generate_and_store(
    provider: GenerationProvider,
    storage: ObjectStorage,
    request: GenerationRequest,
    *,
    key: str,
) -> tuple[str, GenerationResult]:
    """Generate media and persist it. Returns (output_ref, result)."""
    result = await provider.generate(request)
    ref = await storage.save(key, result.data, content_type=result.content_type)
    return ref, result
