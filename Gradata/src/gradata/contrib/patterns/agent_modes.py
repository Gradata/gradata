"""
Agent Modes — Gradata
====================================
Switchable operating modes that control agent autonomy, permissions, and
isolation level.  Five modes from full autonomy (GODMODE) to read-only
(AUDIT).  The current mode is read from the ``GRADATA_MODE`` environment
variable; when unset it defaults to GODMODE for backward compatibility.

Usage::

    from gradata.contrib.patterns.agent_modes import (
        AgentMode, ModeConfig, get_mode, get_current_mode,
        format_mode_prompt, check_permission, auto_select_mode,
    )

    mode = get_current_mode()
    allowed, reason = check_permission(mode, "write")
    if not allowed:
        print(reason)
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from enum import Enum


class AgentMode(Enum):
    """Available operating modes for Gradata agents."""

    GODMODE = "godmode"  # Full autonomy, OODA loop, no permission checks
    PLAN = "plan"  # Propose before executing, wait for approval
    AUDIT = "audit"  # Read-only. Observe and report only.
    CANARY = "canary"  # Build in isolation (worktree/branch), merge only if tests pass
    SAFE = "safe"  # One file at a time, verify after each change


@dataclass
class ModeConfig:
    """Configuration and constraints for a single agent mode."""

    mode: AgentMode
    can_write: bool  # Can create/edit files
    can_execute: bool  # Can run bash commands
    can_spawn: bool  # Can spawn sub-agents
    can_commit: bool  # Can git commit
    requires_approval: bool  # Must get approval before acting
    max_files_per_action: int  # 0 = unlimited
    must_verify_after_edit: bool  # Run py_compile/tests after every change
    isolation: str  # "none", "branch", "worktree"
    description: str


# ---------------------------------------------------------------------------
# Mode registry
# ---------------------------------------------------------------------------

MODE_CONFIGS: dict[AgentMode, ModeConfig] = {
    AgentMode.GODMODE: ModeConfig(
        mode=AgentMode.GODMODE,
        can_write=True,
        can_execute=True,
        can_spawn=True,
        can_commit=True,
        requires_approval=False,
        max_files_per_action=0,
        must_verify_after_edit=False,
        isolation="none",
        description="Full autonomy. OODA loop. Never pause.",
    ),
    AgentMode.PLAN: ModeConfig(
        mode=AgentMode.PLAN,
        can_write=True,
        can_execute=True,
        can_spawn=True,
        can_commit=True,
        requires_approval=True,
        max_files_per_action=0,
        must_verify_after_edit=False,
        isolation="none",
        description="Propose plan, wait for approval before executing.",
    ),
    AgentMode.AUDIT: ModeConfig(
        mode=AgentMode.AUDIT,
        can_write=False,
        can_execute=False,
        can_spawn=False,
        can_commit=False,
        requires_approval=False,
        max_files_per_action=0,
        must_verify_after_edit=False,
        isolation="none",
        description="Read-only. Observe, analyze, report. Cannot modify.",
    ),
    AgentMode.CANARY: ModeConfig(
        mode=AgentMode.CANARY,
        can_write=True,
        can_execute=True,
        can_spawn=True,
        can_commit=True,
        requires_approval=False,
        max_files_per_action=0,
        must_verify_after_edit=True,
        isolation="worktree",
        description="Build in isolation. Merge only if all tests pass.",
    ),
    AgentMode.SAFE: ModeConfig(
        mode=AgentMode.SAFE,
        can_write=True,
        can_execute=True,
        can_spawn=False,
        can_commit=True,
        requires_approval=False,
        max_files_per_action=1,
        must_verify_after_edit=True,
        isolation="branch",
        description="One file at a time. Verify after every change.",
    ),
}

_ACTION_FIELD_MAP: dict[str, str] = {
    "write": "can_write",
    "execute": "can_execute",
    "spawn": "can_spawn",
    "commit": "can_commit",
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_mode(mode_name: str) -> ModeConfig:
    """Get mode config by name.  Defaults to GODMODE for unknown names."""
    try:
        agent_mode = AgentMode(mode_name.lower().strip())
    except ValueError:
        return MODE_CONFIGS[AgentMode.GODMODE]
    return MODE_CONFIGS[agent_mode]


def get_current_mode() -> ModeConfig:
    """Read current mode from ``GRADATA_MODE`` env var (default: GODMODE)."""
    return get_mode(os.environ.get("GRADATA_MODE", "godmode"))


def check_permission(mode: ModeConfig, action: str) -> tuple[bool, str]:
    """Check whether *action* is allowed in *mode*.

    Args:
        mode: The active :class:`ModeConfig`.
        action: One of ``"write"``, ``"execute"``, ``"spawn"``, ``"commit"``.

    Returns:
        ``(allowed, reason)`` — *reason* explains why the action was blocked.
    """
    field = _ACTION_FIELD_MAP.get(action)
    if field is None:
        return False, f"Unknown action '{action}'."
    allowed: bool = getattr(mode, field)
    if allowed:
        return True, ""
    return False, (
        f"Action '{action}' is not permitted in {mode.mode.value} mode. {mode.description}"
    )


def format_mode_prompt(mode: AgentMode) -> str:
    """Generate the mode-specific instruction block for agent prompt injection.

    Returns a multi-line string of rules/constraints derived from the mode's
    configuration that should be injected into the agent's system prompt.
    """
    cfg = MODE_CONFIGS[mode]
    lines: list[str] = [
        f'<agent-mode name="{mode.value}">',
        f"  Description: {cfg.description}",
    ]

    if not cfg.can_write:
        lines.append("  CONSTRAINT: Do NOT create, edit, or delete any files.")
    if not cfg.can_execute:
        lines.append("  CONSTRAINT: Do NOT run shell commands.")
    if not cfg.can_spawn:
        lines.append("  CONSTRAINT: Do NOT spawn sub-agents.")
    if not cfg.can_commit:
        lines.append("  CONSTRAINT: Do NOT make git commits.")
    if cfg.requires_approval:
        lines.append(
            "  CONSTRAINT: Propose your full plan FIRST. Do NOT execute until the user approves."
        )
    if cfg.max_files_per_action > 0:
        lines.append(
            f"  CONSTRAINT: Touch at most {cfg.max_files_per_action} "
            f"file(s) per action, then verify before continuing."
        )
    if cfg.must_verify_after_edit:
        lines.append(
            "  CONSTRAINT: After every file edit, run py_compile or "
            "relevant tests before proceeding."
        )
    if cfg.isolation == "branch":
        lines.append("  CONSTRAINT: Work on a dedicated branch, not main.")
    elif cfg.isolation == "worktree":
        lines.append(
            "  CONSTRAINT: Work in an isolated git worktree. "
            "Merge to main only after all tests pass."
        )

    lines.append("</agent-mode>")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Heuristic auto-selection
# ---------------------------------------------------------------------------

_MODE_KEYWORDS: list[tuple[re.Pattern[str], AgentMode]] = [
    (re.compile(r"\b(review|audit|check|inspect|analyze)\b", re.I), AgentMode.AUDIT),
    (re.compile(r"\b(deploy|push|release|publish|ship)\b", re.I), AgentMode.PLAN),
    (re.compile(r"\b(fix|hotfix|urgent|patch|bugfix)\b", re.I), AgentMode.SAFE),
    (re.compile(r"\b(experiment|try|test|spike|prototype)\b", re.I), AgentMode.CANARY),
]


def auto_select_mode(
    task_description: str,
    context: dict[str, object] | None = None,
) -> AgentMode:
    """Heuristic mode selection based on *task_description* keywords.

    Scans for keywords associated with each mode and returns the first match.
    Falls back to :attr:`AgentMode.GODMODE` when nothing matches.
    """
    for pattern, mode in _MODE_KEYWORDS:
        if pattern.search(task_description):
            return mode
    return AgentMode.GODMODE
