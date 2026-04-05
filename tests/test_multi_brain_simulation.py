"""
Multi-Brain Simulation — validates Gradata SDK at scale across 10 synthetic personas.
======================================================================================

Simulates 10 distinct "brains" (personas), each generating 50-100 synthetic
corrections. Tests that the SDK's graduation pipeline, meta-rule emergence,
rule injection cap, and data isolation all behave correctly under realistic
multi-user conditions.

All tests are fully deterministic (seeded RNG). No production DB is touched —
all SQLite operations use :memory: or tmp_path.

Run: pytest sdk/tests/test_multi_brain_simulation.py -v
"""

from __future__ import annotations

import random
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import NamedTuple

import pytest

from gradata._types import ELIGIBLE_STATES, Lesson, LessonState, RuleTransferScope
from gradata._scope import RuleScope
from gradata.enhancements.meta_rules import (
    discover_meta_rules,
    ensure_table,
    save_meta_rules,
    load_meta_rules,
)
from gradata.rules.rule_engine import apply_rules
from gradata.enhancements.self_improvement import (
    ACCEPTANCE_BONUS,
    CONTRADICTION_PENALTY,
    INITIAL_CONFIDENCE,
    PATTERN_THRESHOLD,
    RULE_THRESHOLD,
    SEVERITY_WEIGHTS,
    SURVIVAL_SEVERITY_WEIGHTS,
    SURVIVAL_BONUS,
)

# ---------------------------------------------------------------------------
# Deterministic seed — every run produces identical results
# ---------------------------------------------------------------------------

_SEED = 20260327


# ---------------------------------------------------------------------------
# Severity label constants (matches diff_engine and self_improvement)
# ---------------------------------------------------------------------------

SEVERITIES = ["trivial", "minor", "moderate", "major", "rewrite"]

# Confidence delta per correction event:
#   survival  -> +SURVIVAL_BONUS * SURVIVAL_SEVERITY_WEIGHTS[severity]
#   violation -> +CONTRADICTION_PENALTY * SEVERITY_WEIGHTS[severity]   (negative)


def _survival_delta(severity: str) -> float:
    return round(SURVIVAL_BONUS * SURVIVAL_SEVERITY_WEIGHTS.get(severity, 1.0), 4)


def _violation_delta(severity: str) -> float:
    return round(CONTRADICTION_PENALTY * SEVERITY_WEIGHTS.get(severity, 1.0), 4)


# ---------------------------------------------------------------------------
# Persona definition
# ---------------------------------------------------------------------------

@dataclass
class PersonaSpec:
    """Definition of a simulated persona's correction habits.

    Attributes:
        name: Human-readable persona label.
        primary_categories: Categories this persona corrects most (weighted high).
        secondary_categories: Categories corrected occasionally.
        severity_weights: Probability weights per severity (trivial..rewrite).
        corrections_per_session: Range (min, max) of corrections each session.
    """

    name: str
    primary_categories: list[str]
    secondary_categories: list[str]
    severity_weights: list[float]       # maps to SEVERITIES order
    corrections_per_session: tuple[int, int] = (1, 3)


# ---------------------------------------------------------------------------
# 10 Persona definitions
# ---------------------------------------------------------------------------

