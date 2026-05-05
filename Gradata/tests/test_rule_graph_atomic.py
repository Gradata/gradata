"""Rule graph atomic persistence tests."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import contextlib

from gradata.rules.rule_graph import RuleGraph


def test_rule_graph_save_preserves_prior_state_when_replace_fails() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "rule_graph.json"

        graph = RuleGraph(path)
        graph.add_conflict("A", "B")
        graph.save()

        updated = RuleGraph(path)
        updated.add_conflict("A", "C")

        with patch("gradata._atomic.os.replace", side_effect=OSError("replace failed")):
            with contextlib.suppress(OSError):
                updated.save()

        loaded = RuleGraph(path)
        assert loaded.has_conflict("A", "B")
        assert not loaded.has_conflict("A", "C")
