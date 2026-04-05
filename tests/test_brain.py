"""
Integration tests for the Gradata.

Each test creates an isolated brain in a temp directory to verify that the SDK
works correctly for any new user — not just the developer's environment.

Run: pytest sdk/tests/test_brain.py -v
"""

import json
import os
import sqlite3
import zipfile
from pathlib import Path

import pytest

from gradata import Brain


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _init_brain(tmp_path: Path, name: str = "TestBrain", domain: str = "Testing") -> Brain:
    """Create a fresh brain in the given tmp directory.

    After init, force-reload SDK modules that cache path variables at import
    time so they pick up the new brain directory.
    """
    brain_dir = tmp_path / "brain"
    os.environ["BRAIN_DIR"] = str(brain_dir)
    brain = Brain.init(
        brain_dir,
        name=name,
        domain=domain,
        embedding="local",
        interactive=False,
    )
    # SDK modules import path variables at module level (e.g.
    # ``from gradata._paths import DB_PATH``).  Brain.__init__ calls
    # set_brain_dir() which updates _paths globals, but any module that
    # already imported those names holds stale references.  Force the
    # dependent modules to re-read the current values.
    import gradata._paths as _p
    import gradata._events as _ev
    import gradata._brain_manifest as _bm
    _ev.BRAIN_DIR = _p.BRAIN_DIR
    _ev.EVENTS_JSONL = _p.EVENTS_JSONL
    _ev.DB_PATH = _p.DB_PATH
    _bm.BRAIN_DIR = _p.BRAIN_DIR
    _bm.DB_PATH = _p.DB_PATH
    _bm.EVENTS_JSONL = _p.EVENTS_JSONL
    _bm.WORKING_DIR = _p.WORKING_DIR
    _bm.MANIFEST_PATH = _p.BRAIN_DIR / "brain.manifest.json"
    # Export module also caches paths and derived vars at module level
    import gradata._export_brain as _ex
    _ex.BRAIN_DIR = _p.BRAIN_DIR
    _ex.WORKING_DIR = _p.WORKING_DIR
    _ex.PROSPECTS_DIR = _p.PROSPECTS_DIR
    _ex.SESSIONS_DIR = _p.SESSIONS_DIR
    _ex.VERSION_FILE = _p.VERSION_FILE
    _ex.PATTERNS_FILE = _p.PATTERNS_FILE
    _ex.CARL_DIR = _p.CARL_DIR
    _ex.GATES_DIR = _p.GATES_DIR
    _ex.EXPORTS_DIR = _p.BRAIN_DIR / "exports"
    _ex.VAULT_DIR = _p.BRAIN_DIR / "vault"
    _ex.LESSONS_ACTIVE = _p.WORKING_DIR / ".claude" / "lessons.md"
    _ex.LESSONS_ARCHIVE = _p.WORKING_DIR / ".claude" / "lessons-archive.md"
    _ex.QUALITY_RUBRICS = _p.WORKING_DIR / ".claude" / "quality-rubrics.md"
    _ex.DOMAIN_CONFIG = _p.WORKING_DIR / "domain" / "DOMAIN.md"
    _ex.DOMAIN_SOUL = _p.WORKING_DIR / "domain" / "soul.md"
    _ex.CARL_LOOP = _p.CARL_DIR / "loop"
    _ex.CARL_GLOBAL = _p.CARL_DIR / "global"
    # Query module caches DB_PATH / BRAIN_DIR
    import gradata._query as _q
    _q.DB_PATH = _p.DB_PATH
    _q.BRAIN_DIR = _p.BRAIN_DIR
    # ChromaDB removed S66 — no CHROMA_DIR needed in _query
    # Tag taxonomy caches PROSPECTS_DIR
    import gradata._tag_taxonomy as _tt
    _tt.PROSPECTS_DIR = _p.PROSPECTS_DIR
    return brain


# ---------------------------------------------------------------------------
# 1. test_init_creates_brain
# ---------------------------------------------------------------------------

