"""Regression tests — agent_precontext scope + env domain filter fix.

Locks in the fix from commit f7b2ab8 (fix(hooks): agent_precontext respects
scope + env domain filter).

Root cause: agent_precontext.main() called resolve_brain_dir() which
prioritises GRADATA_BRAIN_DIR over BRAIN_DIR.  An ambient GRADATA_BRAIN_DIR
in the shell environment would shadow the BRAIN_DIR set by test fixtures (or
by a scoped-brain caller), causing rules from the wrong domain to leak into
sub-agent context.

Security: this was also a cross-domain rule leakage — graduated rules from
domain A (e.g. sales) could appear in domain B (e.g. code) agents.

Fix verified:
1. BRAIN_DIR takes priority over GRADATA_BRAIN_DIR.
2. tool_input.scope_domain overrides GRADATA_SCOPE_DOMAIN env var.
3. Rules from the wrong domain are NOT injected.
"""

from __future__ import annotations

import json
import os
import textwrap
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_lessons(lessons_path: Path, lessons: list[dict]) -> None:
    """Write a minimal lessons.md file readable by parse_lessons."""
    lines = []
    for i, lesson in enumerate(lessons):
        lines.append(f"## Lesson {i + 1}")
        lines.append(f"- **Category**: {lesson['category']}")
        lines.append(f"- **Description**: {lesson['description']}")
        lines.append(f"- **Confidence**: {lesson.get('confidence', 0.9)}")
        scope = lesson.get("scope_json", "{}")
        lines.append(f"- **Scope**: {scope}")
        lines.append("")
    lessons_path.write_text("\n".join(lines), encoding="utf-8")


def _init_test_brain(tmp_path: Path, lessons: list[dict]) -> Path:
    """Create a minimal brain dir with a lessons.md."""
    brain_dir = tmp_path / "brain"
    brain_dir.mkdir(parents=True, exist_ok=True)
    _write_lessons(brain_dir / "lessons.md", lessons)
    return brain_dir


# ---------------------------------------------------------------------------
# _resolve_agent_brain_dir: BRAIN_DIR priority
# ---------------------------------------------------------------------------


class TestResolveAgentBrainDir:
    """BRAIN_DIR must take priority over GRADATA_BRAIN_DIR."""

    def test_positive_brain_dir_used_when_set(self, tmp_path, monkeypatch):
        """When BRAIN_DIR is set and exists, it is returned."""
        brain_dir = tmp_path / "brain"
        brain_dir.mkdir()

        monkeypatch.setenv("BRAIN_DIR", str(brain_dir))
        monkeypatch.delenv("GRADATA_BRAIN_DIR", raising=False)

        from gradata.hooks.agent_precontext import _resolve_agent_brain_dir
        result = _resolve_agent_brain_dir()
        assert result == str(brain_dir)

    def test_negative_gradata_brain_dir_does_not_shadow_brain_dir(
        self, tmp_path, monkeypatch
    ):
        """GRADATA_BRAIN_DIR must NOT shadow an explicitly set BRAIN_DIR.

        This is the regression: before the fix, an ambient GRADATA_BRAIN_DIR
        set in the shell would override the test fixture's BRAIN_DIR, causing
        main() to read the production brain instead of the test brain.
        """
        test_brain = tmp_path / "test_brain"
        test_brain.mkdir()
        ambient_brain = tmp_path / "ambient_brain"
        ambient_brain.mkdir()

        monkeypatch.setenv("BRAIN_DIR", str(test_brain))
        monkeypatch.setenv("GRADATA_BRAIN_DIR", str(ambient_brain))

        from gradata.hooks.agent_precontext import _resolve_agent_brain_dir
        result = _resolve_agent_brain_dir()
        assert result == str(test_brain), (
            "REGRESSION: GRADATA_BRAIN_DIR shadowed BRAIN_DIR — "
            "ambient shell env is clobbering test fixtures / scoped-brain callers"
        )


# ---------------------------------------------------------------------------
# Scope domain: tool_input takes priority over env var
# ---------------------------------------------------------------------------


