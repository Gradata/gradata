"""
SDK Paths — Portable Path Resolution
======================================
SDK LAYER: All paths derived from BRAIN_DIR (constructor param or env var).
No hardcoded user paths. No machine-specific references.

For Oliver's original runtime: brain/scripts/paths.py (unchanged).
This file is the SDK-portable equivalent.
"""

import os
from pathlib import Path


def resolve_brain_dir(brain_dir: str | Path | None = None) -> Path:
    """Resolve brain directory from argument, env var, or cwd."""
    if brain_dir:
        return Path(brain_dir).resolve()
    env = os.environ.get("BRAIN_DIR")
    if env:
        return Path(env).resolve()
    return Path.cwd().resolve()


def make_paths(brain_dir: str | Path | None = None) -> dict:
    """Build all derived paths from a brain directory.

    Returns a dict of Path objects keyed by the same names
    used in the original paths.py, so callers can do:
        p = make_paths(brain_dir)
        DB_PATH = p["DB_PATH"]
    """
    bd = resolve_brain_dir(brain_dir)

    return {
        "BRAIN_DIR": bd,
        "CHROMA_DIR": bd / ".vectorstore",
        "MANIFEST_FILE": bd / ".embed-manifest.json",
        "LOOP_STATE": bd / "loop-state.md",
        "VERSION_FILE": bd / "VERSION.md",
        "PATTERNS_FILE": bd / "emails" / "PATTERNS.md",
        "OUTCOMES_DIR": bd / "learnings",
        "DB_PATH": bd / "system.db",
        "EVENTS_JSONL": bd / "events.jsonl",
        "PROSPECTS_DIR": bd / "prospects",
        "SESSIONS_DIR": bd / "sessions",
        "METRICS_DIR": bd / "metrics",
    }


# Module-level defaults (set when BRAIN_DIR env var is present or cwd is used).
# SDK classes override these by calling set_brain_dir() before using modules.
_current_paths = make_paths()

BRAIN_DIR = _current_paths["BRAIN_DIR"]
CHROMA_DIR = _current_paths["CHROMA_DIR"]
MANIFEST_FILE = _current_paths["MANIFEST_FILE"]
LOOP_STATE = _current_paths["LOOP_STATE"]
VERSION_FILE = _current_paths["VERSION_FILE"]
PATTERNS_FILE = _current_paths["PATTERNS_FILE"]
OUTCOMES_DIR = _current_paths["OUTCOMES_DIR"]
DB_PATH = _current_paths["DB_PATH"]
EVENTS_JSONL = _current_paths["EVENTS_JSONL"]
PROSPECTS_DIR = _current_paths["PROSPECTS_DIR"]
SESSIONS_DIR = _current_paths["SESSIONS_DIR"]
METRICS_DIR = _current_paths["METRICS_DIR"]

# These are optional — only used by export/manifest in Oliver's setup.
# SDK users won't have them; modules that reference them handle None gracefully.
WORKING_DIR = Path(os.environ.get("WORKING_DIR", ".")).resolve()
DOMAIN_DIR = Path(os.environ.get("DOMAIN_DIR", ".")).resolve()
LESSONS_FILE = WORKING_DIR / ".claude" / "lessons.md"
CARL_DIR = WORKING_DIR / ".carl"
GATES_DIR = WORKING_DIR / "domain" / "gates"


def set_brain_dir(brain_dir: str | Path, working_dir: str | Path | None = None):
    """Re-point all module-level path variables to a new brain directory.

    Called by Brain.__init__() so that all SDK modules resolve paths
    relative to the active brain.

    Args:
        brain_dir: Path to the brain directory (contains system.db, prospects/, etc.)
        working_dir: Optional path to the working directory (contains .carl/, .claude/, domain/).
                     If not provided, derived from WORKING_DIR env var or brain_dir parent.
    """
    global BRAIN_DIR, CHROMA_DIR, MANIFEST_FILE, LOOP_STATE, VERSION_FILE
    global PATTERNS_FILE, OUTCOMES_DIR, DB_PATH, EVENTS_JSONL
    global PROSPECTS_DIR, SESSIONS_DIR, METRICS_DIR, _current_paths
    global WORKING_DIR, DOMAIN_DIR, LESSONS_FILE, CARL_DIR, GATES_DIR

    _current_paths = make_paths(brain_dir)
    BRAIN_DIR = _current_paths["BRAIN_DIR"]
    CHROMA_DIR = _current_paths["CHROMA_DIR"]
    MANIFEST_FILE = _current_paths["MANIFEST_FILE"]
    LOOP_STATE = _current_paths["LOOP_STATE"]
    VERSION_FILE = _current_paths["VERSION_FILE"]
    PATTERNS_FILE = _current_paths["PATTERNS_FILE"]
    OUTCOMES_DIR = _current_paths["OUTCOMES_DIR"]
    DB_PATH = _current_paths["DB_PATH"]
    EVENTS_JSONL = _current_paths["EVENTS_JSONL"]
    PROSPECTS_DIR = _current_paths["PROSPECTS_DIR"]
    SESSIONS_DIR = _current_paths["SESSIONS_DIR"]
    METRICS_DIR = _current_paths["METRICS_DIR"]

    # Update working dir and derived paths
    if working_dir:
        WORKING_DIR = Path(working_dir).resolve()
    elif os.environ.get("WORKING_DIR"):
        WORKING_DIR = Path(os.environ["WORKING_DIR"]).resolve()
    DOMAIN_DIR = Path(os.environ.get("DOMAIN_DIR", WORKING_DIR / "domain")).resolve()
    LESSONS_FILE = WORKING_DIR / ".claude" / "lessons.md"
    CARL_DIR = WORKING_DIR / ".carl"
    GATES_DIR = WORKING_DIR / "domain" / "gates"