class TestInit:
    def test_init_creates_brain(self, tmp_path):
        """Brain.init() creates a brain directory with all expected structure."""
        brain = _init_brain(tmp_path)

        # Required subdirectories
        for subdir in ("prospects", "sessions", "vault"):
            assert (brain.dir / subdir).is_dir(), f"Missing subdirectory: {subdir}"

        # Required files
        assert brain.db_path.exists(), "system.db not created"
        assert brain.manifest_path.exists(), "brain.manifest.json not created"

        # Manifest is valid JSON with required keys
        manifest = json.loads(brain.manifest_path.read_text(encoding="utf-8"))
        assert manifest["schema_version"] == "1.0.0"
        assert "metadata" in manifest
        assert manifest["metadata"]["brain_name"] == "TestBrain"
        assert manifest["metadata"]["domain"] == "Testing"

        # DB has events table
        conn = sqlite3.connect(str(brain.db_path))
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()]
        conn.close()
        assert "events" in tables, f"events table missing. Tables: {tables}"

    def test_init_duplicate_raises(self, tmp_path):
        """Attempting to init a brain where one already exists raises FileExistsError."""
        _init_brain(tmp_path)
        brain_dir = tmp_path / "brain"
        with pytest.raises(FileExistsError):
            Brain.init(brain_dir, name="Dupe", interactive=False)


# ---------------------------------------------------------------------------
# 2. test_emit_event
# ---------------------------------------------------------------------------

class TestEmitEvent:
    def test_emit_event(self, tmp_path):
        """Emitting an event writes to BOTH events.jsonl and system.db."""
        brain = _init_brain(tmp_path)

        result = brain.emit(
            "TEST_EVENT", "pytest",
            data={"detail": "hello world"},
            tags=["session:0"],
            session=0,
        )

        # Return value has expected shape
        assert result["type"] == "TEST_EVENT"
        assert result["source"] == "pytest"
        assert "ts" in result

        # Verify JSONL
        jsonl_path = brain.dir / "events.jsonl"
        assert jsonl_path.exists(), "events.jsonl not created"
        lines = jsonl_path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) >= 1
        event_jsonl = json.loads(lines[-1])
        assert event_jsonl["type"] == "TEST_EVENT"
        assert event_jsonl["data"]["detail"] == "hello world"

        # Verify SQLite
        conn = sqlite3.connect(str(brain.db_path))
        row = conn.execute(
            "SELECT type, source, data_json FROM events WHERE type = 'TEST_EVENT'"
        ).fetchone()
        conn.close()
        assert row is not None, "Event not found in system.db"
        assert row[0] == "TEST_EVENT"
        assert row[1] == "pytest"
        data = json.loads(row[2])
        assert data["detail"] == "hello world"


# ---------------------------------------------------------------------------
# 3. test_emit_enriches_tags
# ---------------------------------------------------------------------------

class TestTagEnrichment:
    def test_emit_enriches_tags(self, tmp_path):
        """DELTA_TAG events auto-enrich prospect and channel tags in BOTH stores."""
        brain = _init_brain(tmp_path)

        result = brain.emit(
            "DELTA_TAG", "pytest",
            data={
                "prospect": "Jane Doe",
                "activity_type": "email_sent",
            },
            tags=[],
            session=1,
        )

        # The enriched tags should contain prospect and channel
        tags = result.get("tags", [])
        tag_prefixes = {t.split(":")[0] for t in tags if ":" in t}
        assert "prospect" in tag_prefixes, f"prospect tag missing from enriched tags: {tags}"
        assert "channel" in tag_prefixes, f"channel tag missing from enriched tags: {tags}"

        # Verify channel value is correct for email_sent
        channel_tags = [t for t in tags if t.startswith("channel:")]
        assert any("email" in t for t in channel_tags), f"Expected channel:email, got {channel_tags}"

        # Verify JSONL also has enriched tags
        jsonl_path = brain.dir / "events.jsonl"
        event_jsonl = json.loads(
            jsonl_path.read_text(encoding="utf-8").strip().splitlines()[-1]
        )
        jsonl_prefixes = {t.split(":")[0] for t in event_jsonl.get("tags", []) if ":" in t}
        assert "prospect" in jsonl_prefixes, "prospect tag missing from JSONL"
        assert "channel" in jsonl_prefixes, "channel tag missing from JSONL"

        # Verify SQLite also has enriched tags
        conn = sqlite3.connect(str(brain.db_path))
        row = conn.execute(
            "SELECT tags_json FROM events WHERE type = 'DELTA_TAG'"
        ).fetchone()
        conn.close()
        db_tags = json.loads(row[0])
        db_prefixes = {t.split(":")[0] for t in db_tags if ":" in t}
        assert "prospect" in db_prefixes, "prospect tag missing from DB"
        assert "channel" in db_prefixes, "channel tag missing from DB"


