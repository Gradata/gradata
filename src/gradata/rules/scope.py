"""
Scope Classification — Domain-Agnostic Task Typing
====================================================
Classifies an incoming request into a ``TaskType`` (what the user wants to
accomplish) and an ``AudienceTier`` (who the output is aimed at).

Both dimensions are fully configurable.  Domains ship their own intents by
calling ``register_task_type``; the built-in table covers generic,
engineering, recruiting, and sales workflows so a brain works out-of-the-box
without any domain configuration.

Example::

    from gradata.rules.scope import classify_scope

    task, audience = classify_scope("prepare for the upcoming meeting")
    print(task)      # TaskType.MEETING_PREP
    print(audience)  # AudienceTier.STAKEHOLDER

Backward compatibility guarantee
---------------------------------
All sales intents present before this refactor (email_draft, demo_prep,
prospecting, objection_handling, follow_up, crm_update) are preserved
verbatim as members of ``DEFAULT_TASK_TYPES`` so existing sales brains
continue to classify identically.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

# ---------------------------------------------------------------------------
# Audience Tiers
# ---------------------------------------------------------------------------

class AudienceTier(StrEnum):
    """Who the output is primarily written for.

    Tiers below are intentionally role-agnostic so they apply equally to
    sales, engineering, recruiting, and general-purpose brains.
    """

    # Organizational hierarchy (applicable to any domain)
    C_SUITE = "c_suite"          # CEO, CTO, CPO, Founder, Partner
    VP = "vp"                    # VP-level, Head of …
    DIRECTOR = "director"        # Director, Senior Director
    MANAGER = "manager"          # Manager, Team Lead, Tech Lead
    IC = "ic"                    # Individual contributor (engineer, analyst, etc.)

    # Recruiting / hiring
    CANDIDATE = "candidate"      # Job applicant
    INTERVIEWER = "interviewer"  # Hiring-side participant

    # Broad / cross-functional
    STAKEHOLDER = "stakeholder"  # Sponsor, approver, or any governance role
    END_USER = "end_user"        # Direct consumer of the product or output
    PEER = "peer"                # Same-level colleague or collaborator

    # Fallback
    UNKNOWN = "unknown"          # Could not determine audience


# Keyword sets used by classify_scope to detect audience from the raw query.
_AUDIENCE_KEYWORDS: dict[AudienceTier, list[str]] = {
    AudienceTier.C_SUITE: [
        "ceo", "cto", "cpo", "coo", "cfo", "founder", "co-founder", "owner",
        "president", "partner", "executive", "c-suite", "board",
    ],
    AudienceTier.VP: [
        "vp", "vice president", "head of", "svp", "evp",
    ],
    AudienceTier.DIRECTOR: [
        "director", "senior director",
    ],
    AudienceTier.MANAGER: [
        "manager", "team lead", "tech lead", "engineering manager",
        "product manager", "project manager",
    ],
    AudienceTier.CANDIDATE: [
        "candidate", "applicant", "interviewee", "job seeker",
    ],
    AudienceTier.INTERVIEWER: [
        "interviewer", "hiring manager", "panel",
    ],
    AudienceTier.STAKEHOLDER: [
        "stakeholder", "sponsor", "approver", "client", "customer",
    ],
    AudienceTier.END_USER: [
        "end user", "user", "consumer",
    ],
    AudienceTier.PEER: [
        "peer", "colleague", "teammate", "coworker",
    ],
    AudienceTier.IC: [
        "engineer", "developer", "analyst", "designer", "scientist",
        "specialist", "contributor",
    ],
}


# ---------------------------------------------------------------------------
# Task Types
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TaskType:
    """A named intent with associated keyword signals.

    Attributes:
        name: Machine-readable identifier (snake_case).  Used as the ``intent``
              field in ``RequestClassification``.
        keywords: Substrings that suggest this task type when found in the
                  lowercased request text.  Longer / more-specific strings
                  should appear before shorter ones to avoid false positives.
        domain_hint: Optional free-text label so operators can filter by
                     domain (e.g. "sales", "engineering", "recruiting").
                     Empty string means "generic / cross-domain".
    """

    name: str
    keywords: list[str] = field(default_factory=list)
    domain_hint: str = ""


# ---------------------------------------------------------------------------
# Default task-type table
# ---------------------------------------------------------------------------
# Ordering within each group matters: more-specific entries must come before
# shorter ones whose keywords are substrings of the specific entry's keywords.

DEFAULT_TASK_TYPES: list[TaskType] = [
    # ── Specific "prepare for X" intents — must precede meeting_prep ────────
    # These share the "prepare for" prefix with meeting_prep; they must appear
    # first so that qualifier-specific keywords are checked before the generic
    # meeting-prep fallback.
    TaskType(
        name="interview_prep",
        keywords=[
            "prepare for interview", "prep for interview", "interview prep",
            "practice interview", "mock interview", "interview questions",
            "before the interview",
        ],
        domain_hint="recruiting",
    ),
    TaskType(
        name="demo_prep",
        keywords=[
            "prepare for demo", "prep for demo", "prep the demo",
            "demo prep", "before the demo", "get ready for demo",
        ],
        domain_hint="sales",
    ),

    # ── Generic / cross-domain ──────────────────────────────────────────────
    TaskType(
        name="meeting_prep",
        keywords=[
            "upcoming meeting", "meeting prep", "before the meeting",
            "before the call", "ready for the call", "prepare for the meeting",
            "prep for the meeting",
        ],
        domain_hint="",
    ),
    TaskType(
        name="research",
        keywords=[
            "research", "look up", "find information", "gather info",
            "background on", "learn about", "investigate",
        ],
        domain_hint="",
    ),
    TaskType(
        name="content_creation",
        keywords=[
            "write a post", "create content", "draft article", "blog post",
            "social media", "newsletter", "write content", "create a draft",
        ],
        domain_hint="",
    ),
    TaskType(
        name="report_generation",
        keywords=[
            "generate report", "create report", "weekly report",
            "monthly report", "status report", "write a report",
            "produce report",
        ],
        domain_hint="",
    ),
    TaskType(
        name="data_analysis",
        keywords=[
            "analyze data", "analyse data", "data analysis", "run analysis",
            "look at the data", "crunch", "trends in", "metrics",
            "dashboard", "visualize",
        ],
        domain_hint="",
    ),
    TaskType(
        name="documentation",
        keywords=[
            "write docs", "documentation", "document this", "update readme",
            "api docs", "write up", "document the", "add docstring",
        ],
        domain_hint="",
    ),
    TaskType(
        name="summary",
        keywords=[
            "summarize", "tldr", "tl;dr", "give me the highlights",
            "key points", "brief overview",
        ],
        domain_hint="",
    ),
    TaskType(
        name="planning",
        keywords=[
            "plan", "roadmap", "strategy", "prioritize", "schedule",
            "sprint", "backlog",
        ],
        domain_hint="",
    ),

    # ── Engineering / developer ─────────────────────────────────────────────
    TaskType(
        name="code_review",
        keywords=[
            "code review", "review this pr", "review the pr",
            "review this pull request", "review pull request",
            "look at this code", "check my code", "review code",
        ],
        domain_hint="engineering",
    ),
    TaskType(
        name="debugging",
        keywords=[
            "debug", "fix this bug", "error", "traceback", "exception",
            "not working", "broken", "failing test", "stack trace",
        ],
        domain_hint="engineering",
    ),
    TaskType(
        name="design_review",
        keywords=[
            "design review", "review the design", "architecture review",
            "review this design", "system design", "erd", "schema review",
        ],
        domain_hint="engineering",
    ),
    TaskType(
        name="refactoring",
        keywords=[
            "refactor", "clean up", "clean this up", "improve readability",
            "simplify", "restructure",
        ],
        domain_hint="engineering",
    ),

    # ── Recruiting / talent ─────────────────────────────────────────────────
    # Note: interview_prep is defined earlier (before meeting_prep) to ensure
    # "prepare for interview" is matched before the generic "prepare for" group.
    TaskType(
        name="candidate_search",
        keywords=[
            "find candidates", "search for candidates", "source candidates",
            "research candidates", "look for talent", "talent search",
        ],
        domain_hint="recruiting",
    ),
    TaskType(
        name="job_description",
        keywords=[
            "job description", "write jd", "write a jd", "job posting",
            "job req", "job requisition",
        ],
        domain_hint="recruiting",
    ),

    # ── Sales (preserved for backward compatibility) ────────────────────────
    # Note: demo_prep is defined earlier (before meeting_prep) to ensure
    # "prepare for demo" is matched before the generic meeting-prep group.
    TaskType(
        name="email_draft",
        keywords=[
            "draft email", "write email", "compose email",
            "draft a message", "write outreach",
        ],
        domain_hint="sales",
    ),
    TaskType(
        name="research",
        keywords=[
            "find entities", "find items", "entity list",
            "build a list", "identify targets",
        ],
        domain_hint="",
    ),
    TaskType(
        name="resistance_handling",
        keywords=[
            "objection", "push back", "they said no", "handle objection",
            "overcome", "rebuttal",
        ],
        domain_hint="",
    ),
    TaskType(
        name="follow_up",
        keywords=[
            "follow up", "check in", "touch base", "follow-up email",
            "circle back",
        ],
        domain_hint="sales",
    ),
    TaskType(
        name="system_update",
        keywords=[
            "update crm", "log a note", "crm note", "update system",
            "update records", "deal note",
        ],
        domain_hint="",
    ),
]


# ---------------------------------------------------------------------------
# Runtime-configurable registry
# ---------------------------------------------------------------------------

# Mutable copy: domains append to this list at process startup.
_REGISTERED_TASK_TYPES: list[TaskType] = list(DEFAULT_TASK_TYPES)


def register_task_type(
    name: str,
    keywords: list[str],
    domain_hint: str = "",
    *,
    prepend: bool = False,
) -> None:
    """Register a custom task type so the classifier recognises it.

    Domain-specific brains call this once at startup to extend the default
    keyword table without touching library code.

    Args:
        name: Snake-case identifier for the intent (e.g. ``"policy_review"``).
            If a task type with this name already exists it is replaced.
        keywords: List of lowercase substrings that signal this intent.
            Order within the list is preserved; earlier entries match first.
        domain_hint: Optional label for filtering (e.g. ``"legal"``).
        prepend: When ``True`` the new entry is inserted at position 0 so it
            takes precedence over any existing entry with overlapping keywords.

    Example::

        from gradata.rules.scope import register_task_type

        register_task_type(
            name="policy_review",
            keywords=["review policy", "compliance check", "audit policy"],
            domain_hint="legal",
        )
    """
    # Remove any existing entry with the same name to avoid duplicates.
    global _REGISTERED_TASK_TYPES
    _REGISTERED_TASK_TYPES = [t for t in _REGISTERED_TASK_TYPES if t.name != name]

    entry = TaskType(name=name, keywords=keywords, domain_hint=domain_hint)
    if prepend:
        _REGISTERED_TASK_TYPES.insert(0, entry)
    else:
        _REGISTERED_TASK_TYPES.append(entry)



# ---------------------------------------------------------------------------
# Classification helpers
# ---------------------------------------------------------------------------

def _detect_task_type(query_lower: str) -> str:
    """Return the name of the first matching TaskType, or ``"general"``."""
    for task_type in _REGISTERED_TASK_TYPES:
        for keyword in task_type.keywords:
            if keyword in query_lower:
                return task_type.name
    return "general"


def _detect_audience(query_lower: str) -> AudienceTier:
    """Return the most specific AudienceTier found in the query."""
    for tier, keywords in _AUDIENCE_KEYWORDS.items():
        for kw in keywords:
            if kw in query_lower:
                return tier
    return AudienceTier.UNKNOWN


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def classify_scope(query: str) -> tuple[str, AudienceTier]:
    """Classify a raw query into a task type name and an audience tier.

    Args:
        query: The raw user request in any case.

    Returns:
        A ``(task_type_name, audience_tier)`` tuple.  ``task_type_name`` is
        ``"general"`` when no registered keyword matches.  ``audience_tier``
        is ``AudienceTier.UNKNOWN`` when no audience signal is detected.

    Example::

        task, audience = classify_scope("prepare for the upcoming meeting")
        # task == "meeting_prep"
        # audience == AudienceTier.STAKEHOLDER  (or UNKNOWN if no role keyword)
    """
    lower = query.lower()
    task_name = _detect_task_type(lower)
    audience = _detect_audience(lower)
    return task_name, audience