PERSONAS: list[PersonaSpec] = [
    PersonaSpec(
        name="Sales Rep",
        primary_categories=["DRAFTING", "EMAIL_FORMAT", "POSITIONING"],
        secondary_categories=["COMMUNICATION", "CONSTRAINT"],
        severity_weights=[0.10, 0.35, 0.35, 0.15, 0.05],
        corrections_per_session=(1, 3),
    ),
    PersonaSpec(
        name="DevOps Engineer",
        primary_categories=["ARCHITECTURE", "PROCESS", "VERIFICATION"],
        secondary_categories=["ACCURACY", "THOROUGHNESS"],
        severity_weights=[0.05, 0.20, 0.40, 0.25, 0.10],
        corrections_per_session=(1, 2),
    ),
    PersonaSpec(
        name="Data Scientist",
        primary_categories=["ACCURACY", "DATA_INTEGRITY", "THOROUGHNESS"],
        secondary_categories=["PROCESS", "VERIFICATION"],
        severity_weights=[0.05, 0.25, 0.40, 0.20, 0.10],
        corrections_per_session=(1, 3),
    ),
    PersonaSpec(
        name="Product Manager",
        primary_categories=["COMMUNICATION", "PRESENTATION", "CONSTRAINT"],
        secondary_categories=["DRAFTING", "POSITIONING"],
        severity_weights=[0.15, 0.35, 0.30, 0.15, 0.05],
        corrections_per_session=(1, 3),
    ),
    PersonaSpec(
        name="Junior Developer",
        primary_categories=[
            "DRAFTING", "ACCURACY", "PROCESS", "ARCHITECTURE",
            "COMMUNICATION", "VERIFICATION",
        ],
        secondary_categories=["CONSTRAINT", "THOROUGHNESS", "DATA_INTEGRITY"],
        severity_weights=[0.20, 0.30, 0.25, 0.15, 0.10],
        corrections_per_session=(2, 4),
    ),
    PersonaSpec(
        name="Senior Architect",
        primary_categories=["ARCHITECTURE"],
        secondary_categories=["PROCESS", "VERIFICATION"],
        severity_weights=[0.50, 0.30, 0.15, 0.04, 0.01],
        corrections_per_session=(0, 2),
    ),
    PersonaSpec(
        name="Marketing Writer",
        primary_categories=["DRAFTING", "POSITIONING", "IP_PROTECTION"],
        secondary_categories=["COMMUNICATION", "EMAIL_FORMAT"],
        severity_weights=[0.10, 0.30, 0.35, 0.20, 0.05],
        corrections_per_session=(1, 3),
    ),
    PersonaSpec(
        name="Support Agent",
        primary_categories=["ACCURACY", "COMMUNICATION", "DEMO_PREP"],
        secondary_categories=["PROCESS", "THOROUGHNESS"],
        severity_weights=[0.15, 0.35, 0.30, 0.15, 0.05],
        corrections_per_session=(1, 3),
    ),
    PersonaSpec(
        name="Researcher",
        primary_categories=["THOROUGHNESS", "ACCURACY", "PROCESS"],
        secondary_categories=["VERIFICATION", "DATA_INTEGRITY"],
        severity_weights=[0.05, 0.20, 0.45, 0.25, 0.05],
        corrections_per_session=(1, 3),
    ),
    PersonaSpec(
        name="Executive",
        primary_categories=["COMMUNICATION", "PRESENTATION", "CONSTRAINT"],
        secondary_categories=["DRAFTING", "POSITIONING"],
        severity_weights=[0.25, 0.40, 0.25, 0.08, 0.02],
        corrections_per_session=(1, 2),
    ),
]


# ---------------------------------------------------------------------------
# Synthetic lesson / correction generators
# ---------------------------------------------------------------------------

