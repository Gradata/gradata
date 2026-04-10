"""
Memory Taxonomy — Typed memory units for the learning pipeline.
================================================================
Adapted from: EverOS (EverMind-AI/EverOS) memory_types.py

Maps EverOS's 5 memory types to Gradata's learning domain:
  Episodic    → CorrectionNarrative (what happened, full story)
  EventLog    → AtomicFact (individual facts extracted from corrections)
  Foresight   → PredictedImpact (predicted future effect of a lesson)
  Profile     → BrainProfile (accumulated brain characteristics)
  GroupProfile → CrossBrainProfile (patterns shared across brains)

Key insight from EverOS: Foresight memories are forward-looking predictions
stored as first-class objects with temporal bounds. This enables proactive
rule application ("this lesson will matter when X happens").

Usage::

    from gradata.enhancements.memory_taxonomy import (
        MemoryType, CorrectionNarrative, AtomicFact,
        PredictedImpact, BrainProfile, CrossBrainProfile,
        classify_memory_type,
    )

    narrative = CorrectionNarrative(
        subject="Email tone too formal",
        summary="User corrected formal language to casual",
        episode="Full correction narrative...",
        severity="moderate",
        evidence_ids=["evt_123", "evt_124"],
    )

    impact = PredictedImpact(
        prediction="Will affect all future email drafts",
        evidence="3 corrections on tone in last 5 sessions",
        duration_days=30,
    )
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

__all__ = [
    "AtomicFact",
    "BaseMemoryUnit",
    "BrainProfile",
    "CorrectionNarrative",
    "CrossBrainProfile",
    "MemoryType",
    "PredictedImpact",
    "ProfileField",
    "SharedPattern",
    "classify_memory_type",
]


class MemoryType(Enum):
    """Five memory types for the learning pipeline.

    Adapted from EverOS's episodic/eventlog/foresight/profile/group taxonomy.
    """
    CORRECTION_NARRATIVE = "correction_narrative"  # Full story of a correction
    ATOMIC_FACT = "atomic_fact"                     # Individual extracted facts
    PREDICTED_IMPACT = "predicted_impact"           # Forward-looking predictions
    BRAIN_PROFILE = "brain_profile"                 # Accumulated characteristics
    CROSS_BRAIN_PROFILE = "cross_brain_profile"     # Cross-brain shared patterns


@dataclass
class BaseMemoryUnit:
    """Base class for all memory units.

    Attributes:
        memory_type: Which of the 5 types this is.
        timestamp: When this memory was created (unix time).
        session_id: Session that produced this memory.
        brain_id: Brain this memory belongs to.
        evidence_ids: Event IDs that support this memory.
        vector: Optional embedding vector for similarity search.
        metadata: Arbitrary metadata.
    """
    memory_type: MemoryType = MemoryType.CORRECTION_NARRATIVE  # Overridden by subclass __post_init__
    timestamp: float = 0.0
    session_id: str = ""
    brain_id: str = ""
    evidence_ids: list[str] = field(default_factory=list)
    vector: list[float] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.timestamp == 0.0:
            self.timestamp = time.time()


# ---------------------------------------------------------------------------
# Type 1: CorrectionNarrative (Episodic)
# ---------------------------------------------------------------------------

@dataclass
class CorrectionNarrative(BaseMemoryUnit):
    """Full narrative of a correction event.

    Stores the complete story: what was produced, what was corrected,
    why, and the outcome. Adapted from EverOS's EpisodeMemory.

    Attributes:
        subject: Short title for the correction.
        summary: One-paragraph summary.
        episode: Full narrative text with context.
        severity: Correction severity (trivial/minor/moderate/major/rewrite).
        original_output: What the brain originally produced.
        corrected_output: What the correction changed it to.
        task_type: Type of task where correction happened.
    """
    subject: str = ""
    summary: str = ""
    episode: str = ""
    severity: str = ""
    original_output: str = ""
    corrected_output: str = ""
    task_type: str = ""

    def __post_init__(self) -> None:
        self.memory_type = MemoryType.CORRECTION_NARRATIVE
        super().__post_init__()


# ---------------------------------------------------------------------------
# Type 2: AtomicFact (EventLog)
# ---------------------------------------------------------------------------

@dataclass
class AtomicFact(BaseMemoryUnit):
    """Individual fact extracted from a correction or session.

    Adapted from EverOS's EventLog. Each fact is independent and
    self-contained, making it suitable for fine-grained retrieval.

    Attributes:
        facts: List of atomic fact strings.
        source_type: Where this fact was extracted from (correction/session/rule).
        confidence: How confident we are in this fact (0.0-1.0).
    """
    facts: list[str] = field(default_factory=list)
    source_type: str = "correction"
    confidence: float = 1.0

    def __post_init__(self) -> None:
        self.memory_type = MemoryType.ATOMIC_FACT
        super().__post_init__()

    @property
    def fact_count(self) -> int:
        return len(self.facts)


# ---------------------------------------------------------------------------
# Type 3: PredictedImpact (Foresight) — Novel from EverOS
# ---------------------------------------------------------------------------

@dataclass
class PredictedImpact(BaseMemoryUnit):
    """Forward-looking prediction about a lesson's future impact.

    This is the novel type from EverOS. Instead of only recording what
    happened (backward-looking), Foresight memories predict what WILL
    happen based on the lesson learned.

    Enables proactive rule application: "this lesson will matter when
    the brain encounters task type X within the next N days."

    Attributes:
        prediction: What we predict will happen.
        evidence: Supporting evidence for the prediction.
        start_date: When the prediction becomes relevant (ISO date).
        end_date: When the prediction expires (ISO date).
        duration_days: How long the prediction is valid.
        affected_task_types: Task types this prediction applies to.
        affected_rules: Rule IDs that this prediction relates to.
        realized: Whether the prediction has come true.
    """
    prediction: str = ""
    evidence: str = ""
    start_date: str = ""
    end_date: str = ""
    duration_days: int = 0
    affected_task_types: list[str] = field(default_factory=list)
    affected_rules: list[str] = field(default_factory=list)
    realized: bool | None = None  # None = not yet evaluated

    def __post_init__(self) -> None:
        self.memory_type = MemoryType.PREDICTED_IMPACT
        super().__post_init__()

    @property
    def is_active(self) -> bool:
        """Whether this prediction is currently in its active window."""
        if not self.start_date or not self.end_date:
            return True  # No bounds = always active
        from datetime import date
        today = date.today().isoformat()
        return self.start_date <= today <= self.end_date

    @property
    def is_expired(self) -> bool:
        """Whether this prediction's window has passed."""
        if not self.end_date:
            return False
        from datetime import date
        return date.today().isoformat() > self.end_date


