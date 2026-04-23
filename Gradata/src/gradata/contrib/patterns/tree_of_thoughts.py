"""
Tree of Thoughts — branching exploration for graduation decisions.
Evaluates multiple candidate rule wordings before committing to one.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable


@dataclass
class Thought:
    """A single candidate in the exploration tree."""

    content: str
    score: float = 0.0
    rationale: str = ""
    children: list[Thought] = field(default_factory=list)

    @property
    def is_leaf(self) -> bool:
        return len(self.children) == 0


@dataclass
class ToTResult:
    """Result of Tree of Thoughts exploration."""

    best: Thought
    alternatives: list[Thought]
    depth: int
    total_explored: int


def explore(
    candidates: list[str],
    scorer: Callable[[str], tuple[float, str]],
    *,
    branch_factor: int = 3,
    max_depth: int = 2,
    min_score: float = 0.5,
) -> ToTResult:
    """Explore candidate rule wordings using tree search.

    Args:
        candidates: Initial candidate strings to evaluate.
        scorer: (candidate: str) -> (score: float, rationale: str).
        branch_factor: Max children per node.
        max_depth: Max depth to explore.
        min_score: Minimum score to continue expanding a branch.

    Returns:
        ToTResult with the best candidate and alternatives.
    """
    root_thoughts: list[Thought] = []
    total = 0

    for candidate in candidates[:branch_factor]:
        score, rationale = scorer(candidate)
        total += 1
        thought = Thought(content=candidate, score=score, rationale=rationale)
        root_thoughts.append(thought)

    # Sort by score descending
    root_thoughts.sort(key=lambda t: t.score, reverse=True)

    # Expand top candidates to depth
    if max_depth > 1 and root_thoughts:
        for thought in root_thoughts[:branch_factor]:
            if thought.score >= min_score:
                # Generate variations (append refinement markers)
                variations = [
                    f"{thought.content} (more specific)",
                    f"{thought.content} (more general)",
                    f"{thought.content} (with exception)",
                ]
                for var in variations[:branch_factor]:
                    score, rationale = scorer(var)
                    total += 1
                    child = Thought(content=var, score=score, rationale=rationale)
                    thought.children.append(child)

    # Flatten and find best
    all_thoughts = list(root_thoughts)
    for t in root_thoughts:
        all_thoughts.extend(t.children)

    all_thoughts.sort(key=lambda t: t.score, reverse=True)
    best = all_thoughts[0] if all_thoughts else Thought(content="", score=0.0)
    alternatives = all_thoughts[1:5] if len(all_thoughts) > 1 else []

    return ToTResult(
        best=best,
        alternatives=alternatives,
        depth=max_depth,
        total_explored=total,
    )


def evaluate_rule_candidates(
    lesson_description: str,
    existing_rules: list[str],
    scorer: Callable[[str], tuple[float, str]] | None = None,
) -> ToTResult:
    """Evaluate multiple wordings for a graduating rule.

    When a lesson is about to graduate from PATTERN to RULE, this
    explores different phrasings to find the most precise, actionable
    wording. Prevents vague rules from graduating.

    Args:
        lesson_description: The lesson text to refine.
        existing_rules: Current rules (to check for overlap/contradiction).
        scorer: Custom scorer. Default uses keyword overlap heuristic.

    Returns:
        ToTResult with best rule wording.
    """
    effective_scorer: Callable[[str], tuple[float, str]]
    if scorer is None:

        def _default_scorer(candidate: str) -> tuple[float, str]:
            # Heuristic: shorter, more specific rules score higher
            words = candidate.split()
            length_score = max(0.0, 1.0 - len(words) / 50)
            # Penalize overlap with existing rules
            overlap_penalty = 0.0
            for rule in existing_rules:
                common = set(candidate.lower().split()) & set(rule.lower().split())
                if len(common) > 5:
                    overlap_penalty += 0.2
            score = round(length_score - overlap_penalty, 4)
            return (
                max(0.0, min(1.0, score)),
                f"length={len(words)}, overlap_penalty={overlap_penalty:.2f}",
            )

        effective_scorer = _default_scorer
    else:
        effective_scorer = scorer

    candidates = [
        lesson_description,
        f"Always {lesson_description.lower().removeprefix('always ')}",
        f"Never {lesson_description.lower().replace('always ', '').replace('use ', 'use ').strip()}",
    ]

    return explore(candidates, effective_scorer)