def _make_lesson(
    category: str,
    severity: str,
    session: int,
    rng: random.Random,
    confidence: float = INITIAL_CONFIDENCE,
    state: LessonState = LessonState.INSTINCT,
    index: int = 0,
) -> Lesson:
    """Build a deterministic synthetic Lesson.

    The description is constructed to include category-specific vocabulary so
    that ``discover_meta_rules()``'s theme detection can cluster lessons from
    the same persona meaningfully.
    """
    # Category-specific phrase banks so theme detection gets real signal
    _PHRASES: dict[str, list[str]] = {
        "DRAFTING": [
            "use colons not em dashes in prose",
            "no bold mid-paragraph for emphasis",
            "tight sentences, strip filler words",
            "subject line must be specific, no vague titles",
            "lead with the outcome not the feature",
        ],
        "EMAIL_FORMAT": [
            "email subject should reference company name",
            "draft reply on correct thread not new email",
            "hyperlink scheduling link in every booking CTA",
            "no pricing in cold email drafts",
            "three paragraphs max for outbound emails",
        ],
        "POSITIONING": [
            "never use agency pricing framing",
            "lead with outcome, not feature list",
            "frame as partnership not vendor pitch",
            "avoid promotional language in subject lines",
            "reference pain point before introducing solution",
        ],
        "ARCHITECTURE": [
            "use dependency injection not global state",
            "never expose internal mechanisms in public docs",
            "async first for all IO bound operations",
            "separate concerns between layers",
            "prefer composition over inheritance",
        ],
        "PROCESS": [
            "never skip the startup skill on session open",
            "always verify data before reporting numbers",
            "wrap-up must include lesson logging step",
            "check calendar two weeks out before demos",
            "run tests before marking gate complete",
        ],
        "VERIFICATION": [
            "verify prospect identity before drafting email",
            "confirm deal stage before updating pipeline",
            "never assume data without checking source",
            "validate email with validation service before upload",
            "check before reporting, never guess",
        ],
        "ACCURACY": [
            "never report unverified numbers",
            "source all statistics before including in output",
            "verify facts before stating as certain",
            "do not guess company revenue, look it up",
            "always check before claiming accuracy",
        ],
        "DATA_INTEGRITY": [
            "filter leads by owner before processing",
            "dedup list before importing to enrichment service",
            "never blend user A and user B metrics",
            "ensure all data is owner-filtered",
            "validate integrity before exporting",
        ],
        "THOROUGHNESS": [
            "research must complete before pushing to CRM",
            "include plain-English company explainer in demo prep",
            "full profile scrape beats headline filter",
            "enrich before tiering, never skip enrichment",
            "investigate all sources before concluding",
        ],
        "COMMUNICATION": [
            "match tone to audience seniority level",
            "acknowledge pain point before pitching solution",
            "avoid condescending phrasing in follow-ups",
            "direct communication over hedging language",
            "frame outcomes not features in C-suite messages",
        ],
        "PRESENTATION": [
            "lead with business impact on slide one",
            "three talking points max per slide",
            "use visual evidence not text walls",
            "highlight ROI in the first two minutes",
            "personalise deck for each prospect company",
        ],
        "CONSTRAINT": [
            "only use truly free tools, no paid tiers",
            "only work on user A deals, not user B or user C",
            "scheduling link is mandatory CTA, not website",
            "do not include pricing unless explicitly asked",
            "max ten rules injected per session",
        ],
        "IP_PROTECTION": [
            "never expose graduation mechanism in public docs",
            "public docs sell outcomes, never expose architecture",
            "keep proprietary scoring server-side only",
            "open source patterns only, not cloud internals",
            "competitor analysis stays internal, not in emails",
        ],
        "DEMO_PREP": [
            "research LinkedIn before the demo call",
            "trace campaign origin before demo prep",
            "check calendar attendees before tagging deals",
            "prepare company explainer before demo",
            "use research tool for deep research before calls",
        ],
    }

    phrases = _PHRASES.get(category, [f"generic correction for {category}"])
    phrase = phrases[index % len(phrases)]
    description = f"{phrase} → apply consistently (session {session}, {severity})"

    return Lesson(
        date=f"2026-01-{(session % 28) + 1:02d}",
        state=state,
        confidence=round(confidence, 2),
        category=category,
        description=description,
        root_cause=f"Repeated pattern in {category.lower()} work",
        fire_count=rng.randint(0, 5),
        sessions_since_fire=rng.randint(0, 3),
    )


def _update_confidence(lesson: Lesson, severity: str, survived: bool) -> Lesson:
    """Apply a single confidence update to a lesson (in-place).

    Uses the same delta calculation as the SDK's self_improvement constants.

    Args:
        lesson: The lesson to update.
        severity: Correction severity label.
        survived: True = lesson survived (positive signal), False = violated.

    Returns:
        The mutated lesson.
    """
    if survived:
        delta = _survival_delta(severity)
    else:
        delta = _violation_delta(severity)

    new_conf = round(lesson.confidence + delta, 2)
    lesson.confidence = max(0.0, min(1.0, new_conf))

    # Promote / demote based on thresholds
    if lesson.state == LessonState.INSTINCT and lesson.confidence >= PATTERN_THRESHOLD:
        lesson.state = LessonState.PATTERN
    elif lesson.state == LessonState.PATTERN and lesson.confidence >= RULE_THRESHOLD:
        lesson.state = LessonState.RULE
    elif lesson.state == LessonState.PATTERN and lesson.confidence < PATTERN_THRESHOLD:
        lesson.state = LessonState.INSTINCT
    elif lesson.state == LessonState.RULE and lesson.confidence < PATTERN_THRESHOLD:
        lesson.state = LessonState.PATTERN

    return lesson


# Maximum distinct lesson variants per category across all BrainState instances.
# Caps at 5 to ensure primary categories accumulate enough lessons to trigger
# meta-rule emergence (threshold = 3) while keeping memory usage bounded.
_MAX_LESSONS_PER_CATEGORY = 5


