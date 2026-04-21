"""
Orchestrator — Domain-Agnostic Pattern Router
==============================================
Maps any incoming request to one of the 15 base agentic patterns and, where
applicable, selects a secondary pattern for multi-step workflows.

All intent detection is driven by the configurable task-type registry in
``scope.py``.  There are no sales-specific (or domain-specific) if/elif
chains hardcoded here.  Domains extend behaviour by calling
``register_intent_pattern`` at process startup.

Architecture note
-----------------
The 15 base patterns below come from established agentic-systems literature.
The Gradata treats them as primitives; domain logic (CARL rules,
gates, voice) enhances *on top* of these primitives without replacing them.

The 15 base patterns
--------------------
1.  reflection          — Self-evaluation and quality checking
2.  tool_use            — Calling external tools / APIs
3.  planning            — Goal decomposition and step sequencing
4.  memory              — Storing / retrieving past context
5.  multi_agent         — Spawning or coordinating sub-agents
6.  chain_of_thought    — Step-by-step reasoning
7.  react               — Reason + Act interleaved loops
8.  retrieval           — Fetching relevant knowledge (RAG)
9.  summarization       — Condensing large inputs
10. generation          — Open-ended content production
11. classification      — Labelling or routing inputs
12. extraction          — Pulling structured data from unstructured text
13. transformation      — Reformatting or translating existing content
14. validation          — Checking outputs against a rubric or schema
15. orchestration       — Coordinating a pipeline of the above patterns

Example::

    from gradata.contrib.patterns.orchestrator import classify_request

    result = classify_request("review this pull request")
    print(result.intent)            # code_review
    print(result.selected_pattern)  # reflection

    result = classify_request("prepare for the upcoming meeting")
    print(result.intent)            # meeting_prep
    print(result.selected_pattern)  # retrieval
"""

from __future__ import annotations

from dataclasses import dataclass, field

from gradata.rules.scope import (
    AudienceTier,
    classify_scope,
)

# ---------------------------------------------------------------------------
# Pattern constants
# ---------------------------------------------------------------------------

PATTERN_REFLECTION = "reflection"
PATTERN_TOOL_USE = "tool_use"
PATTERN_PLANNING = "planning"
PATTERN_MEMORY = "memory"
PATTERN_MULTI_AGENT = "multi_agent"
PATTERN_CHAIN_OF_THOUGHT = "chain_of_thought"
PATTERN_REACT = "react"
PATTERN_RETRIEVAL = "retrieval"
PATTERN_SUMMARIZATION = "summarization"
PATTERN_GENERATION = "generation"
PATTERN_CLASSIFICATION = "classification"
PATTERN_EXTRACTION = "extraction"
PATTERN_TRANSFORMATION = "transformation"
PATTERN_VALIDATION = "validation"
PATTERN_ORCHESTRATION = "orchestration"

ALL_PATTERNS: frozenset[str] = frozenset(
    {
        PATTERN_REFLECTION,
        PATTERN_TOOL_USE,
        PATTERN_PLANNING,
        PATTERN_MEMORY,
        PATTERN_MULTI_AGENT,
        PATTERN_CHAIN_OF_THOUGHT,
        PATTERN_REACT,
        PATTERN_RETRIEVAL,
        PATTERN_SUMMARIZATION,
        PATTERN_GENERATION,
        PATTERN_CLASSIFICATION,
        PATTERN_EXTRACTION,
        PATTERN_TRANSFORMATION,
        PATTERN_VALIDATION,
        PATTERN_ORCHESTRATION,
    }
)


# ---------------------------------------------------------------------------
# Intent-to-pattern mapping
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class IntentPattern:
    """Maps a named intent to its primary pattern and optional secondaries.

    Attributes:
        intent: The task-type name (must match a ``TaskType.name`` in scope.py).
        primary: The first base pattern to activate.
        secondary: Ordered list of additional patterns for multi-step workflows.
    """

    intent: str
    primary: str
    secondary: list[str] = field(default_factory=list)


