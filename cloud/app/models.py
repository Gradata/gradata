"""Pydantic request/response models for the sync API."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class Severity(str, Enum):
    trivial = "trivial"
    minor = "minor"
    moderate = "moderate"
    major = "major"
    rewrite = "rewrite"


class LessonState(str, Enum):
    INSTINCT = "INSTINCT"
    PATTERN = "PATTERN"
    RULE = "RULE"
    UNTESTABLE = "UNTESTABLE"
    ARCHIVED = "ARCHIVED"
    KILLED = "KILLED"


class CorrectionPayload(BaseModel):
    """A single correction from the SDK."""

    session: int
    category: str = Field(default="UNKNOWN", max_length=100)
    severity: Severity = Severity.minor
    description: str = Field(default="", max_length=2000)
    draft_preview: str = Field(default="", max_length=500)
    final_preview: str = Field(default="", max_length=500)
    created_at: str | None = None  # ISO timestamp from SDK; server uses now() if absent


class LessonPayload(BaseModel):
    """A lesson (graduated rule) from the SDK."""

    category: str = Field(max_length=100)
    description: str = Field(max_length=2000)
    state: LessonState = LessonState.INSTINCT
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    fire_count: int = 0
    recurrence_days: int | None = None


class EventPayload(BaseModel):
    """A raw event from events.jsonl."""

    type: str = Field(max_length=100)
    source: str = Field(default="", max_length=200)
    data: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list, max_length=20)
    session: int | None = None
    created_at: str | None = None

    @field_validator("type")
    @classmethod
    def type_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Event type cannot be empty")
        return v


class MetaRulePayload(BaseModel):
    """A meta-rule from the SDK."""

    title: str = Field(max_length=200)
    description: str = Field(max_length=2000)
    source_lesson_descriptions: list[str] = Field(default_factory=list, max_length=20)


class SyncRequest(BaseModel):
    """POST /api/v1/sync request body.

    The SDK calls this on end_session() when GRADATA_API_KEY is set.
    Sends all new corrections, lessons, events, and meta-rules since last sync.
    """

    brain_name: str = Field(default="default", max_length=100)
    corrections: list[CorrectionPayload] = Field(default_factory=list, max_length=500)
    lessons: list[LessonPayload] = Field(default_factory=list, max_length=500)
    events: list[EventPayload] = Field(default_factory=list, max_length=1000)
    meta_rules: list[MetaRulePayload] = Field(default_factory=list, max_length=100)
    manifest: dict[str, Any] = Field(default_factory=dict)


class SyncResponse(BaseModel):
    """POST /api/v1/sync response."""

    status: str = "ok"
    corrections_synced: int = 0
    lessons_synced: int = 0
    events_synced: int = 0
    meta_rules_synced: int = 0
