"""Tests for Meta-Harness A RULE_FAILURE matcher in capture_learning.py.

capture_learning.py lives in .claude/hooks/reflect/scripts/ and isn't part of
the src tree, so we load it via importlib to test the matcher in isolation.
The matcher reads <brain>/.last_injection.json and shells out to events.py
via subprocess.run — we patch both to avoid touching real infrastructure.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

HOOK_PATH = (
    Path(__file__).resolve().parents[4]
    / ".claude"
    / "hooks"
    / "reflect"
    / "scripts"
    / "capture_learning.py"
)
if not HOOK_PATH.is_file():
    pytest.skip(
        f"capture_learning.py not found at {HOOK_PATH} — "
        "tests assume worktree layout under Sprites Work/.claude/",
        allow_module_level=True,
    )


@pytest.fixture()
def capture_module(tmp_path, monkeypatch):
    """Load capture_learning.py with BRAIN_DIR pointing at tmp_path."""
    # lib/ next to the hook holds reflect_utils imported at module level.
    monkeypatch.syspath_prepend(str(HOOK_PATH.parent))
    monkeypatch.setenv("BRAIN_DIR", str(tmp_path))
    # Force a fresh load so BRAIN_DIR is re-read.
    sys.modules.pop("capture_learning", None)
    spec = importlib.util.spec_from_file_location("capture_learning", HOOK_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    # Sanity — constant picked up the env var.
    assert mod.BRAIN_DIR == str(tmp_path)
    return mod


def _write_manifest(brain_dir: Path, anchors: dict) -> None:
    (brain_dir / ".last_injection.json").write_text(
        json.dumps({"anchors": anchors}), encoding="utf-8"
    )


def test_tokens_for_match_strips_stopwords_and_short(capture_module):
    toks = capture_module._tokens_for_match(
        "User corrected: don't attribute quotes prospects didn't say"
    )
    # "user", "corrected", "dont", "this" style stopwords gone; len<4 gone.
    assert "attribute" in toks
    assert "quotes" in toks
    assert "prospects" in toks
    assert "user" not in toks          # stopword
    assert "corrected" not in toks     # stopword
    assert "say" not in toks           # len < 4


def test_emit_rule_failure_matches_hits_relevant_rule(capture_module, tmp_path):
    _write_manifest(tmp_path, {
        "a1f9": {
            "full_id": "a1f92b3c4d5e",
            "category": "LEADS",
            "description": "Don't attribute quotes prospects didn't say",
            "state": "RULE",
            "cluster_category": "LEADS",
        },
        "b2c3": {
            "full_id": "b2c31a2b3c4d",
            "category": "DEMO_PREP",
            "description": "Always trigger feedback_post_demo_workflow automatically",
            "state": "RULE",
            "cluster_category": None,
        },
    })

    calls = []

    def fake_run(args, **kwargs):
        calls.append(args)

        class _Result:
            returncode = 0
            stdout = ""
            stderr = ""

        return _Result()

    with patch("subprocess.run", side_effect=fake_run):
        capture_module.emit_rule_failure_matches(
            "you attributed quotes the prospects never said — verify transcript"
        )

    # Should have emitted RULE_FAILURE for the LEADS anchor only.
    rule_failure_calls = [c for c in calls if "RULE_FAILURE" in c]
    assert len(rule_failure_calls) == 1
    payload = rule_failure_calls[0]
    # events.py CLI shape: [py, events.py, "emit", "RULE_FAILURE", source, data, tags]
    data = json.loads(payload[5])
    assert data["anchor"] == "a1f9"
    assert data["full_id"] == "a1f92b3c4d5e"
    assert data["category"] == "LEADS"
    assert data["cluster_category"] == "LEADS"
    # Exact token matches expected: "quotes" + "prospects" both appear on
    # both sides of the match. (attribute/attributed differ by suffix, so
    # they don't unify without stemming.)
    assert "quotes" in data["matched_tokens"]
    assert "prospects" in data["matched_tokens"]
    assert data["jaccard"] >= 0.15


def test_emit_rule_failure_matches_noop_without_manifest(capture_module):
    """No manifest file → silent no-op, no subprocess calls."""
    calls = []

    def fake_run(args, **kwargs):
        calls.append(args)

    with patch("subprocess.run", side_effect=fake_run):
        capture_module.emit_rule_failure_matches("anything goes here")

    assert calls == []


def test_emit_rule_failure_matches_short_correction_skipped(capture_module, tmp_path):
    """Corrections with < 2 significant tokens are not attributable."""
    _write_manifest(tmp_path, {
        "a1f9": {
            "full_id": "a1f92b3c4d5e",
            "category": "LEADS",
            "description": "Don't attribute quotes prospects didn't say",
            "state": "RULE",
            "cluster_category": "LEADS",
        },
    })
    calls = []

    def fake_run(args, **kwargs):
        calls.append(args)

    with patch("subprocess.run", side_effect=fake_run):
        # Only one significant token ("quotes") after stopword+len filter.
        capture_module.emit_rule_failure_matches("no quotes")

    assert calls == []


def test_emit_rule_failure_matches_low_jaccard_skipped(capture_module, tmp_path):
    """Correction sharing only one-off tokens (below jaccard threshold) not emitted."""
    _write_manifest(tmp_path, {
        "a1f9": {
            "full_id": "a1f92b3c4d5e",
            "category": "LEADS",
            "description": "Don't attribute quotes prospects didn't say — verify transcript",
            "state": "RULE",
            "cluster_category": None,
        },
    })
    calls = []

    def fake_run(args, **kwargs):
        calls.append(args)

    with patch("subprocess.run", side_effect=fake_run):
        # Shares only "quotes" (1 token) — needs >= 2.
        capture_module.emit_rule_failure_matches(
            "please fix these compiler warnings about unused quotes tonight carefully"
        )

    assert calls == []