# Default mapping — domain-agnostic.  Covers generic, engineering, recruiting,
# and sales intents without any domain-specific logic.
DEFAULT_INTENT_PATTERNS: list[IntentPattern] = [
    # ── Generic / cross-domain ───────────────────────────────────────────────
    IntentPattern(
        intent="meeting_prep",
        primary=PATTERN_RETRIEVAL,
        secondary=[PATTERN_SUMMARIZATION, PATTERN_GENERATION],
    ),
    IntentPattern(
        intent="research",
        primary=PATTERN_RETRIEVAL,
        secondary=[PATTERN_EXTRACTION, PATTERN_SUMMARIZATION],
    ),
    IntentPattern(
        intent="content_creation",
        primary=PATTERN_GENERATION,
        secondary=[PATTERN_REFLECTION, PATTERN_VALIDATION],
    ),
    IntentPattern(
        intent="report_generation",
        primary=PATTERN_GENERATION,
        secondary=[PATTERN_RETRIEVAL, PATTERN_SUMMARIZATION, PATTERN_VALIDATION],
    ),
    IntentPattern(
        intent="data_analysis",
        primary=PATTERN_EXTRACTION,
        secondary=[PATTERN_CHAIN_OF_THOUGHT, PATTERN_GENERATION],
    ),
    IntentPattern(
        intent="documentation",
        primary=PATTERN_GENERATION,
        secondary=[PATTERN_RETRIEVAL, PATTERN_REFLECTION],
    ),
    IntentPattern(
        intent="summary",
        primary=PATTERN_SUMMARIZATION,
        secondary=[PATTERN_EXTRACTION],
    ),
    IntentPattern(
        intent="planning",
        primary=PATTERN_PLANNING,
        secondary=[PATTERN_CHAIN_OF_THOUGHT, PATTERN_ORCHESTRATION],
    ),
    # ── Engineering / developer ──────────────────────────────────────────────
    IntentPattern(
        intent="code_review",
        primary=PATTERN_REFLECTION,
        secondary=[PATTERN_VALIDATION, PATTERN_GENERATION],
    ),
    IntentPattern(
        intent="debugging",
        primary=PATTERN_REACT,
        secondary=[PATTERN_CHAIN_OF_THOUGHT, PATTERN_TOOL_USE],
    ),
    IntentPattern(
        intent="design_review",
        primary=PATTERN_REFLECTION,
        secondary=[PATTERN_VALIDATION, PATTERN_GENERATION],
    ),
    IntentPattern(
        intent="refactoring",
        primary=PATTERN_TRANSFORMATION,
        secondary=[PATTERN_REFLECTION, PATTERN_VALIDATION],
    ),
    # ── Recruiting / talent ──────────────────────────────────────────────────
    IntentPattern(
        intent="interview_prep",
        primary=PATTERN_RETRIEVAL,
        secondary=[PATTERN_GENERATION, PATTERN_REFLECTION],
    ),
    IntentPattern(
        intent="candidate_search",
        primary=PATTERN_TOOL_USE,
        secondary=[PATTERN_EXTRACTION, PATTERN_CLASSIFICATION],
    ),
    IntentPattern(
        intent="job_description",
        primary=PATTERN_GENERATION,
        secondary=[PATTERN_REFLECTION, PATTERN_VALIDATION],
    ),
    # ── Sales (preserved for backward compatibility) ─────────────────────────
    IntentPattern(
        intent="email_draft",
        primary=PATTERN_GENERATION,
        secondary=[PATTERN_RETRIEVAL, PATTERN_REFLECTION],
    ),
    IntentPattern(
        intent="demo_prep",
        primary=PATTERN_RETRIEVAL,
        secondary=[PATTERN_SUMMARIZATION, PATTERN_GENERATION],
    ),
    IntentPattern(
        intent="prospecting",
        primary=PATTERN_TOOL_USE,
        secondary=[PATTERN_EXTRACTION, PATTERN_CLASSIFICATION],
    ),
    IntentPattern(
        intent="objection_handling",
        primary=PATTERN_RETRIEVAL,
        secondary=[PATTERN_CHAIN_OF_THOUGHT, PATTERN_GENERATION],
    ),
    IntentPattern(
        intent="follow_up",
        primary=PATTERN_MEMORY,
        secondary=[PATTERN_GENERATION, PATTERN_REFLECTION],
    ),
    IntentPattern(
        intent="crm_update",
        primary=PATTERN_EXTRACTION,
        secondary=[PATTERN_TOOL_USE],
    ),
]

# Fallback when the intent has no explicit mapping.
_DEFAULT_FALLBACK = IntentPattern(
    intent="general",
    primary=PATTERN_GENERATION,
    secondary=[PATTERN_REFLECTION],
)


# ---------------------------------------------------------------------------
# Runtime-configurable registry
# ---------------------------------------------------------------------------

_REGISTERED_INTENT_PATTERNS: list[IntentPattern] = list(DEFAULT_INTENT_PATTERNS)
# O(1) lookup mirror of _REGISTERED_INTENT_PATTERNS; rebuilt on registration.
_REGISTERED_INTENT_INDEX: dict[str, IntentPattern] = {
    p.intent: p for p in _REGISTERED_INTENT_PATTERNS
}