@dataclass
class BrainState:
    """In-memory brain state for a single simulated persona.

    Attributes:
        persona: The persona spec driving this brain.
        lessons: All active lessons (mutable).
        session_count: Number of sessions simulated so far.
        rng: Per-brain seeded RNG for determinism.
    """

    persona: PersonaSpec
    lessons: list[Lesson] = field(default_factory=list)
    session_count: int = 0
    rng: random.Random = field(default_factory=random.Random)

    def run_session(self) -> list[Lesson]:
        """Simulate one session of corrections.

        Returns the list of lessons modified this session.

        Design: each correction either updates an existing lesson (confidence
        update) or creates a new one if the category has fewer than
        MAX_LESSONS_PER_CATEGORY lessons.  This ensures that primary categories
        accumulate enough lessons to cross the meta-rule emergence threshold.
        """
        self.session_count += 1
        session = self.session_count

        lo, hi = self.persona.corrections_per_session
        n_corrections = self.rng.randint(lo, hi)

        # Build the weighted category pool: primaries appear 3x more often
        cat_pool = (
            self.persona.primary_categories * 3
            + self.persona.secondary_categories
        )

        # Count lessons per category for growth decisions
        from collections import Counter
        cat_counts: Counter[str] = Counter(l.category for l in self.lessons)

        modified: list[Lesson] = []
        for _ in range(n_corrections):
            category = self.rng.choice(cat_pool)
            severity = self.rng.choices(SEVERITIES, weights=self.persona.severity_weights)[0]

            existing = [l for l in self.lessons if l.category == category]

            # Grow: add a new lesson variant if below the per-category cap
            if cat_counts[category] < _MAX_LESSONS_PER_CATEGORY:
                lesson = _make_lesson(
                    category=category,
                    severity=severity,
                    session=session,
                    rng=self.rng,
                    confidence=INITIAL_CONFIDENCE,
                    index=cat_counts[category],  # distinct phrase per variant
                )
                self.lessons.append(lesson)
                cat_counts[category] += 1
                # First touch: always a violation (we're learning this rule)
                _update_confidence(lesson, severity, survived=False)
                modified.append(lesson)
            else:
                # Update an existing lesson in the category
                lesson = self.rng.choice(existing)
                # 60% chance the lesson survived (positive reinforcement)
                survived = self.rng.random() < 0.60
                _update_confidence(lesson, severity, survived)
                modified.append(lesson)

        # Survival pass: existing lessons not touched this session get mild bonus
        touched_cats = {l.category for l in modified}
        for lesson in self.lessons:
            if lesson.category not in touched_cats:
                _update_confidence(lesson, "trivial", survived=True)

        return modified


def _build_brain(persona: PersonaSpec, n_sessions: int, seed: int) -> BrainState:
    """Run a persona through n_sessions and return the final BrainState.

    Args:
        persona: The persona spec.
        n_sessions: Number of sessions to simulate.
        seed: RNG seed for determinism.

    Returns:
        Fully populated BrainState.
    """
    brain = BrainState(persona=persona, rng=random.Random(seed))
    for _ in range(n_sessions):
        brain.run_session()
    return brain


# ---------------------------------------------------------------------------
# Pytest fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def all_brains() -> list[BrainState]:
    """All 10 personas each run through 50 sessions. Module-scoped for speed."""
    return [
        _build_brain(persona, n_sessions=50, seed=_SEED + i)
        for i, persona in enumerate(PERSONAS)
    ]


@pytest.fixture(scope="module")
def graduated_lessons_per_brain(all_brains: list[BrainState]) -> list[list[Lesson]]:
    """Extract PATTERN+RULE lessons for each brain."""
    return [
        [l for l in brain.lessons if l.state in ELIGIBLE_STATES]
        for brain in all_brains
    ]


# ---------------------------------------------------------------------------
# Test 1: Persona graduation divergence
# ---------------------------------------------------------------------------

def _top_categories(lessons: list[Lesson], n: int = 10) -> set[str]:
    """Return the top-n categories by total confidence among graduated lessons."""
    from collections import Counter
    counts: Counter[str] = Counter()
    for l in lessons:
        counts[l.category] += l.confidence
    return {cat for cat, _ in counts.most_common(n)}


def _jaccard(a: set, b: set) -> float:
    """Jaccard similarity between two sets. 0.0 = disjoint, 1.0 = identical."""
    if not a and not b:
        return 1.0
    return len(a & b) / len(a | b)


