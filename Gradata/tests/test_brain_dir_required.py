"""BRAIN_DIR required behavior tests."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gradata._doctor import _check_brain_dir
from gradata.exceptions import BrainNotConfiguredError
from gradata.hooks import implicit_feedback
from gradata.hooks._base import run_hook
from gradata.hooks.implicit_feedback import main


def test_implicit_feedback_raises_without_brain_dir() -> None:
    with patch.object(implicit_feedback, "resolve_brain_dir", return_value=None):
        try:
            main({"prompt": "No, don't do it that way"})
        except BrainNotConfiguredError:
            return
    raise AssertionError("expected BrainNotConfiguredError")


def test_doctor_reports_missing_brain_dir() -> None:
    with patch.dict("os.environ", {}, clear=True):
        check = _check_brain_dir()
    assert check["name"] == "brain_dir"
    assert check["status"] == "fail"
    assert "BrainNotConfiguredError" in check["detail"]


def test_hook_runner_does_not_suppress_brain_not_configured() -> None:
    with (
        patch.dict("os.environ", {"GRADATA_HOOK_PROFILE": "strict"}),
        patch.object(implicit_feedback, "resolve_brain_dir", return_value=None),
    ):
        try:
            run_hook(
                main,
                implicit_feedback.HOOK_META,
                raw_input='{"prompt": "No, don\\u0027t do that"}',
            )
        except BrainNotConfiguredError:
            return
    raise AssertionError("expected BrainNotConfiguredError")
