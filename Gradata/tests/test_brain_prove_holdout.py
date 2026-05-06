"""Tests for holdout validation in brain.prove()."""

from __future__ import annotations

import importlib
import os
from pathlib import Path

import gradata._paths as _paths
from gradata._core import brain_prove_holdout
from gradata.brain import Brain


def _init_brain(tmp_path: Path) -> Brain:
    brain_dir = tmp_path / "brain"
    os.environ["BRAIN_DIR"] = str(brain_dir)
    importlib.reload(_paths)
    return Brain.init(brain_dir, name="TestBrain", domain="Testing", interactive=False)


def _brain_with_correction_counts(tmp_path: Path, counts: list[int]) -> Brain:
    brain = _init_brain(tmp_path)
    for session, count in enumerate(counts, start=1):
        for _ in range(count):
            brain.emit(
                "CORRECTION",
                "pytest",
                {"category": "DRAFTING", "severity": "minor"},
                ["category:DRAFTING"],
                session=session,
            )
    return brain


def test_holdout_insufficient_data_with_five_sessions(tmp_path):
    brain = _brain_with_correction_counts(tmp_path, [3, 3, 3, 3, 3])

    result = brain_prove_holdout(brain)

    assert result["method"] == "holdout_welch_ttest"
    assert result["confidence_level"] == "insufficient"
    assert result["proven"] is False
    assert result["test_window"]["n"] < 2


def test_holdout_clear_improvement_is_proven(tmp_path):
    brain = _brain_with_correction_counts(tmp_path, [9, 8, 10, 9, 8, 9, 10, 1, 1, 2])

    result = brain_prove_holdout(brain)

    assert result["proven"] is True
    assert result["p_value"] < 0.05
    assert result["lift_pct"] >= 10
    assert result["confidence_level"] in {"strong", "moderate"}


def test_holdout_no_improvement_is_not_proven(tmp_path):
    brain = _brain_with_correction_counts(tmp_path, [4, 4, 4, 4, 4, 4, 4, 4, 4, 4])

    result = brain_prove_holdout(brain)

    assert result["proven"] is False
    assert result["confidence_level"] == "insufficient"
    assert result["lift_pct"] == 0


def test_holdout_increasing_corrections_is_not_proven(tmp_path):
    brain = _brain_with_correction_counts(tmp_path, [1, 1, 2, 1, 2, 8, 9, 8, 9, 10])

    result = brain_prove_holdout(brain)

    assert result["proven"] is False
    assert result["test_window"]["mean"] > result["train_window"]["mean"]
    assert result["lift_pct"] < 0


def test_brain_prove_uses_holdout_for_big_brain(tmp_path):
    brain = _brain_with_correction_counts(tmp_path, [9, 8, 10, 9, 8, 9, 10, 1, 1, 2])

    result = brain.prove()

    assert result["method"] == "holdout_welch_ttest"


def test_brain_prove_uses_legacy_for_cold_start(tmp_path):
    brain = _brain_with_correction_counts(tmp_path, [3, 2, 2, 1])

    result = brain.prove()

    assert result["method"] == "in_sample_mann_kendall_legacy"


def test_holdout_p_value_is_deterministic(tmp_path):
    counts = [9, 8, 10, 9, 8, 9, 10, 1, 1, 2]
    brain_a = _brain_with_correction_counts(tmp_path / "a", counts)
    brain_b = _brain_with_correction_counts(tmp_path / "b", counts)

    result_a = brain_prove_holdout(brain_a)
    result_b = brain_prove_holdout(brain_b)

    assert result_a["p_value"] == result_b["p_value"]
