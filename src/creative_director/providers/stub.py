"""Keyless stub image provider.

Produces a genuine (valid, decodable) solid-color PNG whose color is derived
deterministically from the prompt — no external service, no API key, no Pillow.
This lets the full brief -> plan -> generate -> store -> review loop run and be
tested end-to-end with real bytes on real storage.
"""

from __future__ import annotations

import hashlib
import struct
import zlib

from ..domain.enums import Modality
from .base import GenerationProvider, GenerationRequest, GenerationResult


def _chunk(tag: bytes, data: bytes) -> bytes:
    return (
        struct.pack(">I", len(data))
        + tag
        + data
        + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    )


def solid_png(width: int, height: int, rgb: tuple[int, int, int]) -> bytes:
    """Build a minimal valid RGB PNG filled with one color."""
    signature = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    row = b"\x00" + bytes(rgb) * width  # filter byte 0 (None) + RGB pixels
    raw = row * height
    idat = zlib.compress(raw, 9)
    return signature + _chunk(b"IHDR", ihdr) + _chunk(b"IDAT", idat) + _chunk(b"IEND", b"")


def _color_from_prompt(prompt: str) -> tuple[int, int, int]:
    digest = hashlib.sha256(prompt.encode("utf-8")).digest()
    return digest[0], digest[1], digest[2]


def _dimensions(params: dict) -> tuple[int, int]:
    size = str(params.get("size", "64x64"))
    try:
        w, h = (int(v) for v in size.lower().split("x", 1))
        # Keep the stub cheap regardless of requested size.
        return min(w, 64), min(h, 64)
    except (ValueError, TypeError):
        return 64, 64


class StubImageProvider(GenerationProvider):
    name = "stub-image"
    modality = Modality.IMAGE

    async def generate(self, request: GenerationRequest) -> GenerationResult:
        width, height = _dimensions(request.params)
        data = solid_png(width, height, _color_from_prompt(request.prompt))
        return GenerationResult(
            data=data,
            content_type="image/png",
            ext="png",
            model="stub",
            metadata={"width": width, "height": height, "prompt": request.prompt},
        )
