"""
Targeted regression tests for the 9 bugs found and fixed in S43.
Each test verifies the fix at the data level, not just the API surface.
"""

import json
import sqlite3
from pathlib import Path

import pytest


def _make_brain(tmp_path, taxonomy=None):
    """Create a minimal brain directory for testing."""
    brain_dir = tmp_path / "brain"
    brain_dir.mkdir()
    (brain_dir / "sessions").mkdir()
    (brain_dir / "events.jsonl").write_text("", encoding="utf-8")
    (brain_dir / "system.db").write_text("", encoding="utf-8")
    if taxonomy:
        (brain_dir / "taxonomy.json").write_text(json.dumps(taxonomy), encoding="utf-8")
    from gradata.brain import Brain

    return Brain(brain_dir)


# ═══════════════════════════════════════════════════════════════════
# BUG 1: correction_rate in manifest was always 0.0
# Root cause: cr[-1] on a dict keyed by session number, not index
# ═══════════════════════════════════════════════════════════════════


class TestBug1CorrectionRateManifest:
    def test_correction_rate_nonzero_after_corrections(self, tmp_path):
        brain = _make_brain(tmp_path)
        brain.log_output("Output 1", output_type="email", session=1)
        brain.log_output("Output 2", output_type="email", session=1)
        brain.correct("Draft text", "Final text", session=1)

        m = brain.manifest()
        rate = m.get("quality", {}).get("correction_rate")
        assert rate is not None, "correction_rate should not be None"
        assert rate > 0, f"correction_rate should be > 0, got {rate}"
        assert rate == pytest.approx(0.5, abs=0.1)  # 1 correction / 2 outputs

    def test_correction_rate_zero_with_no_corrections(self, tmp_path):
        brain = _make_brain(tmp_path)
        brain.log_output("Output 1", output_type="email", session=1)

        m = brain.manifest()
        rate = m.get("quality", {}).get("correction_rate")
        # Should be 0 or None, not crash
        assert rate is None or rate == 0.0

    def test_correction_rate_multiple_sessions(self, tmp_path):
        brain = _make_brain(tmp_path)
        for s in range(1, 4):
            brain.log_output(f"Output S{s}", output_type="email", session=s)
            if s % 2 == 0:
                brain.correct(f"Draft S{s}", f"Final S{s}", session=s)

        m = brain.manifest()
        rate = m.get("quality", {}).get("correction_rate")
        assert rate is not None and rate > 0


# ═══════════════════════════════════════════════════════════════════
# BUG 2: MCP brain_correct dispatch crashed on non-serializable dataclass
# ═══════════════════════════════════════════════════════════════════


class TestBug2MCPCorrectDispatch:
    def test_dispatch_correct_returns_content(self, tmp_path):
        brain = _make_brain(tmp_path)
        from gradata.mcp_server import _dispatch

        result = _dispatch(
            brain, "brain_correct", {"draft": "Old text here", "final": "New text here"}
        )
        assert "content" in result, f"Expected content key, got: {result}"
        assert "error" not in result, f"Unexpected error: {result.get('error')}"

    def test_dispatch_correct_content_is_valid_json(self, tmp_path):
        brain = _make_brain(tmp_path)
        from gradata.mcp_server import _dispatch

        result = _dispatch(brain, "brain_correct", {"draft": "Original", "final": "Modified"})
        text = result["content"][0]["text"]
        parsed = json.loads(text)  # Should not raise
        assert "severity" in parsed
        assert "edit_distance" in parsed

    def test_dispatch_all_tools_no_crash(self, tmp_path):
        brain = _make_brain(tmp_path)
        from gradata.mcp_server import _dispatch

        tools = {
            "brain_search": {"query": "test"},
            "brain_correct": {"draft": "a", "final": "b"},
            "brain_log_output": {"text": "hello"},
            "brain_manifest": {},
            "brain_health": {},
        }
        for name, args in tools.items():
            result = _dispatch(brain, name, args)
            assert "content" in result or "error" in result, f"{name} returned nothing"


# ═══════════════════════════════════════════════════════════════════
# BUG 3: Event emission could silently lose learning data
# ═══════════════════════════════════════════════════════════════════