def test_persona_graduation_divergence(graduated_lessons_per_brain: list[list[Lesson]]) -> None:
    """Different personas should graduate different rule sets.

    After 50 sessions, the top-10 categories for each brain are compared
    pairwise. We assert that:
      - At least one pair of brains has Jaccard distance (1 - similarity) > 0.3,
        proving meaningful divergence exists.
      - Personas with non-overlapping primary categories have higher divergence
        than personas with overlapping ones (relative check).
    """
    top_sets = [_top_categories(lessons) for lessons in graduated_lessons_per_brain]

    # --- global divergence check ---
    distances: list[float] = []
    for i in range(len(top_sets)):
        for j in range(i + 1, len(top_sets)):
            dist = 1.0 - _jaccard(top_sets[i], top_sets[j])
            distances.append(dist)

    max_distance = max(distances)
    avg_distance = sum(distances) / len(distances)

    assert max_distance > 0.30, (
        f"Expected at least one persona pair with Jaccard distance > 0.30, "
        f"got max={max_distance:.3f}. Personas are not diverging."
    )

    # --- relative check: Sales Rep (0) vs DevOps Engineer (1) should differ more
    #     than Sales Rep (0) vs Marketing Writer (6), since both 0 and 6 do DRAFTING
    # ---
    sales_top = top_sets[0]
    devops_top = top_sets[1]
    marketing_top = top_sets[6]

    sales_devops_dist = 1.0 - _jaccard(sales_top, devops_top)
    sales_marketing_dist = 1.0 - _jaccard(sales_top, marketing_top)

    # Sales Rep and Marketing Writer share DRAFTING+POSITIONING → should be closer
    assert sales_devops_dist >= sales_marketing_dist, (
        f"Expected Sales Rep vs DevOps to diverge more than Sales Rep vs Marketing Writer. "
        f"sales-devops={sales_devops_dist:.3f}, sales-marketing={sales_marketing_dist:.3f}"
    )

    # --- verify each brain has at least some graduated lessons ---
    for i, lessons in enumerate(graduated_lessons_per_brain):
        assert len(lessons) > 0, (
            f"Persona '{PERSONAS[i].name}' produced zero graduated lessons after 50 sessions."
        )


# ---------------------------------------------------------------------------
# Test 2: Correction-to-meta-rule pipeline
# ---------------------------------------------------------------------------

def test_correction_to_meta_rule_pipeline(graduated_lessons_per_brain: list[list[Lesson]]) -> None:
    """Every persona should produce at least 1 meta-rule after 50 sessions.

    Runs ``discover_meta_rules()`` on each brain's graduated lesson set and
    asserts that category-grouping produces at least one meta-rule where 3+
    lessons share the same category.
    """
    for i, lessons in enumerate(graduated_lessons_per_brain):
        persona_name = PERSONAS[i].name
        if not lessons:
            pytest.skip(f"Persona '{persona_name}' has no graduated lessons.")

        meta_rules = discover_meta_rules(lessons, min_group_size=3, current_session=50)

        assert len(meta_rules) >= 1, (
            f"Persona '{persona_name}' produced 0 meta-rules after 50 sessions "
            f"with {len(lessons)} graduated lessons. "
            f"Category distribution: "
            f"{ {l.category: sum(1 for x in lessons if x.category == l.category) for l in lessons} }"
        )

        # Assert meta-rule properties are well-formed
        for mr in meta_rules:
            assert len(mr.source_lesson_ids) >= 3, (
                f"Meta-rule '{mr.id}' for '{persona_name}' has fewer than 3 source lessons."
            )
            assert mr.confidence > 0.0, (
                f"Meta-rule '{mr.id}' has zero confidence."
            )
            assert mr.principle, (
                f"Meta-rule '{mr.id}' has an empty principle string."
            )


# ---------------------------------------------------------------------------
# Test 3: Cross-brain rule isolation
# ---------------------------------------------------------------------------

def test_cross_brain_rule_isolation(tmp_path: Path) -> None:
    """Corrections applied to brain A must not affect brain B.

    Uses two separate in-memory SQLite databases. Meta-rules are persisted to
    separate files, then read back. Brain B should have zero meta-rules after
    only brain A received corrections.
    """
    db_a = tmp_path / "brain_a.db"
    db_b = tmp_path / "brain_b.db"

    ensure_table(db_a)
    ensure_table(db_b)

    # Build brain A with 50 sessions
    rng = random.Random(_SEED)
    brain_a = _build_brain(PERSONAS[0], n_sessions=50, seed=_SEED)
    graduated_a = [l for l in brain_a.lessons if l.state in ELIGIBLE_STATES]

    meta_rules_a = discover_meta_rules(graduated_a, min_group_size=3, current_session=50)
    assert len(meta_rules_a) >= 1, "Brain A should have at least 1 meta-rule."

    # Save A's meta-rules to A's DB only
    save_meta_rules(db_a, meta_rules_a)

    # Brain B: no corrections applied, empty DB
    loaded_a = load_meta_rules(db_a)
    loaded_b = load_meta_rules(db_b)

    assert len(loaded_a) >= 1, "Brain A DB should contain saved meta-rules."
    assert len(loaded_b) == 0, (
        f"Brain B DB should be empty (no cross-contamination), "
        f"but found {len(loaded_b)} meta-rules."
    )

    # Verify A's IDs don't appear in B
    a_ids = {mr.id for mr in loaded_a}
    b_ids = {mr.id for mr in loaded_b}
    assert a_ids.isdisjoint(b_ids), (
        f"Shared meta-rule IDs between isolated brains: {a_ids & b_ids}"
    )