# ---------------------------------------------------------------------------
# Type 4: BrainProfile (Profile)
# ---------------------------------------------------------------------------

@dataclass
class ProfileField:
    """A single field in a brain profile with evidence tracking.

    Adapted from EverOS's profile field structure:
    {"value": "...", "evidences": ["date|session"], "level": "..."}
    """
    value: str
    level: str = ""  # "beginner", "intermediate", "advanced", "expert"
    evidences: list[str] = field(default_factory=list)
    confidence: float = 0.0

    def add_evidence(self, evidence: str) -> None:
        """Add evidence and increase confidence."""
        if evidence not in self.evidences:
            self.evidences.append(evidence)
            self.confidence = min(1.0, self.confidence + 0.1)


@dataclass
class BrainProfile(BaseMemoryUnit):
    """Accumulated characteristics of a brain.

    Adapted from EverOS's Profile memory type. Tracks what the brain
    is good at, what it struggles with, its tendencies, and patterns.

    Attributes:
        strengths: Task types where the brain excels.
        weaknesses: Task types where corrections are frequent.
        tendencies: Behavioral patterns observed.
        correction_patterns: Recurring correction themes.
        preferred_patterns: Agentic patterns the brain defaults to.
    """
    strengths: list[ProfileField] = field(default_factory=list)
    weaknesses: list[ProfileField] = field(default_factory=list)
    tendencies: list[ProfileField] = field(default_factory=list)
    correction_patterns: list[ProfileField] = field(default_factory=list)
    preferred_patterns: list[ProfileField] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.memory_type = MemoryType.BRAIN_PROFILE
        super().__post_init__()

    def merge(self, other: BrainProfile) -> None:
        """Merge another profile into this one.

        EverOS strategy: keep highest level, merge evidences.
        """
        self._merge_fields(self.strengths, other.strengths)
        self._merge_fields(self.weaknesses, other.weaknesses)
        self._merge_fields(self.tendencies, other.tendencies)
        self._merge_fields(self.correction_patterns, other.correction_patterns)
        self._merge_fields(self.preferred_patterns, other.preferred_patterns)

    @staticmethod
    def _merge_fields(target: list[ProfileField], source: list[ProfileField]) -> None:
        """Merge source fields into target, keeping highest level."""
        target_map = {f.value: f for f in target}
        level_order = {"": 0, "beginner": 1, "intermediate": 2, "advanced": 3, "expert": 4}

        for sf in source:
            if sf.value in target_map:
                tf = target_map[sf.value]
                # Keep highest level
                if level_order.get(sf.level, 0) > level_order.get(tf.level, 0):
                    tf.level = sf.level
                # Merge evidences
                for ev in sf.evidences:
                    if ev not in tf.evidences:
                        tf.evidences.append(ev)
                tf.confidence = max(tf.confidence, sf.confidence)
            else:
                target.append(sf)
                target_map[sf.value] = sf


