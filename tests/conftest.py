"""
Shared test fixtures for the Gradata test suite.

Centralises the _init_brain() helper that was previously duplicated across
test_brain.py and test_coverage_gaps.py.  All test modules should use the
``fresh_brain`` fixture (or call ``init_brain()`` directly) instead of
maintaining their own copy.

Run: pytest sdk/tests/ -v
"""

import os
from pathlib import Path

import pytest

from gradata import Brain


# ---------------------------------------------------------------------------
# Core helper — rewires module-level path caches after Brain.init()
# ---------------------------------------------------------------------------

def init_brain(
    tmp_path: Path,
    name: str = "TestBrain",
    domain: str = "Testing",
) -> Brain:
    """Create a fresh brain in *tmp_path/brain* and rewire cached paths.

    After ``Brain.init()`` the SDK's module-level path variables (imported at
    load time) still point at the old location.  This function forces every
    known caching module to pick up the new directory so that tests are fully
    isolated.
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

    # --- rewire module-level path caches ---
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

    import gradata._query as _q
    _q.DB_PATH = _p.DB_PATH
    _q.BRAIN_DIR = _p.BRAIN_DIR

    import gradata._tag_taxonomy as _tt
    _tt.PROSPECTS_DIR = _p.PROSPECTS_DIR

    return brain


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def fresh_brain(tmp_path: Path) -> Brain:
    """Yield a fully-initialised, isolated brain for a single test."""
    return init_brain(tmp_path)


@pytest.fixture
def brain_with_events(tmp_path: Path) -> Brain:
    """Brain pre-loaded with a few representative events."""
    brain = init_brain(tmp_path)
    brain.emit("CORRECTION", "pytest", {"category": "DRAFTING"}, session=1)
    brain.emit("OUTPUT", "pytest", {"output_type": "email"}, session=1)
    brain.emit("GATE_RESULT", "pytest", {"gate": "demo-prep", "result": "PASS"}, session=1)
    return brain


@pytest.fixture
def brain_with_content(tmp_path: Path) -> Brain:
    """Brain with a prospect markdown file for search tests."""
    brain = init_brain(tmp_path)
    prospect = brain.dir / "prospects" / "Acme Corp.md"
    prospect.write_text(
        "# Acme Corp\n\n"
        "## Overview\n"
        "Acme Corp specialises in rocketship manufacturing.\n"
        "CEO: Wile E. Coyote\n"
        "Budget: $500K annually for AI tooling.\n",
        encoding="utf-8",
    )
    return brain
