"""
Tone Profile — Graduated Tone Matching for Email Drafting
==========================================================
Layer 1 Enhancement: imports from patterns/ (memory)

Extracts tone features from emails, tracks corrections to tone,
and graduates tone patterns through INSTINCT→PATTERN→RULE.

Unlike static "match my last 20 emails" approaches, this module:
1. Scopes tone by task_type (follow-up tone != cold outreach tone)
2. Tracks which tone features the user corrects vs keeps
3. Graduates tone rules the same way content rules graduate
4. At RULE tier, tone rules become deterministic guards

Tone features extracted:
  - avg_sentence_length: words per sentence
  - formality: ratio of formal markers vs casual markers
  - greeting_style: "hey", "hi", "hello", none
  - cta_style: question, imperative, link, soft-close
  - punctuation: em_dash_count, colon_count, exclamation_count
  - bullet_density: fraction of lines that are bullets
  - paragraph_count: number of paragraphs
  - word_count: total words
  - opener_type: empathy, direct, context, question

Pure computation — no file I/O. The brain-layer wiring (reading sent
emails, persisting profiles) stays in brain/scripts/.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Tone Feature Extraction
# ---------------------------------------------------------------------------

# Formal markers (boost formality score)
_FORMAL_MARKERS = re.compile(
    r"\b(?:regarding|furthermore|additionally|consequently|therefore|"
    r"pursuant|sincerely|respectfully|accordingly|herein)\b", re.I
)

# Casual markers (reduce formality score)
_CASUAL_MARKERS = re.compile(
    r"\b(?:hey|yeah|gonna|wanna|btw|fyi|lol|haha|nope|yep|cool|"
    r"awesome|super|totally|honestly|basically|literally)\b", re.I
)

# Greeting patterns
_GREETING_PATTERNS = [
    (re.compile(r"^hey\b", re.I | re.M), "hey"),
    (re.compile(r"^hi\b", re.I | re.M), "hi"),
    (re.compile(r"^hello\b", re.I | re.M), "hello"),
    (re.compile(r"^dear\b", re.I | re.M), "dear"),
]

# CTA patterns — order matters: most specific first
_CTA_PATTERNS = [
    (re.compile(r"(?:let me know|thoughts\??|sound good|make sense)\b", re.I), "soft-close"),
    (re.compile(r"https?://\S+", re.I), "link"),
    (re.compile(r"(?:book|schedule|click|grab|sign up|register)\b", re.I), "imperative"),
    (re.compile(r"\?[^?]*$", re.M), "question"),
]

# Opener classification
_OPENER_PATTERNS = [
    (re.compile(r"^(?:I\s+(?:know|understand|hear|imagine|get)|sorry|congrats)", re.I), "empathy"),
    (re.compile(r"^(?:quick|two|three|one|just|wanted to)", re.I), "direct"),
    (re.compile(r"^(?:following up|after our|when we|on our|per our)", re.I), "context"),
    (re.compile(r"^(?:have you|do you|did you|are you|what if|how)", re.I), "question"),
]

# Sentence splitter (handles abbreviations reasonably)
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")

# Em dash variants
_EM_DASH = re.compile(r"[\u2014\u2013]|--")


@dataclass
class ToneFeatures:
    """Extracted tone features from a single email.

    All features are numeric or categorical, suitable for comparison
    and averaging across multiple emails.
    """

    avg_sentence_length: float = 0.0
    formality: float = 0.5          # 0.0 = very casual, 1.0 = very formal
    greeting_style: str = "none"    # hey, hi, hello, dear, none
    cta_style: str = "none"         # question, imperative, link, soft-close, none
    opener_type: str = "direct"     # empathy, direct, context, question
    em_dash_count: int = 0
    colon_count: int = 0
    exclamation_count: int = 0
    bullet_density: float = 0.0     # fraction of lines that are bullets
    paragraph_count: int = 1
    word_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for JSON storage."""
        return {
            "avg_sentence_length": round(self.avg_sentence_length, 1),
            "formality": round(self.formality, 2),
            "greeting_style": self.greeting_style,
            "cta_style": self.cta_style,
            "opener_type": self.opener_type,
            "em_dash_count": self.em_dash_count,
            "colon_count": self.colon_count,
            "exclamation_count": self.exclamation_count,
            "bullet_density": round(self.bullet_density, 2),
            "paragraph_count": self.paragraph_count,
            "word_count": self.word_count,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ToneFeatures:
        """Deserialize from dict."""
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


def extract_tone(text: str) -> ToneFeatures:
    """Extract tone features from email text.

    Pure function — no I/O.

    Args:
        text: Raw email body text (no headers).

    Returns:
        ToneFeatures with all fields populated.
    """
    if not text or not text.strip():
        return ToneFeatures()

    lines = text.strip().split("\n")
    words = text.split()
    word_count = len(words)

    # Sentences
    sentences = _SENTENCE_SPLIT.split(text.strip())
    sentences = [s for s in sentences if s.strip()]
    avg_sentence_length = (
        sum(len(s.split()) for s in sentences) / len(sentences)
        if sentences else 0.0
    )

    # Formality
    formal_count = len(_FORMAL_MARKERS.findall(text))
    casual_count = len(_CASUAL_MARKERS.findall(text))
    total_markers = formal_count + casual_count
    formality = (
        formal_count / total_markers if total_markers > 0
        else 0.5  # neutral default
    )

    # Greeting
    greeting = "none"
    first_line = lines[0].strip() if lines else ""
    for pattern, style in _GREETING_PATTERNS:
        if pattern.search(first_line):
            greeting = style
            break

    # CTA (check last 3 lines)
    last_lines = "\n".join(lines[-3:]) if len(lines) >= 3 else text
    cta = "none"
    for pattern, style in _CTA_PATTERNS:
        if pattern.search(last_lines):
            cta = style
            break

    # Opener (first non-greeting, non-empty line)
    opener = "direct"
    body_start = 1 if greeting != "none" else 0
    for line in lines[body_start:]:
        stripped = line.strip()
        if not stripped:
            continue
        for pattern, style in _OPENER_PATTERNS:
            if pattern.search(stripped):
                opener = style
                break
        break  # only check first body line

    # Punctuation
    em_dash_count = len(_EM_DASH.findall(text))
    colon_count = text.count(":")
    exclamation_count = text.count("!")

    # Bullets
    bullet_lines = sum(1 for l in lines if l.strip().startswith(("-", "*", "\u2022")))
    bullet_density = bullet_lines / len(lines) if lines else 0.0

    # Paragraphs (separated by blank lines)
    paragraphs = [p for p in text.split("\n\n") if p.strip()]

    return ToneFeatures(
        avg_sentence_length=avg_sentence_length,
        formality=formality,
        greeting_style=greeting,
        cta_style=cta,
        opener_type=opener,
        em_dash_count=em_dash_count,
        colon_count=colon_count,
        exclamation_count=exclamation_count,
        bullet_density=bullet_density,
        paragraph_count=len(paragraphs),
        word_count=word_count,
    )


# ---------------------------------------------------------------------------
# Tone Profile (aggregated from multiple emails)
# ---------------------------------------------------------------------------


@dataclass
class ToneProfile:
    """Aggregated tone profile from N emails, scoped by task_type.

    This is the graduated output: after N emails of a given type,
    the profile represents the user's settled voice for that context.

    Attributes:
        task_type: Email context (cold_outreach, follow_up, break_up, demo_prep, etc.)
        sample_count: Number of emails contributing to this profile
        features: Averaged numeric features + mode for categoricals
        corrections: Count of times the user corrected tone in this task_type
        confidence: 0.0-1.0, graduates like lessons
    """

    task_type: str
    sample_count: int = 0
    features: ToneFeatures = field(default_factory=ToneFeatures)
    corrections: int = 0
    confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_type": self.task_type,
            "sample_count": self.sample_count,
            "features": self.features.to_dict(),
            "corrections": self.corrections,
            "confidence": round(self.confidence, 2),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ToneProfile:
        features = ToneFeatures.from_dict(d.get("features", {}))
        return cls(
            task_type=d["task_type"],
            sample_count=d.get("sample_count", 0),
            features=features,
            corrections=d.get("corrections", 0),
            confidence=d.get("confidence", 0.0),
        )


def build_tone_profile(
    emails: list[str],
    task_type: str,
    existing: ToneProfile | None = None,
) -> ToneProfile:
    """Build or update a tone profile from a list of email texts.

    Incrementally updates an existing profile if provided, or creates
    a new one. Uses exponential moving average for numeric features
    so recent emails weight more than old ones.

    Args:
        emails: List of email body texts (most recent first).
        task_type: The email context type.
        existing: Optional existing profile to update.

    Returns:
        Updated ToneProfile with graduated confidence.
    """
    if not emails:
        return existing or ToneProfile(task_type=task_type)

    # Extract features from all emails
    all_features = [extract_tone(email) for email in emails]

    # Compute averaged numeric features
    n = len(all_features)
    avg_sentence = sum(f.avg_sentence_length for f in all_features) / n
    avg_formality = sum(f.formality for f in all_features) / n
    avg_bullets = sum(f.bullet_density for f in all_features) / n
    avg_paragraphs = sum(f.paragraph_count for f in all_features) / n
    avg_words = sum(f.word_count for f in all_features) / n
    avg_em_dash = sum(f.em_dash_count for f in all_features) / n
    avg_colon = sum(f.colon_count for f in all_features) / n
    avg_exclamation = sum(f.exclamation_count for f in all_features) / n

    # Mode for categoricals (most common value)
    def _mode(values: list[str]) -> str:
        counts: dict[str, int] = {}
        for v in values:
            counts[v] = counts.get(v, 0) + 1
        return max(counts, key=lambda k: counts[k]) if counts else "none"

    greeting = _mode([f.greeting_style for f in all_features])
    cta = _mode([f.cta_style for f in all_features])
    opener = _mode([f.opener_type for f in all_features])

    features = ToneFeatures(
        avg_sentence_length=avg_sentence,
        formality=avg_formality,
        greeting_style=greeting,
        cta_style=cta,
        opener_type=opener,
        em_dash_count=round(avg_em_dash),
        colon_count=round(avg_colon),
        exclamation_count=round(avg_exclamation),
        bullet_density=avg_bullets,
        paragraph_count=round(avg_paragraphs),
        word_count=round(avg_words),
    )

    # Compute confidence based on sample size
    # 5 emails = 0.30 (INSTINCT), 15 = 0.60 (PATTERN), 30 = 0.90 (RULE)
    total_samples = n + (existing.sample_count if existing else 0)
    confidence = min(1.0, total_samples * 0.03)  # linear ramp, caps at ~33 samples

    # Blend with existing if provided (EMA with alpha=0.3 for new data)
    if existing and existing.sample_count > 0:
        alpha = 0.3  # weight of new data vs existing
        features.avg_sentence_length = (
            alpha * features.avg_sentence_length
            + (1 - alpha) * existing.features.avg_sentence_length
        )
        features.formality = (
            alpha * features.formality
            + (1 - alpha) * existing.features.formality
        )
        features.bullet_density = (
            alpha * features.bullet_density
            + (1 - alpha) * existing.features.bullet_density
        )
        features.word_count = round(
            alpha * features.word_count
            + (1 - alpha) * existing.features.word_count
        )
        # Categoricals: keep new mode if it differs from existing (correction signal)
        # Otherwise keep existing (stability)

    return ToneProfile(
        task_type=task_type,
        sample_count=total_samples,
        features=features,
        corrections=existing.corrections if existing else 0,
        confidence=round(confidence, 2),
    )


# ---------------------------------------------------------------------------
# Tone Diff (correction detection)
# ---------------------------------------------------------------------------


@dataclass
class ToneDiff:
    """Diff between draft tone and final (corrected) tone.

    When the user edits an email's tone, this captures what changed.
    Used to generate tone lessons that graduate through the pipeline.
    """

    field: str           # which feature changed (e.g., "formality", "greeting_style")
    draft_value: Any     # value in the draft
    final_value: Any     # value after the user's edit
    delta: float = 0.0   # numeric delta (0 for categoricals)
    significance: str = "minor"  # "minor" | "major"


def compute_tone_diff(draft: str, final: str) -> list[ToneDiff]:
    """Compute tone differences between draft and final email.

    Returns a list of ToneDiff objects for features that changed
    meaningfully. Minor variations (< threshold) are filtered out.

    Args:
        draft: The AI-generated draft text.
        final: The user's edited version.

    Returns:
        List of ToneDiff objects, empty if no meaningful tone changes.
    """
    draft_features = extract_tone(draft)
    final_features = extract_tone(final)
    diffs: list[ToneDiff] = []

    # Numeric features with thresholds
    numeric_checks = [
        ("avg_sentence_length", 3.0),   # 3+ words difference is meaningful
        ("formality", 0.15),             # 15% shift is meaningful
        ("bullet_density", 0.10),        # 10% shift
        ("word_count", 20),              # 20+ words added/removed
        ("em_dash_count", 1),            # any em dash change
        ("exclamation_count", 1),        # any exclamation change
    ]

    for field_name, threshold in numeric_checks:
        draft_val = getattr(draft_features, field_name)
        final_val = getattr(final_features, field_name)
        delta = final_val - draft_val

        if abs(delta) >= threshold:
            significance = "major" if abs(delta) >= threshold * 2 else "minor"
            diffs.append(ToneDiff(
                field=field_name,
                draft_value=draft_val,
                final_value=final_val,
                delta=round(delta, 2),
                significance=significance,
            ))

    # Categorical features (any change is meaningful)
    categorical_checks = ["greeting_style", "cta_style", "opener_type"]
    for field_name in categorical_checks:
        draft_val = getattr(draft_features, field_name)
        final_val = getattr(final_features, field_name)
        if draft_val != final_val:
            diffs.append(ToneDiff(
                field=field_name,
                draft_value=draft_val,
                final_value=final_val,
                significance="major",
            ))

    return diffs


def tone_diff_to_lesson(diffs: list[ToneDiff], task_type: str) -> str | None:
    """Convert tone diffs into a lesson description for the graduation pipeline.

    Only generates a lesson if there are major diffs. Minor diffs are noise.

    Args:
        diffs: Output of compute_tone_diff.
        task_type: Email task type for scoping.

    Returns:
        Lesson description string, or None if no lesson warranted.
    """
    major_diffs = [d for d in diffs if d.significance == "major"]
    if not major_diffs:
        return None

    parts = []
    for d in major_diffs:
        if isinstance(d.draft_value, (int, float)):
            direction = "increase" if d.delta > 0 else "decrease"
            parts.append(f"{direction} {d.field} (was {d.draft_value}, corrected to {d.final_value})")
        else:
            parts.append(f"change {d.field} from '{d.draft_value}' to '{d.final_value}'")

    description = f"In {task_type} emails: " + "; ".join(parts)
    return description


# ---------------------------------------------------------------------------
# Tone Prompt Generation
# ---------------------------------------------------------------------------


def generate_tone_prompt(profile: ToneProfile) -> str:
    """Generate a prompt injection string from a tone profile.

    This is what gets injected into the drafting prompt to guide
    the LLM toward the user's established tone for this email type.

    At INSTINCT confidence (<0.60): weak guidance ("consider")
    At PATTERN confidence (0.60-0.89): moderate ("use")
    At RULE confidence (0.90+): strong ("always/never")

    Args:
        profile: The tone profile to convert to prompt text.

    Returns:
        Prompt text string. Empty string if profile has no data.
    """
    if profile.sample_count == 0:
        return ""

    f = profile.features
    confidence = profile.confidence

    # Determine strength words
    if confidence >= 0.90:
        verb, neg = "Always", "Never"
    elif confidence >= 0.60:
        verb, neg = "Use", "Avoid"
    else:
        verb, neg = "Consider using", "Consider avoiding"

    lines = [f"# Tone Profile ({profile.task_type}, {profile.sample_count} samples, confidence {confidence:.0%})"]

    # Sentence length
    if f.avg_sentence_length > 0:
        if f.avg_sentence_length < 12:
            lines.append(f"- {verb} short sentences (~{f.avg_sentence_length:.0f} words)")
        elif f.avg_sentence_length > 20:
            lines.append(f"- {verb} longer, detailed sentences (~{f.avg_sentence_length:.0f} words)")

    # Formality
    if f.formality < 0.3:
        lines.append(f"- {verb} casual, conversational tone")
    elif f.formality > 0.7:
        lines.append(f"- {verb} formal, professional tone")

    # Greeting
    if f.greeting_style != "none":
        lines.append(f"- {verb} '{f.greeting_style}' as greeting")

    # Opener
    if f.opener_type != "direct":
        lines.append(f"- {verb} {f.opener_type} opener")

    # CTA
    if f.cta_style != "none":
        lines.append(f"- {verb} {f.cta_style} CTA style")

    # Em dashes (commonly corrected out)
    if f.em_dash_count == 0 and confidence >= 0.60:
        lines.append(f"- {neg} em dashes. Use colons or commas instead.")

    # Exclamations
    if f.exclamation_count == 0 and confidence >= 0.60:
        lines.append(f"- {neg} exclamation marks")

    # Bullets
    if f.bullet_density > 0.15:
        lines.append(f"- {verb} bullet lists ({f.bullet_density:.0%} of lines)")
    elif f.bullet_density < 0.05 and confidence >= 0.60:
        lines.append(f"- {neg} bullet lists (prefer prose)")

    # Word count
    if f.word_count > 0:
        lines.append(f"- Target ~{f.word_count} words")

    return "\n".join(lines)