def register_intent_pattern(
    intent: str,
    pattern: str,
    secondary: list[str] | None = None,
    *,
    prepend: bool = False,
) -> None:
    """Register or replace an intent-to-pattern mapping.

    Domain-specific brains call this at startup to wire custom intents (added
    via ``register_task_type``) to the appropriate base patterns.

    Args:
        intent: The task-type name to map (e.g. ``"policy_review"``).  If an
            existing entry with this name exists it is replaced.
        pattern: The primary base pattern identifier.  Must be one of the
            constants defined in this module (e.g. ``PATTERN_REFLECTION``).
        secondary: Optional ordered list of secondary pattern identifiers
            for multi-step workflows.
        prepend: When ``True`` the new entry is inserted at position 0 so it
            takes precedence during lookup.

    Raises:
        ValueError: If ``pattern`` or any element of ``secondary`` is not a
            recognised base pattern identifier.

    Example::

        from gradata.contrib.patterns.orchestrator import (
            register_intent_pattern,
            PATTERN_REFLECTION,
            PATTERN_VALIDATION,
        )

        register_intent_pattern(
            intent="policy_review",
            pattern=PATTERN_REFLECTION,
            secondary=[PATTERN_VALIDATION],
        )
    """
    if pattern not in ALL_PATTERNS:
        raise ValueError(f"Unknown pattern {pattern!r}.  Must be one of: {sorted(ALL_PATTERNS)}")
    bad = [s for s in (secondary or []) if s not in ALL_PATTERNS]
    if bad:
        raise ValueError(
            f"Unknown secondary pattern(s) {bad!r}.  Must be one of: {sorted(ALL_PATTERNS)}"
        )

    global _REGISTERED_INTENT_PATTERNS
    _REGISTERED_INTENT_PATTERNS = [p for p in _REGISTERED_INTENT_PATTERNS if p.intent != intent]

    entry = IntentPattern(
        intent=intent,
        primary=pattern,
        secondary=list(secondary or []),
    )
    if prepend:
        _REGISTERED_INTENT_PATTERNS.insert(0, entry)
    else:
        _REGISTERED_INTENT_PATTERNS.append(entry)

    # Keep the dict index in sync for O(1) classify_request lookup.
    _REGISTERED_INTENT_INDEX[entry.intent] = entry


# ---------------------------------------------------------------------------
# Classification result
# ---------------------------------------------------------------------------


@dataclass
class RequestClassification:
    """Full classification of a single incoming request.

    Attributes:
        query: The original raw query string.
        intent: Detected task-type name (snake_case).  ``"general"`` when no
            registered keyword matched.
        audience: Detected audience tier.
        selected_pattern: Primary base pattern chosen for this request.
        secondary_patterns: Ordered secondary patterns for multi-step execution.
        confidence: Rough confidence score (0.0–1.0).  Currently rule-based;
            a future version will use embedding similarity.
    """

    query: str
    intent: str
    audience: AudienceTier
    selected_pattern: str
    secondary_patterns: list[str]
    confidence: float


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def classify_request(query: str) -> RequestClassification:
    """Classify a raw query and return the full routing decision.

    Detects the task type and audience via the scope classifier, then looks up
    the primary and secondary patterns from the configurable registry.

    Args:
        query: The raw user request in any case.

    Returns:
        A ``RequestClassification`` with all routing fields populated.

    Example::

        result = classify_request("review this pull request")
        print(result.intent)            # code_review
        print(result.selected_pattern)  # reflection

        result = classify_request("complete this task for the client")
        print(result.intent)            # general
        print(result.selected_pattern)  # generation
    """
    intent_name, audience = classify_scope(query)

    # O(1) dict lookup (was an O(N) linear scan of _REGISTERED_INTENT_PATTERNS).
    matched = _REGISTERED_INTENT_INDEX.get(intent_name, _DEFAULT_FALLBACK)

    # Confidence is 1.0 when we matched a specific intent, 0.5 for the
    # fallback.  The audience detection does not yet adjust this score.
    confidence = 1.0 if intent_name != "general" else 0.5

    return RequestClassification(
        query=query,
        intent=intent_name,
        audience=audience,
        selected_pattern=matched.primary,
        secondary_patterns=list(matched.secondary),
        confidence=confidence,
    )


# ---------------------------------------------------------------------------
# Keyword-based route rules (extracted from brain/scripts/spawn.py)
# ---------------------------------------------------------------------------
# This is a simpler, domain-agnostic routing mechanism that maps keyword
# lists to agent names.  Domains register their own rules at startup;
# ``route_by_keywords`` then matches an incoming task description.


