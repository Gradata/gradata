"""
Brain RAG Pipeline — Shared Configuration (SDK Copy)
=====================================================
SDK LAYER: Portable. No hardcoded paths.

Domain-specific values (FILE_TYPE_MAP, MEMORY_TYPE_MAP, MEMORY_TYPE_WEIGHTS)
are defaults that can be overridden by brain/taxonomy.json. See reload_config()
and the _tag_taxonomy.py reload mechanism.
"""

import json
import os
from pathlib import Path

# ── Embedding Model ────────────────────────────────────────────────
# Two providers: "gemini" (cloud, free tier, better quality) or "local" (no API key needed)
EMBEDDING_PROVIDER = os.environ.get("EMBEDDING_PROVIDER", "local")  # SDK default: local

# Gemini config
GEMINI_MODEL = "gemini-embedding-2-preview"
GEMINI_DIMS = 768

# Local config (sentence-transformers, no API key)
LOCAL_MODEL = "all-MiniLM-L6-v2"
LOCAL_DIMS = 384

# Active config (set by provider)
EMBEDDING_MODEL = GEMINI_MODEL if EMBEDDING_PROVIDER == "gemini" else LOCAL_MODEL
EMBEDDING_DIMS = GEMINI_DIMS if EMBEDDING_PROVIDER == "gemini" else LOCAL_DIMS
MAX_TOKENS_PER_CHUNK = 7500
API_KEY_ENV_VAR = "GEMINI_API_KEY"

# ── Search: FTS5 is primary search engine, sqlite-vec planned for vector similarity ──

# ── File Type Classification ───────────────────────────────────────
FILE_TYPE_MAP = {
    "entities": "entity",
    "sessions": "session",
    "emails": "email_pattern",
    "learnings": "learning",
    "metrics": "metric",
    "personas": "persona",
    "competitors": "competitor",
    "objections": "objection",
    "meetings": "meeting",
    "templates": "template",
    "pipeline": "pipeline",
    "messages": "message",
}

# ── RAG Graduation ─────────────────────────────────────────────────
RAG_ACTIVATION_THRESHOLD = 20
RAG_ACTIVE = True
DOMAIN_THRESHOLDS = {}

# ── Episodic Memory ───────────────────────────────────────────────
RECENCY_DECAY = 0.008
RECENCY_FLOOR = 0.5
RECENCY_WINDOW_DAYS = 60

# ── Confidence Scoring ───────────────────────────────────────────
CONFIDENCE_HIGH = 0.65
CONFIDENCE_MED = 0.50
CONFIDENCE_LOW = 0.35

# ── Query Defaults ─────────────────────────────────────────────────
DEFAULT_TOP_K = 5
SIMILARITY_THRESHOLD = 0.35

# ── Brain File Extensions to Index ─────────────────────────────────
INDEXABLE_EXTENSIONS = {".md", ".txt"}

# ── Files/Dirs to Skip ────────────────────────────────────────────
SKIP_FILES = {"_TEMPLATE.md", "README.md", ".gitkeep"}
SKIP_DIRS = {".git", ".vectorstore", "scripts"}

# ── Memory Taxonomy ──────────────────────────────────────────────
MEMORY_TYPE_MAP = {
    "entity": "semantic",
    "session": "episodic",
    "email_pattern": "procedural",
    "learning": "episodic",
    "metric": "episodic",
    "persona": "semantic",
    "competitor": "semantic",
    "objection": "semantic",
    "meeting": "episodic",
    "template": "procedural",
    "pipeline": "episodic",
    "message": "episodic",
    "general": "semantic",
}

MEMORY_TYPE_WEIGHTS = {
    "email_drafting": {
        "procedural": 1.5,
        "semantic": 1.2,
        "episodic": 0.8,
        "strategic": 0.6,
    },
    "entity_research": {
        "semantic": 1.5,
        "episodic": 1.2,
        "strategic": 0.8,
        "procedural": 0.6,
    },
    "system_decision": {
        "strategic": 1.5,
        "procedural": 1.2,
        "semantic": 0.8,
        "episodic": 0.6,
    },
    "default": {
        "episodic": 1.0,
        "semantic": 1.0,
        "procedural": 1.0,
        "strategic": 1.0,
    },
}


def reload_config(brain_dir: str | Path | None = None) -> None:
    """Reload domain-specific config from brain/taxonomy.json if it exists.

    This makes FILE_TYPE_MAP, MEMORY_TYPE_MAP, and MEMORY_TYPE_WEIGHTS
    configurable per brain. Sales defaults are used if taxonomy.json is
    absent or doesn't contain these keys.

    Called automatically by Brain.__init__() after taxonomy reload.

    taxonomy.json can include:
        {
          "file_type_map": {"projects": "project", "tickets": "ticket"},
          "memory_type_map": {"project": "semantic", "ticket": "episodic"},
          "memory_type_weights": {
            "code_review": {"procedural": 1.5, "semantic": 1.2, ...},
            "default": {"episodic": 1.0, ...}
          }
        }
    """
    global FILE_TYPE_MAP, MEMORY_TYPE_MAP, MEMORY_TYPE_WEIGHTS

    if brain_dir is None:
        return

    taxonomy_path = Path(brain_dir) / "taxonomy.json"
    if not taxonomy_path.exists():
        return

    try:
        data = json.loads(taxonomy_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return

    # Merge (not replace) so defaults are preserved for unmapped types
    if "file_type_map" in data and isinstance(data["file_type_map"], dict):
        FILE_TYPE_MAP.update(data["file_type_map"])

    if "memory_type_map" in data and isinstance(data["memory_type_map"], dict):
        MEMORY_TYPE_MAP.update(data["memory_type_map"])

    if "memory_type_weights" in data and isinstance(data["memory_type_weights"], dict):
        # Always preserve the "default" fallback
        new_weights = data["memory_type_weights"]
        if "default" not in new_weights:
            new_weights["default"] = MEMORY_TYPE_WEIGHTS.get("default", {
                "episodic": 1.0, "semantic": 1.0, "procedural": 1.0, "strategic": 1.0,
            })
        MEMORY_TYPE_WEIGHTS.update(new_weights)