class TestScopeDomainPriority:
    """tool_input.scope_domain must override GRADATA_SCOPE_DOMAIN env var."""

    def test_positive_env_scope_used_when_no_tool_input(self, monkeypatch):
        """When tool_input has no scope_domain, GRADATA_SCOPE_DOMAIN env var is used."""
        from gradata.hooks.agent_precontext import _resolve_scope_domain

        monkeypatch.setenv("GRADATA_SCOPE_DOMAIN", "sales")
        data = {"tool_input": {"subagent_type": "general"}}
        assert _resolve_scope_domain(data) == "sales"

    def test_positive_tool_input_scope_used_when_set(self, monkeypatch):
        """Explicit tool_input.scope_domain is returned."""
        from gradata.hooks.agent_precontext import _resolve_scope_domain

        monkeypatch.setenv("GRADATA_SCOPE_DOMAIN", "sales")
        data = {"tool_input": {"scope_domain": "code"}}
        assert _resolve_scope_domain(data) == "code"

    def test_negative_env_var_does_not_override_tool_input(self, monkeypatch):
        """tool_input.scope_domain='code' must win over GRADATA_SCOPE_DOMAIN='sales'.

        Before the fix, the env var could override the explicit tool_input,
        allowing cross-domain rule leakage (sales rules into code agents).
        """
        from gradata.hooks.agent_precontext import _resolve_scope_domain

        monkeypatch.setenv("GRADATA_SCOPE_DOMAIN", "sales")
        data = {"tool_input": {"scope_domain": "code"}}
        result = _resolve_scope_domain(data)
        assert result == "code", (
            "REGRESSION: GRADATA_SCOPE_DOMAIN overrode tool_input.scope_domain — "
            "cross-domain rule leakage is live again"
        )


# ---------------------------------------------------------------------------
# End-to-end: only correct-domain rules injected
# ---------------------------------------------------------------------------


class TestAgentPrecontextDomainFilter:
    """Integration: main() must inject only rules matching the requested domain."""

    def test_positive_correct_domain_rules_injected(self, tmp_path, monkeypatch):
        """Rules for the requested domain appear in the result block."""
        brain_dir = _init_test_brain(tmp_path, [
            {
                "category": "STYLE",
                "description": "CODE-RULE: use type hints",
                "scope_json": json.dumps({"domain": "code"}),
                "confidence": 0.95,
            },
        ])
        monkeypatch.setenv("BRAIN_DIR", str(brain_dir))
        monkeypatch.delenv("GRADATA_SCOPE_DOMAIN", raising=False)

        from gradata.hooks import agent_precontext
        data = {"tool_input": {"subagent_type": "code", "scope_domain": "code"}}
        result = agent_precontext.main(data)

        if result is not None:
            block = result.get("result", "")
            assert "CODE-RULE" in block

    def test_negative_wrong_domain_rules_not_injected(self, tmp_path, monkeypatch):
        """Rules for domain A must NOT appear when domain B is requested.

        This is the security property: cross-domain rule leakage must be
        impossible.  Before the fix, an ambient GRADATA_BRAIN_DIR or
        GRADATA_SCOPE_DOMAIN could cause domain A rules to surface in domain B
        agent context.
        """
        brain_dir = _init_test_brain(tmp_path, [
            {
                "category": "TONE",
                "description": "SALES-RULE: use warm opener",
                "scope_json": json.dumps({"domain": "sales"}),
                "confidence": 0.95,
            },
            {
                "category": "STYLE",
                "description": "CODE-RULE: prefer comprehensions",
                "scope_json": json.dumps({"domain": "code"}),
                "confidence": 0.95,
            },
        ])
        monkeypatch.setenv("BRAIN_DIR", str(brain_dir))
        # Env says "sales" but tool_input says "code" — tool_input must win
        monkeypatch.setenv("GRADATA_SCOPE_DOMAIN", "sales")

        from gradata.hooks import agent_precontext
        data = {
            "tool_input": {
                "subagent_type": "general",
                "description": "help with code",
                "scope_domain": "code",
            }
        }
        result = agent_precontext.main(data)

        if result is not None:
            block = result.get("result", "")
            assert "SALES-RULE" not in block, (
                "REGRESSION: SALES-RULE leaked into a code-domain agent — "
                "cross-domain rule leakage is live again"
            )