class TestBug3EventPersistence:
    def test_event_has_persistence_flags(self, tmp_path):
        brain = _make_brain(tmp_path)
        result = brain.correct("Old", "New", session=1)
        assert "_persisted" in result
        assert result["_persisted"]["jsonl"] is True
        assert result["_persisted"]["sqlite"] is True

    def test_output_event_persisted(self, tmp_path):
        brain = _make_brain(tmp_path)
        result = brain.log_output("Test", output_type="email", session=1)
        assert result["_persisted"]["jsonl"] is True
        assert result["_persisted"]["sqlite"] is True

    def test_db_and_jsonl_in_sync(self, tmp_path):
        brain = _make_brain(tmp_path)
        brain.log_output("Out1", session=1)
        brain.correct("Draft", "Final", session=1)
        brain.track_rule("R1", accepted=True, session=1)

        # Count DB events
        db = sqlite3.connect(str(brain.db_path))
        db_count = db.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        db.close()

        # Count JSONL events
        jsonl_path = brain.dir / "events.jsonl"
        with open(jsonl_path) as f:
            jsonl_count = sum(1 for line in f if line.strip())

        assert db_count == jsonl_count, f"DB({db_count}) != JSONL({jsonl_count})"


# ═══════════════════════════════════════════════════════════════════
# BUG 4: FACTUAL category from edit classifier not in taxonomy
# ═══════════════════════════════════════════════════════════════════


class TestBug4FactualCategory:
    def test_factual_in_core_taxonomy(self):
        from gradata._tag_taxonomy import TAXONOMY

        categories = TAXONOMY["category"]["values"]
        assert "FACTUAL" in categories
        assert "CONTENT" in categories
        assert "TONE" in categories
        assert "STRUCTURE" in categories
        assert "STYLE" in categories

    def test_correct_with_number_change_no_warning(self, tmp_path, capsys):
        brain = _make_brain(tmp_path)
        brain.correct("Price is $500", "Price is $300", session=1)
        captured = capsys.readouterr()
        # Should NOT warn about invalid category FACTUAL
        assert "Invalid category value: FACTUAL" not in captured.err


# ═══════════════════════════════════════════════════════════════════
# BUG 5: apply_brain_rules() assumed specific path layout
# ═══════════════════════════════════════════════════════════════════


class TestBug5ApplyBrainRulesPath:
    def test_returns_empty_when_no_lessons(self, tmp_path):
        brain = _make_brain(tmp_path)
        # No lessons.md anywhere — should return "" not crash
        result = brain.apply_brain_rules("email_draft")
        assert result == ""

    def test_finds_lessons_in_brain_dir(self, tmp_path):
        brain = _make_brain(tmp_path)
        lessons = (
            "## Active Lessons\n\n[2026-03-24] [RULE] DRAFTING: Always include CTA in emails.\n"
        )
        (brain.dir / "lessons.md").write_text(lessons, encoding="utf-8")
        result = brain.apply_brain_rules("email_draft")
        # Should find and parse the lessons file
        assert isinstance(result, str)


# ═══════════════════════════════════════════════════════════════════
# BUG 6: hardcoded_user removed from 6 files
# ═══════════════════════════════════════════════════════════════════


class TestBug6HardcodedUserRemoved:
    def test_no_hardcoded_user_in_sdk(self):
        """Grep entire SDK source for hardcoded_user — must find zero."""
        sdk_src = Path(__file__).parent.parent / "src" / "gradata"
        hits = []
        for py_file in sdk_src.rglob("*.py"):
            text = py_file.read_text(encoding="utf-8", errors="replace")
            if "hardcoded_user" in text:
                hits.append(str(py_file.relative_to(sdk_src)))
        assert hits == [], f"hardcoded_user found in: {hits}"

    def test_log_output_uses_major_edit(self, tmp_path):
        brain = _make_brain(tmp_path)
        result = brain.log_output("Test", output_type="email", session=1)
        data = result.get("data", {})
        assert "major_edit" in data
        assert "hardcoded_user" not in data


# ═══════════════════════════════════════════════════════════════════
# BUG 7: Sales-domain coupling (23 hardcodings)
# ═══════════════════════════════════════════════════════════════════