# ---------------------------------------------------------------------------
# Type 5: CrossBrainProfile (GroupProfile)
# ---------------------------------------------------------------------------

@dataclass
class SharedPattern:
    """A pattern observed across multiple brains.

    Attributes:
        pattern: Description of the shared pattern.
        brain_ids: Brains where this pattern was observed.
        confidence: How confident we are this is a real pattern.
        status: Discovery status (exploring/confirmed/promoted).
    """
    pattern: str
    brain_ids: list[str] = field(default_factory=list)
    confidence: float = 0.0
    status: str = "exploring"  # exploring, confirmed, promoted

    @property
    def brain_count(self) -> int:
        return len(self.brain_ids)


@dataclass
class CrossBrainProfile(BaseMemoryUnit):
    """Patterns shared across multiple brains.

    Adapted from EverOS's GroupProfile. Instead of tracking group
    conversation dynamics, tracks patterns that emerge across brains.

    Attributes:
        shared_patterns: Patterns observed in 2+ brains.
        shared_rules: Rules that graduated in multiple brains.
        divergences: Where brains disagree or have conflicting rules.
    """
    shared_patterns: list[SharedPattern] = field(default_factory=list)
    shared_rules: list[str] = field(default_factory=list)
    divergences: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.memory_type = MemoryType.CROSS_BRAIN_PROFILE
        super().__post_init__()

    def add_pattern(self, pattern: str, brain_id: str) -> SharedPattern:
        """Add or update a shared pattern."""
        for sp in self.shared_patterns:
            if sp.pattern == pattern:
                if brain_id not in sp.brain_ids:
                    sp.brain_ids.append(brain_id)
                    sp.confidence = min(1.0, sp.confidence + 0.15)
                return sp

        new_pattern = SharedPattern(
            pattern=pattern,
            brain_ids=[brain_id],
            confidence=0.3,
        )
        self.shared_patterns.append(new_pattern)
        return new_pattern


# ---------------------------------------------------------------------------
# Classification helper
# ---------------------------------------------------------------------------

def classify_memory_type(content: str) -> MemoryType:
    """Heuristic classifier for memory type based on content.

    Args:
        content: Text content to classify.

    Returns:
        The most likely MemoryType.
    """
    content_lower = content.lower()

    prediction_signals = ("will ", "predict", "future", "expect", "likely",
                         "forecast", "anticipate", "upcoming")
    profile_signals = ("tends to", "usually", "pattern of", "strength",
                      "weakness", "prefers", "characteristic")
    fact_signals = ("fact:", "note:", "learned:", "observed:")
    cross_signals = ("across brains", "shared pattern", "multiple brains",
                    "cross-brain", "common to")

    if any(s in content_lower for s in cross_signals):
        return MemoryType.CROSS_BRAIN_PROFILE
    if any(s in content_lower for s in prediction_signals):
        return MemoryType.PREDICTED_IMPACT
    if any(s in content_lower for s in profile_signals):
        return MemoryType.BRAIN_PROFILE
    if any(s in content_lower for s in fact_signals):
        return MemoryType.ATOMIC_FACT

    return MemoryType.CORRECTION_NARRATIVE
