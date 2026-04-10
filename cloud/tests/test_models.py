"""Tests for request/response Pydantic models."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.models import SyncRequest, CorrectionPayload, LessonPayload, EventPayload


def test_sync_request_minimal():
    """Sync with just brain name and empty lists."""
    req = SyncRequest(brain_name="default", corrections=[], lessons=[], events=[])
    assert req.brain_name == "default"
    assert req.corrections == []


def test_sync_request_with_corrections():
    """Sync with correction payloads validates fields."""
    req = SyncRequest(
        brain_name="default",
        corrections=[
            CorrectionPayload(
                session=1,
                category="TONE",
                severity="minor",
                description="Too formal",
                draft_preview="Dear Sir,",
                final_preview="Hey,",
            )
        ],
        lessons=[],
        events=[],
    )
    assert len(req.corrections) == 1
    assert req.corrections[0].category == "TONE"


def test_correction_payload_invalid_severity():
    """Invalid severity rejected."""
    with pytest.raises(ValidationError):
        CorrectionPayload(
            session=1,
            category="TONE",
            severity="catastrophic",  # not in enum
            description="test",
        )


def test_lesson_payload_confidence_bounds():
    """Confidence must be 0.0-1.0."""
    with pytest.raises(ValidationError):
        LessonPayload(
            category="TONE",
            description="test",
            state="RULE",
            confidence=1.5,
        )


def test_event_payload_requires_type():
    """Event must have a type."""
    with pytest.raises(ValidationError):
        EventPayload(type="", source="sdk")  # type: ignore[arg-type]
