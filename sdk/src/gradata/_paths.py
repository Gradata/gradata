"""
SDK Paths — Portable Path Resolution
======================================
SDK LAYER: All paths derived from BRAIN_DIR (constructor param or env var).
No hardcoded user paths. No machine-specific references.

For the original runtime: brain/scripts/paths.py (unchanged).
This file is the SDK-portable equivalent.
"""

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class BrainContext:
    """Immutable context holding all resolved paths for a brain instance.

    This is the dependency-injected alternative to the module-level globals.
    Pass a BrainContext to functions instead of relying on mutable global state.
    Enables multi-brain support (multiple Brain instances in one process).
    """
    brain_dir: Path
    db_path: Path
    events_jsonl: Path
    prospects_dir: Path
    sessions_dir: Path
    metrics_dir: Path
    manifest_file: Path
    loop_state: Path
    version_file: Path
    patterns_file: Path
    outcomes_dir: Path
    working_dir: Path
    domain_dir: Path
    lessons_file: Path
    carl_dir: Path
    gates_dir: Path

    @classmethod
    def from_brain_dir(cls, brain_dir: str | Path, working_dir: str | Path | None = None) -> "BrainContext":
        """Build a BrainContext from a brain directory path.

        Args:
            brain_dir: Path to the brain directory.
            working_dir: Optional working directory. Falls back to WORKING_DIR env var or cwd.
        """
        bd = resolve_brain_dir(brain_dir)
        wd = Path(working_dir).resolve() if working_dir else Path(os.environ.get("WORKING_DIR", ".")).resolve()
        return cls(
            brain_dir=bd,
            db_path=bd / "system.db",
            events_jsonl=bd / "events.jsonl",
            prospects_dir=bd / "prospects",
            sessions_dir=bd / "sessions",
            metrics_dir=bd / "metrics",
            manifest_file=bd / ".embed-manifest.json",
            loop_state=bd / "loop-state.md",
            version_file=bd / "VERSION.md",
            patterns_file=bd / "emails" / "PATTERNS.md",
            outcomes_dir=bd / "learnings",
            working_dir=wd,
            domain_dir=Path(os.environ.get("DOMAIN_DIR", str(wd / "domain"))).resolve(),
            lessons_file=bd / "lessons.md",
            carl_dir=wd / ".carl",
            gates_dir=wd / "domain" / "gates",
        )


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

# These are optional — only used by export/manifest in the host runtime.
# SDK users won't have them; modules that reference them handle None gracefully.
WORKING_DIR = Path(os.environ.get("WORKING_DIR", ".")).resolve()
DOMAIN_DIR = Path(os.environ.get("DOMAIN_DIR", ".")).resolve()
LESSONS_FILE = BRAIN_DIR / "lessons.md"
CARL_DIR = WORKING_DIR / ".carl"
GATES_DIR = WORKING_DIR / "domain" / "gates"


def set_brain_dir(brain_dir: str | Path, working_dir: str | Path | None = None):
    """Re-point all module-level path variables to a new brain directory.

    Called by Brain.__init__() so that all SDK modules resolve paths
    relative to the active brain.

    Also stores a BrainContext in _current_context for modules that accept ctx.

    Args:
        brain_dir: Path to the brain directory (contains system.db, prospects/, etc.)
        working_dir: Optional path to the working directory (contains .carl/, .claude/, domain/).
                     If not provided, derived from WORKING_DIR env var or brain_dir parent.
    """
    global BRAIN_DIR, MANIFEST_FILE, LOOP_STATE, VERSION_FILE
    global PATTERNS_FILE, OUTCOMES_DIR, DB_PATH, EVENTS_JSONL
    global PROSPECTS_DIR, SESSIONS_DIR, METRICS_DIR, _current_paths
    global WORKING_DIR, DOMAIN_DIR, LESSONS_FILE, CARL_DIR, GATES_DIR
    global _current_context

    _current_paths = make_paths(brain_dir)
    BRAIN_DIR = _current_paths["BRAIN_DIR"]
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
    LESSONS_FILE = BRAIN_DIR / "lessons.md"
    CARL_DIR = WORKING_DIR / ".carl"
    GATES_DIR = WORKING_DIR / "domain" / "gates"

    # Store immutable context for DI-aware modules
    _current_context = BrainContext.from_brain_dir(brain_dir, working_dir)


def get_current_context() -> "BrainContext | None":
    """Return the current BrainContext, or None if set_brain_dir() hasn't been called."""
    return _current_context


# Module-level default context (None until set_brain_dir() is called)
_current_context: BrainContext | None = None