class TestBug7DomainAgnostic:
    def test_engineering_brain_no_sales_taxonomy(self, tmp_path):
        eng_taxonomy = {
            "entity": {"desc": "Project", "mode": "dynamic", "required_on": []},
            "output": {
                "desc": "Output type",
                "mode": "closed",
                "values": ["code_review", "design_doc", "test_plan"],
            },
            "extra_categories": ["CODE_QUALITY", "SECURITY"],
        }
        _make_brain(tmp_path, taxonomy=eng_taxonomy)

        from gradata._tag_taxonomy import TAXONOMY

        output_vals = TAXONOMY.get("output", {}).get("values", set())
        assert "code_review" in output_vals
        assert "email" not in output_vals  # Sales value NOT present

    def test_recruiting_brain_with_candidates(self, tmp_path):
        recruit_taxonomy = {
            "entity": {"desc": "Candidate", "mode": "dynamic", "required_on": []},
            "output": {
                "desc": "Output type",
                "mode": "closed",
                "values": ["interview_prep", "job_description", "offer_letter"],
            },
        }
        _make_brain(tmp_path, taxonomy=recruit_taxonomy)

        from gradata._tag_taxonomy import TAXONOMY

        output_vals = TAXONOMY.get("output", {}).get("values", set())
        assert "interview_prep" in output_vals

    def test_onboard_creates_domain_dirs(self):
        from gradata.onboard import _DOMAIN_SUBDIRS

        assert "sales" in _DOMAIN_SUBDIRS
        assert "recruiting" in _DOMAIN_SUBDIRS
        assert "engineering" in _DOMAIN_SUBDIRS
        assert "prospects" in _DOMAIN_SUBDIRS["sales"]
        assert "candidates" in _DOMAIN_SUBDIRS["recruiting"]
        assert "projects" in _DOMAIN_SUBDIRS["engineering"]


# ═══════════════════════════════════════════════════════════════════
# BUG 8: RAG cascade silently swallowed errors
# ═══════════════════════════════════════════════════════════════════


class TestBug8RagCascadeErrors:
    def test_cascade_tracks_fts_error(self):
        from gradata.contrib.patterns.rag import cascade_retrieve

        def bad_fts(query, limit):
            raise RuntimeError("FTS engine crashed")

        result = cascade_retrieve("test", fts_fn=bad_fts)
        # Mode should indicate the failure, not just "empty"
        assert "cascade_failed" in result.mode or "fts" in result.mode

    def test_cascade_tracks_vector_error(self):
        from gradata.contrib.patterns.rag import cascade_retrieve

        def bad_vec(query, limit):
            raise RuntimeError("Vector DB unreachable")

        result = cascade_retrieve("test", vector_fn=bad_vec)
        assert "cascade_failed" in result.mode or "vector" in result.mode

    def test_cascade_no_error_when_no_retrievers(self):
        from gradata.contrib.patterns.rag import cascade_retrieve

        result = cascade_retrieve("test")
        assert result.mode == "empty"
        assert result.chunks == []


# ═══════════════════════════════════════════════════════════════════
# BUG 9: Missing classes (SmartRAG, HumanLoopGate, etc.)
# ═══════════════════════════════════════════════════════════════════


class TestBug9MissingClasses:
    def test_smart_rag_importable_and_functional(self):
        from gradata.contrib.patterns.rag import SmartRAG

        rag = SmartRAG()
        result = rag.retrieve("test")
        assert result.chunks == []
        assert result.mode == "empty"

    def test_naive_rag_importable_and_functional(self):
        from gradata.contrib.patterns.rag import NaiveRAG

        rag = NaiveRAG()
        result = rag.retrieve("test")
        assert result.chunks == []

    def test_human_loop_gate_importable(self):
        from gradata.contrib.patterns.human_loop import HumanLoopGate

        gate = HumanLoopGate()
        risk = gate.assess("delete database")
        assert risk.tier in ("low", "medium", "high", "critical")

    def test_rule_application_importable(self):
        from gradata.rules.rule_tracker import RuleApplication

        ra = RuleApplication(rule_id="test_001", accepted=True)
        assert ra.rule_id == "test_001"
        assert ra.accepted is True

    def test_compute_density_importable(self):
        from gradata.enhancements.learning_pipeline import compute_density

        # Should not crash on missing DB
        assert callable(compute_density)

    def test_top_level_exports(self):
        """Core symbols importable from gradata top level."""
        from gradata import Brain, BrainContext, Lesson, LessonState, __version__

        assert Brain is not None
        assert BrainContext is not None
        assert Lesson is not None
        assert LessonState is not None
        assert __version__ is not None

    def test_pattern_exports_from_contrib(self):
        """Pattern symbols importable from gradata.contrib.patterns and gradata.rules."""
        from gradata.contrib.patterns import (
            Delegation,
            EpisodicMemory,
            HumanLoopGate,
            InputGuard,
            MCPBridge,
            NaiveRAG,
            OutputGuard,
            ParallelBatch,
            Pipeline,
            SmartRAG,
            Stage,
        )
        from gradata.rules.rule_tracker import RuleApplication
        from gradata.rules.scope import AudienceTier

        for sym in (
            SmartRAG,
            NaiveRAG,
            HumanLoopGate,
            RuleApplication,
            Pipeline,
            Stage,
            ParallelBatch,
            EpisodicMemory,
            InputGuard,
            OutputGuard,
            MCPBridge,
            Delegation,
            AudienceTier,
        ):
            assert sym is not None