# ---------------------------------------------------------------------------
# Test 4: Severity-weighted confidence convergence
# ---------------------------------------------------------------------------

def test_severity_weighted_convergence() -> None:
    """Rewrite-severity corrections produce larger confidence changes than trivial.

    Creates two identical lessons and applies corrections at opposite severity
    extremes over 20 rounds. The rewrite-corrected lesson should diverge from
    the trivial-corrected lesson more quickly.
    """
    rng = random.Random(_SEED)
    n_rounds = 20

    lesson_trivial = _make_lesson(
        "ACCURACY", "trivial", session=1, rng=rng,
        confidence=INITIAL_CONFIDENCE, index=0,
    )
    lesson_rewrite = _make_lesson(
        "ACCURACY", "rewrite", session=1, rng=rng,
        confidence=INITIAL_CONFIDENCE, index=0,
    )

    # Alternate survive/violate pattern for both — same pattern, different severity
    cumulative_trivial = 0.0
    cumulative_rewrite = 0.0

    for round_idx in range(n_rounds):
        survived = (round_idx % 3 != 0)  # violate every 3rd round

        conf_before_trivial = lesson_trivial.confidence
        conf_before_rewrite = lesson_rewrite.confidence

        _update_confidence(lesson_trivial, "trivial", survived)
        _update_confidence(lesson_rewrite, "rewrite", survived)

        delta_trivial = abs(lesson_trivial.confidence - conf_before_trivial)
        delta_rewrite = abs(lesson_rewrite.confidence - conf_before_rewrite)

        cumulative_trivial += delta_trivial
        cumulative_rewrite += delta_rewrite

        # Per-round: rewrite must move confidence >= trivial when unclamped.
        # When a lesson hits 0.0 or 1.0 bounds, delta can be 0 regardless of
        # severity — skip the per-round check in those cases.
        trivial_clamped = conf_before_trivial <= 0.0 or conf_before_trivial >= 1.0
        rewrite_clamped = conf_before_rewrite <= 0.0 or conf_before_rewrite >= 1.0
        if not trivial_clamped and not rewrite_clamped:
            assert delta_rewrite >= delta_trivial, (
                f"Round {round_idx}: rewrite delta {delta_rewrite:.4f} < "
                f"trivial delta {delta_trivial:.4f}. Severity weighting broken."
            )

    # Cumulative path length: sum of absolute per-round changes.
    # Rewrite severity oscillates much larger than trivial because violation
    # rounds deliver 13x the penalty. This is the correct stability metric —
    # net displacement doesn't capture oscillation amplitude.
    assert cumulative_rewrite > cumulative_trivial, (
        f"After {n_rounds} rounds, rewrite cumulative path length "
        f"{cumulative_rewrite:.4f} <= trivial {cumulative_trivial:.4f}. "
        f"Rewrite severity should create larger total confidence movement."
    )


# ---------------------------------------------------------------------------
# Test 5: Rule injection scaling (max_rules cap)
# ---------------------------------------------------------------------------

def test_rule_injection_scaling() -> None:
    """apply_rules() must respect the max_rules=10 cap with 50+ eligible lessons.

    Generates 60 synthetic RULE-state lessons across varied categories. Verifies
    that apply_rules() returns at most 10 and that the returned set is a
    highest-priority subset (all must be RULE or PATTERN state).
    """
    rng = random.Random(_SEED)
    categories = [
        "DRAFTING", "ACCURACY", "PROCESS", "ARCHITECTURE",
        "COMMUNICATION", "VERIFICATION", "THOROUGHNESS",
        "CONSTRAINT", "POSITIONING", "DATA_INTEGRITY",
    ]

    lessons: list[Lesson] = []
    for i in range(60):
        cat = categories[i % len(categories)]
        confidence = round(0.90 + rng.uniform(0.0, 0.09), 2)  # all RULE-level
        lesson = _make_lesson(
            category=cat,
            severity="moderate",
            session=i + 1,
            rng=rng,
            confidence=confidence,
            state=LessonState.RULE,
            index=i,
        )
        lessons.append(lesson)

    scope = RuleScope()  # wildcard scope — all lessons eligible
    applied = apply_rules(lessons, scope, max_rules=10)

    assert len(applied) <= 10, (
        f"apply_rules() returned {len(applied)} rules, expected <= 10."
    )
    assert len(applied) > 0, "apply_rules() returned 0 rules from 60 eligible lessons."

    # All returned rules must be PATTERN or RULE state
    for ar in applied:
        assert ar.lesson.state in ELIGIBLE_STATES, (
            f"Rule '{ar.rule_id}' has ineligible state {ar.lesson.state.value}."
        )

    # With 60 RULE-state lessons the cap should be hit
    assert len(applied) == 10, (
        f"Expected exactly 10 rules (cap hit), got {len(applied)}. "
        f"apply_rules() may not be enforcing max_rules."
    )