# ---------------------------------------------------------------------------
# 4. test_search_keyword
# ---------------------------------------------------------------------------

class TestSearch:
    def test_search_keyword(self, tmp_path):
        """Create a markdown file, rebuild FTS5, search by keyword."""
        brain = _init_brain(tmp_path)

        # Create a markdown file with searchable content
        prospect_file = brain.dir / "prospects" / "Acme Corp.md"
        prospect_file.write_text(
            "# Acme Corp\n\n"
            "## Overview\n"
            "Acme Corp specializes in rocketship manufacturing.\n"
            "CEO: Wile E. Coyote\n"
            "Budget: $500K annually for AI tooling.\n",
            encoding="utf-8",
        )

        # Rebuild FTS5 index
        from gradata._query import fts_rebuild
        count = fts_rebuild()
        assert count >= 1, f"FTS rebuild indexed 0 documents (expected >= 1)"

        # Search for a keyword
        results = brain.search("rocketship", mode="keyword")
        assert len(results) >= 1, "Keyword search returned no results"
        assert any("rocketship" in r.get("text", "").lower() for r in results), (
            f"No result contains 'rocketship': {results}"
        )

        # Verify result structure
        first = results[0]
        assert "source" in first
        assert "text" in first
        assert "score" in first


# ---------------------------------------------------------------------------
# 5. test_manifest_generation
# ---------------------------------------------------------------------------

class TestManifest:
    def test_manifest_generation(self, tmp_path):
        """Generate manifest after emitting events; verify required fields."""
        brain = _init_brain(tmp_path)

        # Emit some events so the manifest has data
        brain.emit("CORRECTION", "pytest", {"category": "DRAFTING"}, session=1)
        brain.emit("OUTPUT", "pytest", {"output_type": "email"}, session=1)
        brain.emit("GATE_RESULT", "pytest", {"gate": "demo-prep", "result": "PASS"}, session=1)

        manifest = brain.manifest()

        # Required top-level keys
        assert manifest["schema_version"] == "1.0.0"
        assert "metadata" in manifest
        assert "quality" in manifest

        # Metadata fields
        meta = manifest["metadata"]
        assert "brain_version" in meta
        assert "maturity_phase" in meta
        assert "generated_at" in meta

        # Quality fields
        quality = manifest["quality"]
        assert "correction_rate" in quality
        assert "first_draft_acceptance" in quality

        # Database section reflects our events
        db = manifest["database"]
        assert db["total_events"] >= 3, f"Expected >= 3 events, got {db['total_events']}"
        assert "events" in db["tables"]

        # Manifest file is written to disk
        assert brain.manifest_path.exists()
        disk_manifest = json.loads(brain.manifest_path.read_text(encoding="utf-8"))
        assert disk_manifest["schema_version"] == "1.0.0"


# ---------------------------------------------------------------------------
# 6. test_validator
# ---------------------------------------------------------------------------

