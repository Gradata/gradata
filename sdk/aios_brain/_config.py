"""
Brain RAG Pipeline — Shared Configuration (SDK Copy)
=====================================================
SDK LAYER: Portable. No hardcoded paths.
Mirrors brain/scripts/config.py with all path references removed
(paths come from _paths.py instead).
"""

import os

# ── Embedding Model ────────────────────────────────────────────────
# Two providers: "gemini" (cloud, free tier, better quality) or "local" (no API key needed)
EMBEDDING_PROVIDER = os.environ.get("EMBEDDING_PROVIDER", "local")  # SDK default: local

# Gemini config
GEMINI_MODEL = "gemini-embedding-2-preview"
GEMINI_DIMS = 768

# Local config (sentence-transformers via ChromaDB, no API key)
LOCAL_MODEL = "all-MiniLM-L6-v2"
LOCAL_DIMS = 384

# Active config (set by provider)
EMBEDDING_MODEL = GEMINI_MODEL if EMBEDDING_PROVIDER == "gemini" else LOCAL_MODEL
EMBEDDING_DIMS = GEMINI_DIMS if EMBEDDING_PROVIDER == "gemini" else LOCAL_DIMS
MAX_TOKENS_PER_CHUNK = 7500
API_KEY_ENV_VAR = "GEMINI_API_KEY"

# ── ChromaDB Collections ───────────────────────────────────────────
CORE_COLLECTION = "brain_core"
DOMAIN_COLLECTIONS = {
    "sprites": "domain_sprites",
}

# ── File Type Classification ───────────────────────────────────────
FILE_TYPE_MAP = {
    "prospects": "prospect",
    "sessions": "session",
    "emails": "email_pattern",
    "learnings": "learning",
    "metrics": "metric",
    "personas": "persona",
    "competitors": "competitor",
    "objections": "objection",
    "demos": "demo",
    "templates": "template",
    "pipeline": "pipeline",
    "messages": "message",
}

# ── RAG Graduation ─────────────────────────────────────────────────
RAG_ACTIVATION_THRESHOLD = 20
RAG_ACTIVE = True
DOMAIN_THRESHOLDS = {
    "sprites": 20,
}

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
    "prospect": "semantic",
    "session": "episodic",
    "email_pattern": "procedural",
    "learning": "episodic",
    "metric": "episodic",
    "persona": "semantic",
    "competitor": "semantic",
    "objection": "semantic",
    "demo": "episodic",
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
    "prospect_research": {
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
