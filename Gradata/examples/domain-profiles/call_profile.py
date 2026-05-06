"""
Call Profile — Graduated Behavioral Patterns from Call Transcripts
==================================================================
Layer 1 Enhancement: imports from patterns/ (memory)

Extracts behavioral features from call/demo transcripts (Fireflies format),
correlates with outcomes, and graduates patterns through INSTINCT→PATTERN→RULE.

Unlike aggregate analytics tools (Gong, Chorus, Clari) that benchmark against
"top reps," this module tracks INDIVIDUAL behavioral evolution and compounds
it. After 30 calls, the pre-call cheat sheet writes itself from graduated
patterns specific to the user.

Features extracted:
  - talk_ratio: user's words / total words
  - question_count: total questions asked by user
  - open_question_ratio: open-ended vs closed questions
  - pain_question_count: questions probing pain/impact/cost
  - avg_turn_length: average words per user turn
  - longest_monologue: longest consecutive user speech (words)
  - story_count: case study/proof point deployments
  - objection_responses: count of objection-handling sequences
  - close_attempts: count of next-step/commitment asks
  - discovery_depth: minutes spent in discovery before pitching
  - commitment_specificity: ratio of specific vs vague commitments

Call types:
  - discovery: first call, focus on pain and qualification
  - demo: product walkthrough, focus on value and fit
  - follow_up: post-demo, focus on objections and close
  - break_up: final attempt, focus on urgency

Pure computation — no file I/O, no Fireflies API calls.
The brain-layer wiring (reading transcripts, persisting profiles) stays
in brain/scripts/.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Transcript Parsing
# ---------------------------------------------------------------------------


@dataclass
class Utterance:
    """A single speaker turn in a transcript.

    Attributes:
        speaker: Speaker name or identifier.
        text: What was said.
        start_time: Seconds from call start (0 if unavailable).
        end_time: Seconds from call end (0 if unavailable).
    """

    speaker: str
    text: str
    start_time: float = 0.0
    end_time: float = 0.0

    @property
    def word_count(self) -> int:
        return len(self.text.split())

    @property
    def duration(self) -> float:
        return max(0.0, self.end_time - self.start_time)


def parse_transcript(
    sentences: list[dict],
    user_speaker: str | None = None,
) -> tuple[list[Utterance], str]:
    """Parse Fireflies-format transcript into Utterances.

    Fireflies returns sentences as:
        [{"speaker_name": "Host", "text": "...", "start_time": 0.5, "end_time": 3.2}, ...]

    Also handles plain dicts with "speaker" key.

    Args:
        sentences: List of sentence dicts from Fireflies.
        user_speaker: The user's speaker name. If None, inferred as the
            speaker with the most turns in the first 20% of the call
            (usually the host/caller).

    Returns:
        Tuple of (list of Utterances, detected user_speaker name).
    """
    utterances: list[Utterance] = []

    for s in sentences:
        speaker = s.get("speaker_name") or s.get("speaker") or "Unknown"
        text = s.get("text") or s.get("sentence") or ""
        start = float(s.get("start_time", 0))
        end = float(s.get("end_time", 0))
        if text.strip():
            utterances.append(
                Utterance(speaker=speaker, text=text.strip(), start_time=start, end_time=end)
            )

    # Infer user speaker if not provided
    if not user_speaker and utterances:
        # Count turns per speaker in first 20% of utterances
        cutoff = max(1, len(utterances) // 5)
        counts: dict[str, int] = {}
        for u in utterances[:cutoff]:
            counts[u.speaker] = counts.get(u.speaker, 0) + 1
        user_speaker = max(counts, key=lambda k: counts[k]) if counts else utterances[0].speaker

    return utterances, user_speaker or "Unknown"


# ---------------------------------------------------------------------------
# Question Detection
# ---------------------------------------------------------------------------

# Open-ended question starters
_OPEN_Q = re.compile(
    r"^\s*(?:what|how|why|tell me|describe|explain|walk me through|"
    r"can you (?:share|tell|describe|walk)|what would|how does|how do|"
    r"what if|what's your|how would)\b",
    re.I,
)

# Pain/impact probing questions
_PAIN_Q = re.compile(
    r"(?:impact|affect|cost|pain|challenge|struggle|frustrate|"
    r"what happens (?:if|when)|how (?:does|would) that (?:affect|impact|hurt)|"
    r"what (?:does|would) that (?:mean|cost|look like)|"
    r"how much (?:time|money|effort)|what's at stake|"
    r"biggest (?:challenge|problem|issue|pain)|"
    r"what would it mean (?:for|if|to))",
    re.I,
)

# Closed questions (yes/no oriented)
_CLOSED_Q = re.compile(
    r"^\s*(?:do you|are you|is (?:it|that|there)|have you|"
    r"did you|can you|would you|will you|could you|"
    r"does (?:it|that|your))\b",
    re.I,
)

# Story/proof indicators
_STORY_MARKERS = re.compile(
    r"(?:we had a (?:client|customer)|one of our (?:clients|customers)|"
    r"for example|similar (?:to|situation)|case study|"
    r"(?:company|agency|team) (?:like yours|similar to)|"
    r"we worked with|they (?:saw|achieved|reduced|increased)|"
    r"the result was|within (?:\d+|a few) (?:weeks|months|days))",
    re.I,
)

# Objection markers (from prospect)
_OBJECTION_MARKERS = re.compile(
    r"(?:too expensive|can't afford|not in (?:the |our )?budget|"
    r"already (?:have|use|using)|happy with (?:what|our)|"
    r"not (?:the right|a good) time|need to (?:think|discuss|talk)|"
    r"not sure (?:if|about|we)|sounds (?:expensive|complicated)|"
    r"what if (?:it|we)|concerned about|worried about|"
    r"how (?:is|are) you different|why (?:should|would) (?:we|I))",
    re.I,
)

# Close/commitment language (from user)
_CLOSE_MARKERS = re.compile(
    r"(?:next step|move forward|set up|schedule|book|"
    r"send (?:over|you)|follow up|proposal|"
    r"trial|pilot|get started|kick off|"
    r"does (?:that|this) (?:work|sound)|"
    r"how about (?:we|I)|shall (?:we|I)|"
    r"I'll (?:send|share|prepare|get)|"
    r"let's (?:plan|schedule|set|do))",
    re.I,
)

# Specific commitment markers
_SPECIFIC_COMMIT = re.compile(
    r"(?:by (?:Monday|Tuesday|Wednesday|Thursday|Friday|tomorrow|end of (?:day|week))|"
    r"(?:at|on) (?:\d{1,2}(?::\d{2})?\s*(?:am|pm|PT|ET|CT))|"
    r"\d{1,2}/\d{1,2}|"
    r"(?:this|next) (?:Monday|Tuesday|Wednesday|Thursday|Friday|week))",
    re.I,
)


# ---------------------------------------------------------------------------
# Feature Extraction
# ---------------------------------------------------------------------------


@dataclass
class CallFeatures:
    """Extracted behavioral features from a single call transcript."""

    call_type: str = "unknown"  # discovery, demo, follow_up, break_up
    duration_minutes: float = 0.0
    total_words: int = 0
    user_words: int = 0
    prospect_words: int = 0
    talk_ratio: float = 0.0  # user_words / total_words
    turn_count: int = 0  # total speaker turns
    user_turns: int = 0
    avg_turn_length: float = 0.0  # avg words per user turn
    longest_monologue: int = 0  # longest consecutive user speech
    question_count: int = 0  # questions user asked
    open_question_count: int = 0
    closed_question_count: int = 0
    pain_question_count: int = 0
    open_question_ratio: float = 0.0  # open / total questions
    story_count: int = 0  # case study/proof deployments
    objection_count: int = 0  # objections from prospect
    objection_responses: int = 0  # user responses to objections
    close_attempts: int = 0  # next-step/commitment asks
    commitment_count: int = 0  # total commitments made
    specific_commitments: int = 0  # commitments with dates/times
    commitment_specificity: float = 0.0  # specific / total commitments
    discovery_minutes: float = 0.0  # time before first product mention
    first_pitch_minute: float = 0.0  # when user first pitched

    def to_dict(self) -> dict[str, Any]:
        return {k: round(v, 2) if isinstance(v, float) else v for k, v in self.__dict__.items()}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> CallFeatures:
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


def extract_call_features(
    utterances: list[Utterance],
    user_speaker: str,
    call_type: str = "unknown",
) -> CallFeatures:
    """Extract behavioral features from parsed transcript.

    Pure function — no I/O.

    Args:
        utterances: Parsed transcript (from parse_transcript).
        user_speaker: The user's speaker name.
        call_type: Type of call (discovery, demo, follow_up, break_up).

    Returns:
        CallFeatures with all fields populated.
    """
    if not utterances:
        return CallFeatures(call_type=call_type)

    # Basic counts
    user_utts = [u for u in utterances if u.speaker == user_speaker]
    prospect_utts = [u for u in utterances if u.speaker != user_speaker]

    total_words = sum(u.word_count for u in utterances)
    user_words = sum(u.word_count for u in user_utts)
    prospect_words = sum(u.word_count for u in prospect_utts)

    talk_ratio = user_words / total_words if total_words > 0 else 0.0

    # Turn analysis
    avg_turn = user_words / len(user_utts) if user_utts else 0.0
    longest_mono = max((u.word_count for u in user_utts), default=0)

    # Duration
    if utterances[-1].end_time > 0 and utterances[0].start_time >= 0:
        duration_min = (utterances[-1].end_time - utterances[0].start_time) / 60.0
    else:
        # Estimate from word count (~150 wpm)
        duration_min = total_words / 150.0

    # Questions (from user utterances)
    question_count = 0
    open_q = 0
    closed_q = 0
    pain_q = 0

    for u in user_utts:
        # Count sentences ending with ?
        questions_in_turn = u.text.count("?")
        if questions_in_turn > 0:
            question_count += questions_in_turn

            if _OPEN_Q.search(u.text):
                open_q += questions_in_turn
            elif _CLOSED_Q.search(u.text):
                closed_q += questions_in_turn
            else:
                open_q += questions_in_turn  # default to open if ambiguous

            if _PAIN_Q.search(u.text):
                pain_q += questions_in_turn

    open_ratio = open_q / question_count if question_count > 0 else 0.0

    # Stories/proof points (from user)
    story_count = sum(1 for u in user_utts if _STORY_MARKERS.search(u.text))

    # Objections (from prospect) and responses (from user)
    objection_count = 0
    objection_responses = 0
    prev_was_objection = False

    for u in utterances:
        if u.speaker != user_speaker:
            if _OBJECTION_MARKERS.search(u.text):
                objection_count += 1
                prev_was_objection = True
            else:
                prev_was_objection = False
        else:
            if prev_was_objection:
                objection_responses += 1
            prev_was_objection = False

    # Close attempts (from user)
    close_attempts = sum(1 for u in user_utts if _CLOSE_MARKERS.search(u.text))

    # Commitments
    commitment_count = close_attempts  # close attempts that include specifics
    specific_commits = sum(
        1 for u in user_utts if _CLOSE_MARKERS.search(u.text) and _SPECIFIC_COMMIT.search(u.text)
    )
    commit_specificity = specific_commits / commitment_count if commitment_count > 0 else 0.0

    # Discovery depth: time before first "product" mention
    # Heuristic: first user utterance with product/feature/demo language
    _PITCH_MARKERS = re.compile(
        r"(?:let me (?:show|walk|demo)|here's (?:how|what)|"
        r"our (?:platform|tool|product|solution|system)|"
        r"the way (?:it|we) work|feature|dashboard|integration)",
        re.I,
    )
    first_pitch_time = 0.0
    for u in user_utts:
        if _PITCH_MARKERS.search(u.text):
            first_pitch_time = u.start_time
            break

    discovery_min = first_pitch_time / 60.0 if first_pitch_time > 0 else duration_min * 0.3

    return CallFeatures(
        call_type=call_type,
        duration_minutes=duration_min,
        total_words=total_words,
        user_words=user_words,
        prospect_words=prospect_words,
        talk_ratio=talk_ratio,
        turn_count=len(utterances),
        user_turns=len(user_utts),
        avg_turn_length=avg_turn,
        longest_monologue=longest_mono,
        question_count=question_count,
        open_question_count=open_q,
        closed_question_count=closed_q,
        pain_question_count=pain_q,
        open_question_ratio=open_ratio,
        story_count=story_count,
        objection_count=objection_count,
        objection_responses=objection_responses,
        close_attempts=close_attempts,
        commitment_count=commitment_count,
        specific_commitments=specific_commits,
        commitment_specificity=commit_specificity,
        discovery_minutes=discovery_min,
        first_pitch_minute=first_pitch_time / 60.0,
    )


# ---------------------------------------------------------------------------
# Call Profile (aggregated from multiple calls)
# ---------------------------------------------------------------------------


@dataclass
class CallOutcome:
    """Outcome of a single call, paired with its features."""

    features: CallFeatures
    outcome: str  # "advanced" | "stalled" | "lost" | "closed_won"
    next_stage: str = ""  # e.g., "demo_scheduled", "proposal_sent"
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "features": self.features.to_dict(),
            "outcome": self.outcome,
            "next_stage": self.next_stage,
            "notes": self.notes,
        }


@dataclass
class CallProfile:
    """Aggregated behavioral profile from N calls, scoped by call_type."""

    call_type: str
    sample_count: int = 0
    outcomes: list[CallOutcome] = field(default_factory=list)
    avg_features: CallFeatures = field(default_factory=CallFeatures)
    win_features: CallFeatures | None = None  # avg features when outcome=advanced/closed_won
    loss_features: CallFeatures | None = None  # avg features when outcome=stalled/lost
    confidence: float = 0.0
    patterns: list[str] = field(default_factory=list)  # graduated pattern descriptions

    def to_dict(self) -> dict[str, Any]:
        return {
            "call_type": self.call_type,
            "sample_count": self.sample_count,
            "avg_features": self.avg_features.to_dict(),
            "win_features": self.win_features.to_dict() if self.win_features else None,
            "loss_features": self.loss_features.to_dict() if self.loss_features else None,
            "confidence": round(self.confidence, 2),
            "patterns": self.patterns,
        }


def _avg_features(outcomes: list[CallOutcome]) -> CallFeatures:
    """Average CallFeatures across multiple outcomes."""
    if not outcomes:
        return CallFeatures()

    n = len(outcomes)
    fs = [o.features for o in outcomes]

    return CallFeatures(
        talk_ratio=sum(f.talk_ratio for f in fs) / n,
        question_count=round(sum(f.question_count for f in fs) / n),
        open_question_ratio=sum(f.open_question_ratio for f in fs) / n,
        pain_question_count=round(sum(f.pain_question_count for f in fs) / n),
        avg_turn_length=sum(f.avg_turn_length for f in fs) / n,
        longest_monologue=round(sum(f.longest_monologue for f in fs) / n),
        story_count=round(sum(f.story_count for f in fs) / n),
        objection_count=round(sum(f.objection_count for f in fs) / n),
        objection_responses=round(sum(f.objection_responses for f in fs) / n),
        close_attempts=round(sum(f.close_attempts for f in fs) / n),
        commitment_specificity=sum(f.commitment_specificity for f in fs) / n,
        discovery_minutes=sum(f.discovery_minutes for f in fs) / n,
        duration_minutes=sum(f.duration_minutes for f in fs) / n,
    )


def build_call_profile(
    outcomes: list[CallOutcome],
    call_type: str,
    existing: CallProfile | None = None,
) -> CallProfile:
    """Build or update a call profile from outcomes.

    Splits outcomes into wins (advanced/closed_won) and losses (stalled/lost),
    computes average features for each, and discovers patterns from the delta.

    Args:
        outcomes: New call outcomes to incorporate.
        call_type: Type of call.
        existing: Optional existing profile to update.

    Returns:
        Updated CallProfile with patterns and confidence.
    """
    all_outcomes = list(existing.outcomes if existing else []) + outcomes
    total = len(all_outcomes)

    wins = [o for o in all_outcomes if o.outcome in ("advanced", "closed_won")]
    losses = [o for o in all_outcomes if o.outcome in ("stalled", "lost")]

    avg = _avg_features(all_outcomes)
    win_feat = _avg_features(wins) if wins else None
    loss_feat = _avg_features(losses) if losses else None

    # Confidence: 5 calls = 0.15, 15 = 0.45, 30 = 0.90
    confidence = min(1.0, total * 0.03)

    # Discover patterns from win/loss delta
    patterns = _discover_patterns(win_feat, loss_feat, total)

    return CallProfile(
        call_type=call_type,
        sample_count=total,
        outcomes=all_outcomes,
        avg_features=avg,
        win_features=win_feat,
        loss_features=loss_feat,
        confidence=round(confidence, 2),
        patterns=patterns,
    )


def _discover_patterns(
    win: CallFeatures | None,
    loss: CallFeatures | None,
    sample_count: int,
) -> list[str]:
    """Discover behavioral patterns from win/loss feature deltas.

    Only reports patterns where the delta is meaningful (>20% difference
    or absolute threshold). These become lesson candidates for graduation.
    """
    if not win or not loss or sample_count < 5:
        return []

    patterns: list[str] = []

    # Talk ratio
    if win.talk_ratio < loss.talk_ratio - 0.08:
        patterns.append(
            f"Talk less: wins avg {win.talk_ratio:.0%} talk ratio vs losses {loss.talk_ratio:.0%}"
        )
    elif win.talk_ratio > loss.talk_ratio + 0.08:
        patterns.append(f"Talk more: wins avg {win.talk_ratio:.0%} vs losses {loss.talk_ratio:.0%}")

    # Pain questions
    if win.pain_question_count > loss.pain_question_count + 1:
        patterns.append(
            f"Ask more pain questions: wins avg {win.pain_question_count} vs "
            f"losses {loss.pain_question_count}"
        )

    # Open questions
    if win.open_question_ratio > loss.open_question_ratio + 0.15:
        patterns.append(
            f"Use more open questions: wins {win.open_question_ratio:.0%} open vs "
            f"losses {loss.open_question_ratio:.0%}"
        )

    # Stories
    if win.story_count > loss.story_count + 0.5:
        patterns.append(
            f"Deploy more stories/proof: wins avg {win.story_count:.1f} vs "
            f"losses {loss.story_count:.1f}"
        )

    # Discovery depth
    if win.discovery_minutes > loss.discovery_minutes + 2:
        patterns.append(
            f"Spend more time in discovery: wins avg {win.discovery_minutes:.0f}min vs "
            f"losses {loss.discovery_minutes:.0f}min before pitching"
        )

    # Commitment specificity
    if win.commitment_specificity > loss.commitment_specificity + 0.2:
        patterns.append(
            f"Make commitments specific: wins {win.commitment_specificity:.0%} specific vs "
            f"losses {loss.commitment_specificity:.0%}"
        )

    # Objection handling
    if win.objection_responses > 0 and loss.objection_responses == 0:
        patterns.append("Address objections directly — wins always respond, losses ignore")
    elif (
        win.objection_count > 0
        and loss.objection_count > 0
        and win.objection_responses / max(1, win.objection_count)
        > loss.objection_responses / max(1, loss.objection_count) + 0.2
    ):
        win_rate = win.objection_responses / max(1, win.objection_count)
        loss_rate = loss.objection_responses / max(1, loss.objection_count)
        patterns.append(
            f"Handle more objections: wins respond to {win_rate:.0%} vs losses {loss_rate:.0%}"
        )

    # Monologue length
    if win.longest_monologue < loss.longest_monologue - 30:
        patterns.append(
            f"Keep monologues shorter: wins max {win.longest_monologue} words vs "
            f"losses {loss.longest_monologue}"
        )

    return patterns


# ---------------------------------------------------------------------------
# Pre-Call Cheat Sheet
# ---------------------------------------------------------------------------


def generate_cheat_sheet(profile: CallProfile, prospect_context: str = "") -> str:
    """Generate a pre-call cheat sheet from graduated call patterns.

    Strength adjusts by confidence level:
    - INSTINCT (<0.60): "Consider..." guidance
    - PATTERN (0.60-0.89): "Do..." directives
    - RULE (0.90+): "REQUIRED:" hard rules

    Args:
        profile: The call profile with graduated patterns.
        prospect_context: Optional prospect-specific context to include.

    Returns:
        Formatted cheat sheet string for pre-call review.
    """
    if profile.sample_count == 0:
        return f"# Pre-Call Cheat Sheet ({profile.call_type})\nNo call data yet. This cheat sheet builds itself after 5+ calls with outcomes."

    conf = profile.confidence
    if conf >= 0.90:
        prefix, strength = "REQUIRED", "Rule"
    elif conf >= 0.60:
        prefix, strength = "DO", "Pattern"
    else:
        prefix, strength = "CONSIDER", "Instinct"

    lines = [
        f"# Pre-Call Cheat Sheet ({profile.call_type})",
        f"# Based on {profile.sample_count} calls | Confidence: {conf:.0%} ({strength})",
        "",
    ]

    # Behavioral targets
    f = profile.avg_features
    wf = profile.win_features

    target = wf if wf else f
    lines.append("## Behavioral Targets")

    if target.talk_ratio > 0:
        emoji = "<<" if target.talk_ratio < 0.40 else ">>" if target.talk_ratio > 0.55 else "=="
        lines.append(
            f"- Talk ratio: {target.talk_ratio:.0%} {emoji} (you {'listen more' if target.talk_ratio < 0.45 else 'drive more'})"
        )

    if target.question_count > 0:
        lines.append(
            f"- Ask {target.question_count}+ questions ({target.pain_question_count}+ pain questions)"
        )

    if target.discovery_minutes > 0:
        lines.append(f"- Spend {target.discovery_minutes:.0f}+ min in discovery before pitching")

    if target.story_count > 0:
        lines.append(f"- Deploy {target.story_count}+ stories/proof points")

    if target.close_attempts > 0:
        lines.append(f"- Make {target.close_attempts}+ close/next-step attempts")

    # Graduated patterns
    if profile.patterns:
        lines.append("")
        lines.append("## Graduated Patterns")
        for p in profile.patterns:
            lines.append(f"- [{prefix}] {p}")

    # Prospect context
    if prospect_context:
        lines.append("")
        lines.append("## Prospect Context")
        lines.append(prospect_context)

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Post-Call Audit
# ---------------------------------------------------------------------------


@dataclass
class AuditCheck:
    """Result of a single post-call audit check."""

    rule: str
    passed: bool
    actual: str
    target: str
    severity: str = "info"  # "info" | "warning" | "critical"


@dataclass
class PostCallAudit:
    """Complete post-call audit against graduated patterns."""

    checks: list[AuditCheck]
    score: float  # 0.0-1.0, fraction of checks passed
    call_type: str
    summary: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": round(self.score, 2),
            "call_type": self.call_type,
            "summary": self.summary,
            "checks": [
                {
                    "rule": c.rule,
                    "passed": c.passed,
                    "actual": c.actual,
                    "target": c.target,
                    "severity": c.severity,
                }
                for c in self.checks
            ],
        }


def post_call_audit(
    features: CallFeatures,
    profile: CallProfile,
) -> PostCallAudit:
    """Audit a call's features against the graduated profile targets.

    Compares the call's actual features against win-pattern targets.
    At RULE confidence, failed checks are "critical". At PATTERN, "warning".
    At INSTINCT, "info".

    Args:
        features: Extracted features from the call being audited.
        profile: The graduated profile with targets.

    Returns:
        PostCallAudit with per-check results and overall score.
    """
    if profile.sample_count < 5:
        return PostCallAudit(
            checks=[],
            score=1.0,
            call_type=features.call_type,
            summary="Not enough data for audit (need 5+ calls with outcomes)",
        )

    target = profile.win_features if profile.win_features else profile.avg_features
    severity = (
        "critical"
        if profile.confidence >= 0.90
        else "warning"
        if profile.confidence >= 0.60
        else "info"
    )

    checks: list[AuditCheck] = []

    # Talk ratio
    if target.talk_ratio > 0:
        ok = abs(features.talk_ratio - target.talk_ratio) < 0.15
        checks.append(
            AuditCheck(
                rule=f"Talk ratio near {target.talk_ratio:.0%}",
                passed=ok,
                actual=f"{features.talk_ratio:.0%}",
                target=f"{target.talk_ratio:.0%} +/- 15%",
                severity=severity,
            )
        )

    # Pain questions
    if target.pain_question_count > 0:
        ok = features.pain_question_count >= target.pain_question_count
        checks.append(
            AuditCheck(
                rule=f"Ask {target.pain_question_count}+ pain questions",
                passed=ok,
                actual=str(features.pain_question_count),
                target=f"{target.pain_question_count}+",
                severity=severity,
            )
        )

    # Questions total
    if target.question_count > 0:
        ok = features.question_count >= max(1, target.question_count - 2)
        checks.append(
            AuditCheck(
                rule=f"Ask {target.question_count}+ questions total",
                passed=ok,
                actual=str(features.question_count),
                target=f"{target.question_count}+",
                severity="info",  # less critical than pain questions
            )
        )

    # Story deployment
    if target.story_count > 0:
        ok = features.story_count >= target.story_count
        checks.append(
            AuditCheck(
                rule=f"Deploy {target.story_count}+ stories/proof points",
                passed=ok,
                actual=str(features.story_count),
                target=f"{target.story_count}+",
                severity=severity,
            )
        )

    # Discovery depth
    if target.discovery_minutes > 2:
        ok = features.discovery_minutes >= target.discovery_minutes * 0.7
        checks.append(
            AuditCheck(
                rule=f"Spend {target.discovery_minutes:.0f}+ min in discovery",
                passed=ok,
                actual=f"{features.discovery_minutes:.0f} min",
                target=f"{target.discovery_minutes:.0f}+ min",
                severity=severity,
            )
        )

    # Close attempt
    if target.close_attempts > 0:
        ok = features.close_attempts >= 1
        checks.append(
            AuditCheck(
                rule="Make at least 1 close/next-step attempt",
                passed=ok,
                actual=str(features.close_attempts),
                target="1+",
                severity="critical" if profile.confidence >= 0.60 else "info",
            )
        )

    # Commitment specificity
    if target.commitment_specificity > 0.3:
        ok = features.commitment_specificity >= 0.5 or features.commitment_count == 0
        checks.append(
            AuditCheck(
                rule="Commitments should include specific dates/times",
                passed=ok,
                actual=f"{features.commitment_specificity:.0%} specific",
                target="50%+",
                severity=severity,
            )
        )

    # Monologue length
    if target.longest_monologue > 0 and target.longest_monologue < 200:
        ok = features.longest_monologue <= target.longest_monologue * 1.5
        checks.append(
            AuditCheck(
                rule=f"Keep monologues under {round(target.longest_monologue * 1.5)} words",
                passed=ok,
                actual=f"{features.longest_monologue} words",
                target=f"<{round(target.longest_monologue * 1.5)} words",
                severity="info",
            )
        )

    passed = sum(1 for c in checks if c.passed)
    score = passed / len(checks) if checks else 1.0

    # Summary
    failed = [c for c in checks if not c.passed]
    if not failed:
        summary = f"All {len(checks)} checks passed. Call matched graduated patterns."
    else:
        top_fails = [f"{c.rule} (actual: {c.actual})" for c in failed[:3]]
        summary = f"{passed}/{len(checks)} passed. Issues: " + "; ".join(top_fails)

    return PostCallAudit(
        checks=checks,
        score=score,
        call_type=features.call_type,
        summary=summary,
    )
