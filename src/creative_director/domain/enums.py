"""Canonical enums.

These live in Python (not just as Airtable single-select choices) so that the
allowed values survive the eventual Airtable -> Postgres migration unchanged.
All values are lowercase strings for portable storage.
"""

from __future__ import annotations

# StrEnum (3.11+) serializes members as their plain string value in JSON/Airtable.
from enum import StrEnum


class WorkspaceKind(StrEnum):
    PERSONAL = "personal"
    CLIENT = "client"


class Modality(StrEnum):
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    COPY = "copy"


class ProjectStatus(StrEnum):
    DRAFT = "draft"
    PLANNING = "planning"
    GENERATING = "generating"
    REVIEW = "review"
    COMPLETE = "complete"
    ARCHIVED = "archived"


class AssetStatus(StrEnum):
    PLANNED = "planned"
    GENERATING = "generating"
    REVIEW = "review"
    APPROVED = "approved"
    REJECTED = "rejected"


class VersionStatus(StrEnum):
    """Lifecycle of a single generation output."""

    PENDING = "pending"
    READY = "ready"
    FAILED = "failed"


class VersionVerdict(StrEnum):
    """Outcome of the director's self-critique on a version."""

    PENDING = "pending"
    PASS = "pass"
    REGENERATE = "regenerate"


class PipelineNode(StrEnum):
    """Which director stage a run is at (mirrors the LangGraph nodes)."""

    PLAN = "plan"
    GENERATE = "generate"
    CRITIQUE = "critique"
    REVIEW = "review"
    DONE = "done"


class PipelineStatus(StrEnum):
    RUNNING = "running"
    PAUSED = "paused"
    AWAITING_REVIEW = "awaiting_review"
    COMPLETE = "complete"
    FAILED = "failed"
