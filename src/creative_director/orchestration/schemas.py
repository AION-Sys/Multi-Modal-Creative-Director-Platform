"""Structured-output schemas for the director's Plan stage.

These Pydantic models are the *contract* the director agent must fill. They are
passed to `client.messages.parse(output_format=...)`, so the Anthropic API
constrains the model to emit exactly this shape — the Plan node never has to
parse free text or guess a modality. Kept schema-simple (strings + one enum, no
free-form dicts) because structured outputs require `additionalProperties: false`.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from ..domain.enums import Modality


class PlannedAsset(BaseModel):
    """One content piece the director wants produced for the brief."""

    name: str = Field(description="Short human-readable name, e.g. 'Hero image'.")
    modality: Modality = Field(description="Which content type this asset is.")
    description: str = Field(description="What this asset is and where it's used.")
    prompt: str = Field(
        description="A concrete, self-contained generation prompt for this asset, "
        "already reflecting the brand/style constraints."
    )
    rationale: str = Field(description="Why this asset serves the brief's goal.")


class AssetPlanResult(BaseModel):
    """The director's full plan for a brief."""

    summary: str = Field(description="One-paragraph overview of the plan.")
    assets: list[PlannedAsset] = Field(description="The ordered list of assets to produce.")


class CritiqueResult(BaseModel):
    """The director's self-critique of one generated output against the brief."""

    verdict: Literal["pass", "regenerate"] = Field(
        description="'pass' if the output satisfies the brief/spec, else 'regenerate'."
    )
    score: float = Field(description="Quality score from 0.0 (poor) to 1.0 (excellent).")
    notes: str = Field(description="What works and what doesn't, relative to the brief.")
    suggestions: str = Field(
        description="If regenerate: concrete prompt/param adjustments to try next. "
        "Empty when the verdict is pass."
    )
