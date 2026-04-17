"""
Collaborative Filtering — Cross-brain pattern transfer for the marketplace.
============================================================================
Layer 1 Enhancement: pure logic, stdlib only.

When the marketplace launches, new brains can bootstrap from patterns that
proved themselves in similar brains. This module provides the infrastructure
for cross-brain learning using item-based collaborative filtering.

Core idea: if Brain A and Brain B both graduated the same 5 rules, and Brain A
also graduated rule X, then Brain B should consider rule X as a candidate
with boosted initial confidence.

This module handles the LOCAL side: computing brain similarity vectors,
identifying transferable patterns, and applying confidence boosts.
The CLOUD side (matching brains, aggregating across the platform)
runs on Gradata's servers.

Usage:
    # Export this brain's pattern fingerprint
    fingerprint = BrainFingerprint.from_lessons(my_lessons)

    # Receive recommended patterns from cloud
    recommendations = cloud_client.get_recommendations(fingerprint)

    # Apply boosts to local lessons
    boosted = apply_transfer_boost(local_lessons, recommendations)

Reference: Standard item-based collaborative filtering adapted for
behavioral rules rather than products.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass


@dataclass
class RuleFingerprint:
    """A rule's identity for cross-brain matching.

    Rules are matched on category + description hash, not on the
    exact text (which may vary between brains). The fingerprint
    captures the behavioral intent, not the wording.
    """
    category: str
    description_hash: str     # First 8 chars of SHA-256 of normalized description
    confidence: float
    fire_count: int
    domain: str = ""


@dataclass
class BrainFingerprint:
    """A brain's pattern fingerprint for similarity matching."""
    domain: str
    total_sessions: int
    rules: list[RuleFingerprint]
    category_distribution: dict[str, int]   # category -> rule count

    @classmethod
    def from_lessons(cls, lessons: list, domain: str = "", total_sessions: int = 0) -> BrainFingerprint:
        """Build a fingerprint from a list of Lesson objects."""

        rules = []
        cat_dist: dict[str, int] = {}

        for lesson in lessons:
            # Only include proven patterns (confidence > 0.5)
            if lesson.confidence < 0.5:
                continue

            desc_hash = hashlib.sha256(
                lesson.description.lower().strip().encode()
            ).hexdigest()[:8]

            rules.append(RuleFingerprint(
                category=lesson.category,
                description_hash=desc_hash,
                confidence=lesson.confidence,
                fire_count=lesson.fire_count,
                domain=domain,
            ))

            cat_dist[lesson.category] = cat_dist.get(lesson.category, 0) + 1

        return cls(
            domain=domain,
            total_sessions=total_sessions,
            rules=rules,
            category_distribution=cat_dist,
        )


@dataclass
class TransferRecommendation:
    """A pattern recommended for transfer from another brain."""
    category: str
    description: str
    source_confidence: float     # Confidence in the source brain
    transfer_boost: float        # Suggested confidence boost (0.05-0.20)
    source_brain_similarity: float  # How similar the source brain is (0-1)
    n_brains_graduated: int      # How many brains graduated this pattern


def compute_brain_similarity(a: BrainFingerprint, b: BrainFingerprint) -> float:
    """Compute cosine similarity between two brain fingerprints.

    Uses category distribution as the feature vector. Two brains that
    focus on the same categories (e.g., both heavy on DRAFTING and TONE)
    are more likely to share useful patterns.
    """
    # Build shared category set
    all_cats = set(a.category_distribution.keys()) | set(b.category_distribution.keys())

    if not all_cats:
        return 0.0

    vec_a = [a.category_distribution.get(c, 0) for c in sorted(all_cats)]
    vec_b = [b.category_distribution.get(c, 0) for c in sorted(all_cats)]

    # Cosine similarity
    dot = sum(x * y for x, y in zip(vec_a, vec_b, strict=True))
    mag_a = math.sqrt(sum(x * x for x in vec_a))
    mag_b = math.sqrt(sum(x * x for x in vec_b))

    if mag_a == 0 or mag_b == 0:
        return 0.0

    return round(dot / (mag_a * mag_b), 4)


def apply_transfer_boost(
    local_lessons: list,
    recommendations: list[TransferRecommendation],
    max_boost: float = 0.15,
) -> list:
    """Apply confidence boosts from cross-brain recommendations.

    Only boosts lessons that already exist locally (no injecting foreign
    patterns). The boost is capped at max_boost and scaled by the source
    brain's similarity.

    Returns the modified lessons list (mutated in place).
    """
    for lesson in local_lessons:
        for rec in recommendations:
            if (rec.category == lesson.category
                    and rec.transfer_boost > 0
                    and lesson.confidence < 0.90):  # Don't boost past RULE
                boost = min(
                    rec.transfer_boost * rec.source_brain_similarity,
                    max_boost,
                )
                lesson.confidence = round(
                    min(0.89, lesson.confidence + boost), 2  # Cap below RULE
                )
                break  # One boost per lesson per session

    return local_lessons
