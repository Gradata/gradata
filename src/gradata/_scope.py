"""Scope Builder — rule scoping + context-to-scope inference. RuleScope fields
are hierarchical filters; empty string = wildcard. Flow: ``build_scope(ctx)``
infers a RuleScope; retrieval calls ``scope_matches(rule_scope, query_scope)``
for relevance ranking (0.0 irrelevant → 1.0 perfect match);
``scope_to_dict`` / ``scope_from_dict`` serialise.
SDK LAYER: pure logic, stdlib only. No file I/O.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RuleScope:
    """Immutable descriptor for the context in which a rule applies.

    All fields default to empty string, which acts as a wildcard during
    matching — an empty field in a *rule* scope matches any value in the
    *query* scope.

    Args:
        domain: Operational domain, e.g. "sales", "engineering", "marketing".
        task_type: Classified task kind, e.g. "email_draft", "demo_prep".
        audience: Classified role of the target person, e.g. "c_suite", "vp".
        channel: Delivery channel, e.g. "email", "slack", "document".
        stakes: Risk level — one of "low", "normal", "high", "critical".
    """

    domain: str = ""
    task_type: str = ""
    audience: str = ""
    channel: str = ""
    stakes: str = "normal"
    agent_type: str = ""  # Agent type for scoped rule injection (e.g. "researcher", "reviewer")
    namespace: str = ""  # Scope tag for per-context rules (e.g. "api-endpoint", "onboarding")
    temporal_relevance: str = ""  # "evergreen", "seasonal", "recent", or "" (wildcard)
    max_idle_sessions: int = 0  # Auto-suppress after N idle sessions (0 = never)
    created_session: int = 0  # Session number when this scope was first assigned


def temporal_decay(
    sessions_since_fire: int,
    max_idle: int,
    floor: float = 0.05,
    steepness: float = 3.0,
) -> float:
    """Compute temporal decay multiplier for rule confidence.

    Uses exponential decay: exp(-steepness * ratio^2) where
    ratio = sessions_since_fire / max_idle.

    Returns decay multiplier in [floor, 1.0]. If max_idle=0, returns 1.0 (evergreen).
    """
    if max_idle <= 0:
        return 1.0
    if sessions_since_fire <= 0:
        return 1.0

    import math

    ratio = sessions_since_fire / max_idle
    decay = math.exp(-steepness * ratio * ratio)
    return max(floor, round(decay, 4))


# ---------------------------------------------------------------------------
# Classification constants
# ---------------------------------------------------------------------------

# task_type → keywords (any keyword triggers the type; first match wins)
_TASK_TYPE_KEYWORDS: list[tuple[str, list[str]]] = [
    ("email_draft", ["email", "draft", "write", "compose", "reply", "follow-up", "followup"]),
    ("demo_prep", ["demo", "call", "meeting", "prep", "presentation"]),
    ("prospecting", ["prospect", "lead", "find", "enrich", "list", "sweep"]),
    ("code_review", ["review", "code", "pr", "pull request"]),
    ("documentation", ["doc", "readme", "guide", "spec"]),
]

# audience → title keywords (checked case-insensitively; first match wins)
_AUDIENCE_KEYWORDS: list[tuple[str, list[str]]] = [
    ("c_suite", ["ceo", "cto", "coo", "cfo", "cro", "cmo", "chief"]),
    ("vp", ["vp", "vice president", "head of"]),
    ("director", ["director"]),
    ("manager", ["manager"]),
    # "ic" is the fallback for anything unmatched
]

# channel inference: task keywords → channel
_CHANNEL_KEYWORDS: list[tuple[str, list[str]]] = [
    ("email", ["email", "draft", "compose", "reply", "follow-up", "followup"]),
    ("slack", ["slack", "message", "dm"]),
    ("document", ["doc", "readme", "guide", "spec", "report"]),
    ("call", ["call", "meeting", "demo", "presentation"]),
]

# stakes inference: task keywords → stakes override
_STAKES_KEYWORDS: list[tuple[str, list[str]]] = [
    ("high", ["demo", "call", "meeting", "presentation", "proposal", "critical"]),
    ("low", ["internal", "draft", "note"]),
]


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _classify(text: str, table: list[tuple[str, list[str]]]) -> str:
    """Return the first category whose keywords appear in *text* (lowercased).

    Args:
        text: The text to search within.
        table: Ordered list of ``(category, [keyword, ...])`` pairs.

    Returns:
        Matched category string, or empty string if none match.
    """
    normalised = text.lower()
    for category, keywords in table:
        if any(kw in normalised for kw in keywords):
            return category
    return ""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_scope(context: dict[str, Any]) -> RuleScope:
    """Infer a RuleScope from a session context dictionary.

    The context dict may contain any subset of the following keys:

    - ``"domain"`` (str): passed through directly.
    - ``"task"`` (str): free-text description; classified into ``task_type``
      and used to infer ``channel`` and ``stakes`` when not explicitly set.
    - ``"prospect"`` (dict): may contain a ``"title"`` key for audience
      classification.
    - ``"channel"`` (str): overrides channel inferred from task.
    - ``"stakes"`` (str): overrides stakes inferred from task.

    Args:
        context: Arbitrary session context produced by the agent runtime.

    Returns:
        A fully-populated (where inferable) :class:`RuleScope`.

    Example:
        >>> build_scope({"task": "draft email to CEO", "domain": "sales"})
        RuleScope(domain='sales', task_type='email_draft', audience='c_suite',
                  channel='email', stakes='normal')
    """
    task: str = context.get("task", "") or ""

    # ── domain ──────────────────────────────────────────────────────────────
    domain: str = str(context.get("domain", "") or "")

    # ── task_type ────────────────────────────────────────────────────────────
    task_type: str = _classify(task, _TASK_TYPE_KEYWORDS)

    # ── audience ─────────────────────────────────────────────────────────────
    prospect_raw = context.get("prospect", {})
    prospect: dict[str, Any] = prospect_raw if isinstance(prospect_raw, dict) else {}
    raw_title: str = str(prospect.get("title", "") or "")

    # Also scan the task text for audience signals (e.g. "email to CEO")
    if not raw_title:
        raw_title = task

    audience: str = (_classify(raw_title, _AUDIENCE_KEYWORDS) or "ic") if raw_title.strip() else ""

    # ── channel ──────────────────────────────────────────────────────────────
    channel_raw = context.get("channel", "")
    channel: str = str(channel_raw) if channel_raw else _classify(task, _CHANNEL_KEYWORDS)

    # ── stakes ───────────────────────────────────────────────────────────────
    stakes_raw = context.get("stakes", "")
    if stakes_raw and str(stakes_raw) in {"low", "normal", "high", "critical"}:
        stakes: str = str(stakes_raw)
    else:
        inferred_stakes = _classify(task, _STAKES_KEYWORDS)
        stakes = inferred_stakes if inferred_stakes else "normal"

    # ── agent_type ────────────────────────────────────────────────────────
    agent_type: str = str(context.get("agent_type", "") or "")

    # ── namespace ────────────────────────────────────────────────────────
    namespace: str = str(context.get("namespace", "") or "")

    return RuleScope(
        domain=domain,
        task_type=task_type,
        audience=audience,
        channel=channel,
        stakes=stakes,
        agent_type=agent_type,
        namespace=namespace,
    )


def scope_matches(rule_scope: RuleScope, query_scope: RuleScope) -> float:
    """Score how well a rule's scope matches a query scope.

    Empty fields in *rule_scope* are wildcards and contribute nothing to the
    denominator — they match anything without penalty. Non-empty fields are
    scored as 1.0 (exact match) or 0.0 (mismatch). The final score is the
    mean of all non-wildcard field scores.

    Special case: if *every* field in rule_scope is an empty string (or
    "normal" for stakes, which is the default), the rule is universal and
    returns 1.0 unconditionally.

    Args:
        rule_scope: The scope attached to a stored rule.
        query_scope: The scope inferred from the current session context.

    Returns:
        Float in [0.0, 1.0]. Higher is better.

    Example:
        >>> scope_matches(RuleScope(domain="sales"), RuleScope(domain="sales",
        ...     task_type="email_draft"))
        1.0
        >>> scope_matches(RuleScope(domain="sales"), RuleScope(domain="eng"))
        0.0
    """
    # Represent the dataclass as ordered (field_name, rule_val, query_val)
    rule_dict = asdict(rule_scope)
    query_dict = asdict(query_scope)
    fields = list(rule_dict.keys())

    # The default value for each field acts as a wildcard — it signals
    # "this rule does not constrain this dimension".  Defaults are:
    #   domain, task_type, audience, channel → "" (empty string)
    #   stakes → "normal"  (the neutral, unconstrained value)
    _defaults = dict(asdict(RuleScope()).items())

    scored: list[float] = []
    for field_name in fields:
        rule_val: str = rule_dict[field_name]
        query_val: str = query_dict[field_name]

        # Wildcard: rule field holds its default value → skip from denominator
        if rule_val == _defaults[field_name]:
            continue

        scored.append(1.0 if rule_val == query_val else 0.0)

    # If every field is a wildcard, the rule is universal — applies everywhere
    if not scored:
        return 1.0

    return sum(scored) / len(scored)


def scope_to_dict(scope: RuleScope) -> dict[str, str]:
    """Serialise a RuleScope to a plain string dictionary.

    Suitable for JSON or SQLite TEXT column storage.

    Args:
        scope: The scope to serialise.

    Returns:
        Dict with string keys and string values.

    Example:
        >>> scope_to_dict(RuleScope(domain="sales", stakes="high"))
        {'domain': 'sales', 'task_type': '', 'audience': '',
         'channel': '', 'stakes': 'high'}
    """
    return {k: str(v) for k, v in asdict(scope).items()}


def scope_from_dict(data: dict[str, str]) -> RuleScope:
    """Deserialise a RuleScope from a plain string dictionary.

    Unknown keys are silently ignored for forward-compatibility. Missing keys
    fall back to the dataclass defaults.

    Args:
        data: Dict previously produced by :func:`scope_to_dict` or loaded
            from JSON/SQLite.

    Returns:
        A reconstructed :class:`RuleScope`.

    Example:
        >>> scope_from_dict({"domain": "sales", "stakes": "high"})
        RuleScope(domain='sales', task_type='', audience='',
                  channel='', stakes='high')
    """
    valid_fields = set(RuleScope.__dataclass_fields__)  # type: ignore[attr-defined]
    # Coerce int fields that were stringified by scope_to_dict
    _INT_FIELDS = {"max_idle_sessions", "created_session"}
    filtered = {}
    for k, v in data.items():
        if k not in valid_fields:
            continue
        if k in _INT_FIELDS:
            try:
                v = int(v)
            except (ValueError, TypeError):
                v = 0
        filtered[k] = v
    return RuleScope(**filtered)