@dataclass
class RouteRule:
    """Maps a list of keyword phrases to an agent name.

    Matching is case-insensitive substring containment.  The first rule
    whose keywords match wins, so ordering matters (register more specific
    or multi-word patterns first).

    Attributes:
        keywords: Phrases to search for in the task description (any match wins).
        agent: The agent name to route to when a keyword matches.
    """

    keywords: list[str]
    agent: str


_ROUTE_RULES: list[RouteRule] = []
_ROUTE_DEFAULT: str = "general"


def register_route_rules(
    rules: list[tuple[list[str], str]],
    *,
    default_agent: str | None = None,
    replace: bool = False,
) -> None:
    """Register keyword-to-agent routing rules.

    Args:
        rules: List of ``(keywords, agent_name)`` tuples.  Each ``keywords``
            is a list of phrases; if *any* phrase appears in the task
            description the task routes to ``agent_name``.  Order matters:
            earlier rules take priority.
        default_agent: Fallback agent when no rule matches.  If ``None``
            the current default is kept.
        replace: When ``True`` the existing rule list is replaced entirely.
            When ``False`` (default) the new rules are **prepended** so they
            take priority over previously registered rules.

    Example::

        from gradata.contrib.patterns.orchestrator import register_route_rules

        register_route_rules([
            (["research", "enrich", "qualify"], "prospector"),
            (["write", "draft", "email"], "writer"),
        ], default_agent="prospector")
    """
    global _ROUTE_RULES, _ROUTE_DEFAULT

    new_rules = [RouteRule(keywords=kw, agent=agent) for kw, agent in rules]
    _ROUTE_RULES = new_rules if replace else new_rules + _ROUTE_RULES

    if default_agent is not None:
        _ROUTE_DEFAULT = default_agent


def get_route_rules() -> list[RouteRule]:
    """Return a copy of the current route-rule list."""
    return list(_ROUTE_RULES)


def route_by_keywords(task_description: str) -> str:
    """Match a task description to an agent name via registered keyword rules.

    Performs case-insensitive substring matching against each rule's keyword
    list, in registration order.  Returns the first matching agent name, or
    the default agent if no rule matches.

    Args:
        task_description: Free-text description of the task to route.

    Returns:
        The agent name string for the matched (or default) route.
    """
    task_lower = task_description.lower()
    for rule in _ROUTE_RULES:
        for kw in rule.keywords:
            if kw in task_lower:
                return rule.agent
    return _ROUTE_DEFAULT


def execute_orchestrated(
    tasks: list[str],
    worker: object,
    brain: object | None = None,
    *,
    max_concurrent: int = 3,
) -> dict:
    """Orchestrator-driven execution: classifies tasks and decides strategy.

    - Single task: runs worker directly
    - Multiple independent tasks: uses brain.spawn_queue() for parallel execution
    - Multi-step dependent tasks: runs sequentially

    Args:
        tasks: List of task descriptions.
        worker: Callable (task: str) -> dict.
        brain: Optional Brain instance for spawn_queue and event logging.
        max_concurrent: Max parallel workers when queueing.

    Returns:
        Dict with strategy used, results, and classifications.
    """
    if not tasks:
        return {"strategy": "empty", "results": []}

    # Single task — just run it
    if len(tasks) == 1:
        try:
            result = worker(tasks[0])  # type: ignore[operator]
            return {
                "strategy": "direct",
                "results": [{"task": tasks[0], "status": "completed", "result": result}],
            }
        except Exception as e:
            return {
                "strategy": "direct",
                "results": [{"task": tasks[0], "status": "failed", "error": str(e)}],
            }

    # Multiple tasks — classify to check if they're independent
    classifications = [classify_request(t) for t in tasks]
    patterns = {c.selected_pattern for c in classifications}

    # If brain has spawn_queue, use it for parallel execution
    if brain and hasattr(brain, "spawn_queue"):
        _sq = brain.spawn_queue  # type: ignore[union-attr]
        result = _sq(tasks=tasks, worker=worker, max_concurrent=max_concurrent)
        result["strategy"] = "queue"
        result["patterns_detected"] = sorted(patterns)
        return result

    # Fallback: sequential execution
    results = []
    for task in tasks:
        try:
            r = worker(task)  # type: ignore[operator]
            results.append({"task": task, "status": "completed", "result": r})
        except Exception as e:
            results.append({"task": task, "status": "failed", "error": str(e)})

    return {"strategy": "sequential", "results": results, "patterns_detected": sorted(patterns)}