class TestValidator:
    def test_validator(self, tmp_path):
        """Generate manifest, then validate it. No issues expected for a clean brain."""
        brain = _init_brain(tmp_path)

        # Emit events and generate manifest
        brain.emit("OUTPUT", "pytest", {"output_type": "email"}, session=1)
        brain.manifest()

        # Validate
        from gradata._brain_manifest import validate_manifest
        issues = validate_manifest()

        assert isinstance(issues, list)
        assert len(issues) == 0, f"Validation issues: {issues}"

    def test_validator_catches_missing_manifest(self, tmp_path):
        """Validator reports issue when manifest is missing."""
        brain = _init_brain(tmp_path)

        # Delete the manifest that onboard created
        brain.manifest_path.unlink()

        from gradata._brain_manifest import validate_manifest
        issues = validate_manifest()

        assert len(issues) > 0
        assert any("does not exist" in i for i in issues), f"Expected 'does not exist' issue: {issues}"


# ---------------------------------------------------------------------------
# 7. test_export
# ---------------------------------------------------------------------------

class TestExport:
    def test_export_redacts_pii(self, tmp_path):
        """Export a brain with fake PII; verify email and phone are redacted."""
        brain = _init_brain(tmp_path)

        # Create a prospect file with PII
        prospect_file = brain.dir / "prospects" / "John Smith.md"
        prospect_file.write_text(
            "# John Smith\n\n"
            "name: John Smith\n"
            "company: Acme Corp\n"
            "email: john.smith@acmecorp.com\n"
            "phone: +1 (555) 867-5309\n"
            "api_key: sk-abc123secret\n\n"
            "## Notes\n"
            "Met John at the conference. He mentioned budget concerns.\n",
            encoding="utf-8",
        )

        # Export
        zip_path = brain.export(mode="full")

        assert zip_path.exists(), f"Export zip not created at {zip_path}"
        assert str(zip_path).endswith(".zip")

        # Read the zip and check for PII redaction
        with zipfile.ZipFile(zip_path, "r") as zf:
            names = zf.namelist()
            assert "manifest.json" in names, f"manifest.json missing from archive: {names}"

            # Find the prospect file in the archive
            prospect_entries = [n for n in names if "prospects" in n.lower()]
            assert len(prospect_entries) >= 1, f"No prospect files in archive: {names}"

            # Read the prospect file content
            prospect_content = zf.read(prospect_entries[0]).decode("utf-8")

            # PII should be redacted
            assert "john.smith@acmecorp.com" not in prospect_content, (
                "Email was NOT redacted in export"
            )
            assert "[EMAIL_REDACTED]" in prospect_content, (
                "Email redaction marker missing"
            )
            assert "867-5309" not in prospect_content, (
                "Phone was NOT redacted in export"
            )
            assert "[PHONE_REDACTED]" in prospect_content, (
                "Phone redaction marker missing"
            )

            # Raw PII strings should not appear
            assert "john.smith" not in prospect_content.lower(), (
                "Email fragment still present"
            )


# ---------------------------------------------------------------------------
# 8. Core Learning Loop (correction capture)
# ---------------------------------------------------------------------------

try:
    from gradata.enhancements.edit_classifier import classify_edits as _real_classifier
    _has_graduation = True
except ImportError:
    _has_graduation = False


@pytest.mark.skipif(not _has_graduation, reason="requires gradata_cloud")
class TestCoreLearningLoop:
    def test_correct_produces_diff(self, tmp_path):
        """brain.correct() computes diff and emits CORRECTION event."""
        brain = _init_brain(tmp_path)
        result = brain.correct(
            draft="Hello, I wanted to reach out about our product pricing.",
            final="Hi, quick note about pricing.",
            session=1,
        )
        assert result["type"] == "CORRECTION"
        assert result["data"]["severity"] in ("minor", "moderate", "major", "discarded")
        assert result["data"]["edit_distance"] > 0
        assert "classifications" in result

    def test_log_output(self, tmp_path):
        """brain.log_output() emits OUTPUT event."""
        brain = _init_brain(tmp_path)
        result = brain.log_output(
            text="Draft email about pricing",
            output_type="email",
            self_score=7.5,
            session=1,
        )
        assert result["type"] == "OUTPUT"
        assert result["data"]["output_type"] == "email"
        assert result["data"]["self_score"] == 7.5