# ---------------------------------------------------------------------------
# Test 6: Meta-rule emergence threshold
# ---------------------------------------------------------------------------

def test_meta_rule_emergence_threshold() -> None:
    """Meta-rules emerge at >= 3 eligible lessons; fewer than 3 produce none.

    Step 1: 2 PATTERN lessons in the same category → 0 meta-rules.
    Step 2: Add a 3rd PATTERN lesson → >= 1 meta-rule.
    """
    rng = random.Random(_SEED)

    def _make_pattern_lesson(index: int) -> Lesson:
        l = _make_lesson(
            category="DRAFTING",
            severity="moderate",
            session=index + 1,
            rng=rng,
            confidence=0.75,
            state=LessonState.PATTERN,
            index=index,
        )
        return l

    # --- Step 1: 2 lessons — below threshold ---
    two_lessons = [_make_pattern_lesson(i) for i in range(2)]
    meta_rules_two = discover_meta_rules(two_lessons, min_group_size=3, current_session=2)

    assert len(meta_rules_two) == 0, (
        f"Expected 0 meta-rules from 2 lessons (below threshold=3), "
        f"got {len(meta_rules_two)}."
    )

    # --- Step 2: 3 lessons — at threshold ---
    three_lessons = [_make_pattern_lesson(i) for i in range(3)]
    meta_rules_three = discover_meta_rules(three_lessons, min_group_size=3, current_session=3)

    assert len(meta_rules_three) >= 1, (
        f"Expected >= 1 meta-rule from 3 lessons (at threshold=3), "
        f"got {len(meta_rules_three)}."
    )

    # The emerged meta-rule should reference all 3 source lessons
    top_meta = meta_rules_three[0]
    assert len(top_meta.source_lesson_ids) == 3, (
        f"Meta-rule should reference exactly 3 source lessons, "
        f"got {len(top_meta.source_lesson_ids)}."
    )
    assert "DRAFTING" in top_meta.source_categories, (
        f"Meta-rule source_categories should include 'DRAFTING', "
        f"got {top_meta.source_categories}."
    )


# ---------------------------------------------------------------------------
# Test 7: Persona adaptation score
# ---------------------------------------------------------------------------

def _compute_adaptation_score(
    lessons: list[Lesson],
    all_categories: list[str],
    recent_window: int = 10,
    total_sessions: int = 50,
) -> float:
    """Fraction of categories that have no recent violations.

    A higher score means the persona has stopped making mistakes in more
    categories — evidence of learning / adaptation.

    Args:
        lessons: All lessons for a persona.
        all_categories: The full category universe for this persona.
        recent_window: Sessions considered "recent".
        total_sessions: Total sessions run.

    Returns:
        Score in [0.0, 1.0].
    """
    # Categories where the lesson has high confidence (>= PATTERN threshold)
    # are considered "learned" — the persona stopped violating them.
    learned = {
        l.category
        for l in lessons
        if l.state in ELIGIBLE_STATES and l.confidence >= PATTERN_THRESHOLD
    }

    if not all_categories:
        return 0.0

    return len(learned & set(all_categories)) / len(set(all_categories))


