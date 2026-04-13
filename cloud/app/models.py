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
    category: str = "UNKNOWN"
    severity: Severity = Severity.minor
    description: str = ""
    draft_preview: str = ""
    final_preview: str = ""
    created_at: str | None = None  # ISO timestamp from SDK; server uses now() if absent


class LessonPayload(BaseModel):
    """A lesson (graduated rule) from the SDK."""

    category: str
    description: str
    state: LessonState = LessonState.INSTINCT
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    fire_count: int = 0
    recurrence_days: int | None = None


class EventPayload(BaseModel):
    """A raw event from events.jsonl."""

    type: str
    source: str = ""
    data: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
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

    title: str
    description: str
    source_lesson_descriptions: list[str] = Field(default_factory=list)


class SyncRequest(BaseModel):
    """POST /api/v1/sync request body.

    The SDK calls this on end_session() when GRADATA_API_KEY is set.
    Sends all new corrections, lessons, events, and meta-rules since last sync.
    """

    brain_name: str = "default"
    corrections: list[CorrectionPayload] = Field(default_factory=list)
    lessons: list[LessonPayload] = Field(default_factory=list)
    events: list[EventPayload] = Field(default_factory=list)
    meta_rules: list[MetaRulePayload] = Field(default_factory=list)
    manifest: dict[str, Any] = Field(default_factory=dict)


class SyncResponse(BaseModel):
    """POST /api/v1/sync response."""

    status: str = "ok"
    corrections_synced: int = 0
    lessons_synced: int = 0
    events_synced: int = 0
    meta_rules_synced: int = 0


# ---------------------------------------------------------------------------
# User profile models
# ---------------------------------------------------------------------------


class UserProfile(BaseModel):
    user_id: str
    display_name: str | None = None
    email: str | None = None
    workspaces: list[dict] = Field(default_factory=list)
    created_at: str | None = None


class UpdateProfileRequest(BaseModel):
    display_name: str


class NotificationPrefs(BaseModel):
    """User notification preferences. SIM16 default: weekly digest, alerts opt-in."""

    alert_correction_spike: bool = True
    alert_rule_regression: bool = True
    alert_meta_rule_emerged: bool = False
    digest_cadence: str = "weekly"  # daily|weekly|monthly|off
    digest_email: str = ""           # blank = use account email
    slack_webhook: str = ""          # blank = no Slack delivery

    @field_validator("digest_cadence")
    @classmethod
    def cadence_valid(cls, v: str) -> str:
        if v not in {"daily", "weekly", "monthly", "off"}:
            raise ValueError("digest_cadence must be daily|weekly|monthly|off")
        return v


# ---------------------------------------------------------------------------
# API key models
# ---------------------------------------------------------------------------


class APIKeyResponse(BaseModel):
    id: str
    key_prefix: str  # last 4 chars only
    name: str = "default"
    created_at: str | None = None
    last_used: str | None = None


class CreateAPIKeyRequest(BaseModel):
    name: str = "Default"


class CreateAPIKeyResponse(BaseModel):
    id: str
    key: str  # plaintext — shown once only
    name: str


# ---------------------------------------------------------------------------
# Brain detail models
# ---------------------------------------------------------------------------


class BrainDetail(BaseModel):
    id: str
    user_id: str
    name: str | None = None
    domain: str | None = None
    lesson_count: int = 0
    correction_count: int = 0
    last_sync: str | None = None
    created_at: str | None = None


class UpdateBrainRequest(BaseModel):
    brain_name: str | None = None
    domain: str | None = None


# ---------------------------------------------------------------------------
# Analytics model
# ---------------------------------------------------------------------------


class BrainAnalytics(BaseModel):
    total_corrections: int = 0
    total_lessons: int = 0
    total_events: int = 0
    lessons_by_state: dict[str, int] = Field(default_factory=dict)
    corrections_by_severity: dict[str, int] = Field(default_factory=dict)
    corrections_by_category: dict[str, int] = Field(default_factory=dict)
    avg_confidence: float = 0.0
    graduation_rate: float = 0.0
    last_sync_at: str | None = None
    brain_created_at: str | None = None


# ---------------------------------------------------------------------------
# Billing models
# ---------------------------------------------------------------------------


class PlanTier(str, Enum):
    """Canonical Gradata plan tiers.

    `free` is the default tier (no Stripe sub).
    `cloud` and `team` are the paid Stripe tiers (S104: $29 / $99).
    `enterprise` is sales-only (never goes through Stripe Checkout).
    """

    free = "free"
    cloud = "cloud"
    team = "team"
    enterprise = "enterprise"


class CheckoutRequest(BaseModel):
    plan: PlanTier  # canonical tier; enterprise rejected at the route layer


class CheckoutResponse(BaseModel):
    checkout_url: str


class PortalResponse(BaseModel):
    """Stripe customer portal session URL."""

    url: str


class SubscriptionUsage(BaseModel):
    brains: int = 0
    lessons: int = 0
    events: int = 0


class SubscriptionResponse(BaseModel):
    plan: str | None = None
    status: str | None = None
    current_period_end: str | None = None
    usage: SubscriptionUsage = Field(default_factory=SubscriptionUsage)
