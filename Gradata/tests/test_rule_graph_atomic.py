"""Rule graph atomic persistence tests."""

from __future__ import annotations

import tempfile
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

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
            try:
                updated.save()
            except OSError:
                pass

        loaded = RuleGraph(path)
        assert loaded.has_conflict("A", "B")
        assert not loaded.has_conflict("A", "C")