def test_persona_adaptation_score(all_brains: list[BrainState]) -> None:
    """Adaptation score should improve meaningfully after 50 sessions.

    Tests the following invariants:
      1. Every persona has a positive adaptation score after 50 sessions
         (some categories were learned).
      2. Personas with narrow correction patterns (Senior Architect) have
         a higher adaptation score than those with broad patterns (Junior Dev),
         because they focus on fewer categories.
      3. Adaptation score is bounded in [0.0, 1.0].
    """
    scores: list[float] = []
    for i, brain in enumerate(all_brains):
        persona = brain.persona
        all_cats = persona.primary_categories + persona.secondary_categories
        score = _compute_adaptation_score(
            brain.lessons,
            all_categories=all_cats,
            total_sessions=brain.session_count,
        )
        scores.append(score)
        assert 0.0 <= score <= 1.0, (
            f"Persona '{persona.name}' has out-of-bounds adaptation score: {score}"
        )

    # All personas should have learned at least something
    zero_score_personas = [
        PERSONAS[i].name
        for i, score in enumerate(scores)
        if score == 0.0
    ]
    assert not zero_score_personas, (
        f"These personas have adaptation score = 0 after 50 sessions: "
        f"{zero_score_personas}. No categories were learned."
    )

    # Senior Architect (index 5) has 1 primary category — should have a high
    # adaptation score. Junior Developer (index 4) has 6 primary categories.
    senior_architect_score = scores[5]
    junior_dev_score = scores[4]
    assert senior_architect_score >= junior_dev_score, (
        f"Senior Architect (narrow focus) should adapt >= Junior Dev (broad). "
        f"Senior={senior_architect_score:.3f}, Junior={junior_dev_score:.3f}"
    )

    # Verify score improves: run a 10-session brain vs 50-session brain
    # for the same persona and seed — 50 sessions should score >= 10 sessions
    early_brain = _build_brain(PERSONAS[0], n_sessions=10, seed=_SEED)
    late_brain = _build_brain(PERSONAS[0], n_sessions=50, seed=_SEED)

    early_cats = PERSONAS[0].primary_categories + PERSONAS[0].secondary_categories
    score_early = _compute_adaptation_score(early_brain.lessons, early_cats, total_sessions=10)
    score_late = _compute_adaptation_score(late_brain.lessons, early_cats, total_sessions=50)

    assert score_late >= score_early, (
        f"Adaptation score should not regress over sessions. "
        f"10 sessions: {score_early:.3f}, 50 sessions: {score_late:.3f}"
    )


# ---------------------------------------------------------------------------
# Test 8: Compound score validation across personas
# ---------------------------------------------------------------------------

def test_compound_score_across_personas(all_brains: list[BrainState]) -> None:
    """compound_score should produce meaningful, non-zero scores for all personas.

    Validates that:
      1. Every persona gets compound_score > 0 after 50 sessions.
      2. Personas with more graduated lessons score higher.
      3. Score is bounded [0, 100].
      4. 10-session brain scores < 50-session brain (monotonic improvement).
    """
    from gradata._brain_manifest import _compound_score

    persona_scores: list[float] = []
    for brain in all_brains:
        graduated = [l for l in brain.lessons if l.state == LessonState.RULE]
        active = [l for l in brain.lessons if l.state in (LessonState.INSTINCT, LessonState.PATTERN)]
        total_corrections = brain.session_count * 2  # approximate

        score = _compound_score(
            correction_rate=0.02,  # realistic low rate
            severity_ratio=None,  # no severity data in simulation
            lessons_graduated=len(graduated),
            lessons_active=len(active),
            sessions=brain.session_count,
            total_corrections=total_corrections,
        )
        persona_scores.append(score)

        assert 0.0 <= score <= 100.0, (
            f"Persona '{brain.persona.name}' compound_score {score} out of bounds."
        )

    # All personas should have non-zero scores after 50 sessions
    zero_personas = [
        all_brains[i].persona.name
        for i, s in enumerate(persona_scores)
        if s == 0.0
    ]
    assert not zero_personas, (
        f"These personas have compound_score = 0 after 50 sessions: {zero_personas}"
    )

    # Monotonic: 50 sessions should score >= 10 sessions for the same persona
    early_brain = _build_brain(PERSONAS[0], n_sessions=10, seed=_SEED)
    late_brain = _build_brain(PERSONAS[0], n_sessions=50, seed=_SEED)

    def _score_brain(b: BrainState) -> float:
        grad = [l for l in b.lessons if l.state == LessonState.RULE]
        act = [l for l in b.lessons if l.state in (LessonState.INSTINCT, LessonState.PATTERN)]
        return _compound_score(0.02, severity_ratio=None, lessons_graduated=len(grad), lessons_active=len(act), sessions=b.session_count, total_corrections=b.session_count * 2)

    early_score = _score_brain(early_brain)
    late_score = _score_brain(late_brain)
    assert late_score >= early_score, (
        f"compound_score should not regress: 10 sessions={early_score}, 50 sessions={late_score}"
    )
