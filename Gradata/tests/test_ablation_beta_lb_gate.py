"""Tests for ``brain/scripts/ablation_beta_lb_gate.py`` — the Beta LB pilot harness.

Covers:
    1. Dry-run path: without GRADATA_ABLATION_CONFIRM, prints estimate, exits 0,
       makes zero LLM calls (mock client raises on any invocation).
    2. Gate-off vs gate-on graduate different counts on the seeded synthetic brain.
    3. Output JSON has the expected schema (conditions, metrics, per_task).

Never touches the real Anthropic API — the module's ``_make_anthropic_client``
is monkey-patched to return a stub.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Load the harness module directly from brain/scripts/ (outside tests/)
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_DIR = REPO_ROOT / "brain" / "scripts"
SCRIPT_PATH = SCRIPT_DIR / "ablation_beta_lb_gate.py"


@pytest.fixture(scope="module")
def harness():
    """Import ablation_beta_lb_gate with brain/scripts on sys.path for _common."""
    # Ensure _common.py is importable (harness does `from _common import ...`)
    added = False
    if str(SCRIPT_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPT_DIR))
        added = True
    try:
        spec = importlib.util.spec_from_file_location("ablation_beta_lb_gate", SCRIPT_PATH)
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        # Register before exec_module — the @dataclass decorator needs the module
        # in sys.modules to resolve string annotations like ``int | None``.
        sys.modules["ablation_beta_lb_gate"] = mod
        spec.loader.exec_module(mod)
        yield mod
    finally:
        sys.modules.pop("ablation_beta_lb_gate", None)
        if added:
            sys.path.remove(str(SCRIPT_DIR))


# ---------------------------------------------------------------------------
# Stub Anthropic clients — used to prove we don't hit the real API
# ---------------------------------------------------------------------------


class _ForbiddenClient:
    """Any attempt to use this client fails the test — proves dry-run made zero calls."""

    def __getattr__(self, item):  # noqa: D401
        raise AssertionError(f"Dry-run made a forbidden client access: {item}")


class _StubContentBlock:
    def __init__(self, text: str):
        self.text = text


class _StubMessage:
    def __init__(self, text: str):
        self.content = [_StubContentBlock(text)]


class _StubMessages:
    """Fakes messages.create — returns a generation or a judge JSON based on system prompt."""

    def __init__(self):
        self.call_count = 0

    def create(self, *, model, max_tokens, system, messages):  # noqa: D401
        self.call_count += 1
        # Judge system prompt contains "impartial evaluator"
        if "impartial evaluator" in system:
            return _StubMessage('{"output_a": 7, "output_b": 8}')
        return _StubMessage("This is a stub draft reply.")


class _StubClient:
    def __init__(self):
        self.messages = _StubMessages()


# ---------------------------------------------------------------------------
# 1. Dry-run: no CONFIRM env, zero LLM calls
# ---------------------------------------------------------------------------


def test_dry_run_makes_zero_llm_calls(harness, monkeypatch, capsys):
    """Without GRADATA_ABLATION_CONFIRM, the script must exit 0 with a printed
    estimate and NEVER attempt to construct an Anthropic client."""
    monkeypatch.delenv("GRADATA_ABLATION_CONFIRM", raising=False)

    # Poison the client factory — any call becomes a test failure.
    def _forbidden_factory():
        raise AssertionError("Dry-run must not construct an Anthropic client")

    monkeypatch.setattr(harness, "_make_anthropic_client", _forbidden_factory)

    rc = harness.main(["--tasks", "5", "--iterations", "2"])
    assert rc == 0

    captured = capsys.readouterr()
    assert "DRY RUN" in captured.out
    assert "no API calls made" in captured.out
    assert "GRADATA_ABLATION_CONFIRM=1" in captured.out
    # Must print the cost estimate.
    assert "estimated cost" in captured.out


def test_dry_run_cost_estimate_scales_with_inputs(harness):
    """estimate_cost is monotonic in tasks×iterations."""
    small = harness.estimate_cost(n_tasks=5, n_iterations=2)
    big = harness.estimate_cost(n_tasks=10, n_iterations=3)
    assert small["trials"] == 10
    assert big["trials"] == 30
    assert big["estimated_cost_usd"] > small["estimated_cost_usd"]
    assert big["total_input_tokens"] > small["total_input_tokens"]


# ---------------------------------------------------------------------------
# 2. Gate off vs gate on — different graduation counts
# ---------------------------------------------------------------------------


def test_gate_discriminates_on_synthetic_brain(harness):
    """simulate_graduation with the gate ON blocks STRICTLY FEWER lessons
    than with the gate OFF (it's a non-weakening gate). At least one lesson
    must differ so the harness produces a measurable signal."""
    lessons = harness.build_synthetic_brain(seed=42)
    assert len(lessons) == 20, "synthetic brain must have the expected 20 lessons"

    off = harness.simulate_graduation(lessons, gate_on=False)
    on = harness.simulate_graduation(lessons, gate_on=True)

    assert off["total_patterns_considered"] == on["total_patterns_considered"] == 20
    # Gate ON cannot graduate more than OFF — it's a strictly narrower filter.
    assert on["pattern_to_rule_count"] <= off["pattern_to_rule_count"]
    # And must graduate strictly fewer on this deliberately mixed pool,
    # otherwise the synthetic fixture doesn't exercise the gate.
    assert on["pattern_to_rule_count"] < off["pattern_to_rule_count"], (
        "synthetic brain failed to exercise the gate — rebalance weak/strong specs"
    )

    # Per-lesson trace schema.
    for row in off["per_lesson"]:
        assert set(row) >= {
            "label",
            "alpha",
            "beta_param",
            "fire_count",
            "final_state",
            "promoted_to_rule",
        }


def test_gate_restores_env_var(harness):
    """simulate_graduation must leave GRADATA_BETA_LB_GATE unchanged afterwards."""
    prev = os.environ.get("GRADATA_BETA_LB_GATE")
    try:
        os.environ["GRADATA_BETA_LB_GATE"] = "sentinel"
        lessons = harness.build_synthetic_brain(seed=7)
        harness.simulate_graduation(lessons, gate_on=True)
        harness.simulate_graduation(lessons, gate_on=False)
        assert os.environ.get("GRADATA_BETA_LB_GATE") == "sentinel"
    finally:
        if prev is None:
            os.environ.pop("GRADATA_BETA_LB_GATE", None)
        else:
            os.environ["GRADATA_BETA_LB_GATE"] = prev


# ---------------------------------------------------------------------------
# 3. Output JSON schema
# ---------------------------------------------------------------------------


def test_run_pilot_output_schema(harness, monkeypatch):
    """With a stubbed Anthropic client, run_pilot produces a result dict with
    the expected top-level schema."""
    stub = _StubClient()
    lessons = harness.build_synthetic_brain(seed=42)

    result = harness.run_pilot(
        lessons=lessons,
        n_tasks=2,
        n_iterations=1,
        model="stub-model",
        judge_model="stub-judge",
        client_factory=lambda: stub,
        seed=42,
    )

    # Top-level keys.
    assert set(result) >= {
        "generated_at",
        "model",
        "judge_model",
        "n_tasks",
        "n_iterations",
        "conditions",
        "metrics",
        "per_task",
        "per_lesson_off",
        "per_lesson_on",
    }

    # Conditions substructure.
    for cond in ("gate_off", "gate_on"):
        assert cond in result["conditions"]
        assert "graduations" in result["conditions"][cond]
        assert "mean_judge_score" in result["conditions"][cond]

    # Metrics substructure.
    for key in ("graduation_drop_pct", "preference_lift_pct", "usable_judge_scores"):
        assert key in result["metrics"]

    # Per-task schema.
    assert len(result["per_task"]) == 2  # 2 tasks × 1 iter
    for row in result["per_task"]:
        assert set(row) >= {
            "task_index",
            "task",
            "iteration",
            "output_a",
            "output_b",
            "judge_ok",
        }

    # Judge should have succeeded on every trial (stub always returns valid JSON).
    assert result["metrics"]["usable_judge_scores"] == 2

    # Stub must have been called — proves the code path was exercised.
    assert stub.messages.call_count > 0

    # Sanity: result is JSON-serialisable (the CLI writes it).
    json.dumps(result, default=str)


def test_format_summary_renders(harness):
    """format_summary returns a non-empty string with the decision-criteria anchors."""
    fake_result = {
        "model": "x",
        "judge_model": "y",
        "n_tasks": 5,
        "n_iterations": 2,
        "conditions": {
            "gate_off": {"graduations": 15, "mean_judge_score": 7.0},
            "gate_on": {"graduations": 10, "mean_judge_score": 7.5},
        },
        "metrics": {
            "graduation_drop_pct": 0.333,
            "preference_lift_pct": 0.071,
            "usable_judge_scores": 10,
        },
    }
    s = harness.format_summary(fake_result)
    assert "Beta LB Gate Ablation" in s
    assert "gate OFF" in s
    assert "gate ON" in s
    assert "Decision criteria" in s
