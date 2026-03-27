"""
Brain Query Script — FTS5 Search (SDK Copy).
=============================================
Primary search: SQLite FTS5 (keyword matching).
sqlite-vec planned for vector similarity.
Portable — uses _paths and _config instead of hardcoded paths.
"""

import sqlite3
from datetime import datetime
from pathlib import Path

from gradata._config import (
    DEFAULT_TOP_K, SIMILARITY_THRESHOLD,
    RECENCY_DECAY, RECENCY_FLOOR, RECENCY_WINDOW_DAYS,
    CONFIDENCE_HIGH, CONFIDENCE_MED, CONFIDENCE_LOW,
    MEMORY_TYPE_MAP, MEMORY_TYPE_WEIGHTS,
    FILE_TYPE_MAP, INDEXABLE_EXTENSIONS, SKIP_FILES, SKIP_DIRS,
    MAX_TOKENS_PER_CHUNK,
)
import gradata._paths as _p
from gradata._paths import BrainContext


# ── FTS5 Full-Text Search ────────────────────────────────────────────────

def _ensure_fts_table(conn: sqlite3.Connection):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS brain_fts_content (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT, file_type TEXT, text TEXT, embed_date TEXT
        )
    """)
    conn.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS brain_fts USING fts5(
            source, file_type, text, embed_date,
            content='brain_fts_content', content_rowid='id',
            tokenize='porter unicode61'
        )
    """)
    conn.commit()


def fts_index(source: str, file_type: str, text: str, embed_date: str = "",
              ctx: "BrainContext | None" = None):
    db = ctx.db_path if ctx else _p.DB_PATH
    conn = sqlite3.connect(str(db))
    _ensure_fts_table(conn)
    cursor = conn.execute(
        "INSERT INTO brain_fts_content (source, file_type, text, embed_date) VALUES (?, ?, ?, ?)",
        (source, file_type, text, embed_date),
    )
    rowid = cursor.lastrowid
    conn.execute(
        "INSERT INTO brain_fts (rowid, source, file_type, text, embed_date) VALUES (?, ?, ?, ?, ?)",
        (rowid, source, file_type, text, embed_date),
    )
    conn.commit()
    conn.close()


def fts_index_batch(docs: list[dict], ctx: "BrainContext | None" = None):
    db = ctx.db_path if ctx else _p.DB_PATH
    conn = sqlite3.connect(str(db))
    _ensure_fts_table(conn)
    for d in docs:
        cursor = conn.execute(
            "INSERT INTO brain_fts_content (source, file_type, text, embed_date) VALUES (?, ?, ?, ?)",
            (d["source"], d["file_type"], d["text"], d.get("embed_date", "")),
        )
        rowid = cursor.lastrowid
        conn.execute(
            "INSERT INTO brain_fts (rowid, source, file_type, text, embed_date) VALUES (?, ?, ?, ?, ?)",
            (rowid, d["source"], d["file_type"], d["text"], d.get("embed_date", "")),
        )
    conn.commit()
    conn.close()


def fts_rebuild(ctx: "BrainContext | None" = None):
    db = ctx.db_path if ctx else _p.DB_PATH
    conn = sqlite3.connect(str(db))
    try:
        conn.execute("DROP TABLE IF EXISTS brain_fts")
    except Exception:
        pass
    try:
        conn.execute("DROP TABLE IF EXISTS brain_fts_content")
    except Exception:
        pass
    conn.commit()
    _ensure_fts_table(conn)

    docs = []
    brain_path = Path(ctx.brain_dir if ctx else _p.BRAIN_DIR)
    for ext in INDEXABLE_EXTENSIONS:
        for fpath in brain_path.rglob(f"*{ext}"):
            rel = str(fpath.relative_to(brain_path)).replace("\\", "/")
            if any(skip in fpath.parts for skip in SKIP_DIRS):
                continue
            if fpath.name in SKIP_FILES:
                continue
            try:
                text = fpath.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            if not text.strip():
                continue
            parts = rel.split("/")
            file_type = FILE_TYPE_MAP.get(parts[0], "general") if parts else "general"
            embed_date = datetime.fromtimestamp(fpath.stat().st_mtime).strftime("%Y-%m-%d")
            chunk_size = MAX_TOKENS_PER_CHUNK * 4
            for i in range(0, len(text), chunk_size):
                chunk = text[i:i + chunk_size]
                docs.append({"source": rel, "file_type": file_type, "text": chunk, "embed_date": embed_date})

    if docs:
        for d in docs:
            cursor = conn.execute(
                "INSERT INTO brain_fts_content (source, file_type, text, embed_date) VALUES (?, ?, ?, ?)",
                (d["source"], d["file_type"], d["text"], d.get("embed_date", "")),
            )
            rowid = cursor.lastrowid
            conn.execute(
                "INSERT INTO brain_fts (rowid, source, file_type, text, embed_date) VALUES (?, ?, ?, ?, ?)",
                (rowid, d["source"], d["file_type"], d["text"], d.get("embed_date", "")),
            )
    conn.commit()
    conn.close()
    return len(docs)


def fts_search(query_text: str, file_type: str = None, top_k: int = 10,
               ctx: "BrainContext | None" = None) -> list[dict]:
    db = ctx.db_path if ctx else _p.DB_PATH
    conn = sqlite3.connect(str(db))
    _ensure_fts_table(conn)
    clean_query = query_text.strip('"').strip("'")
    # FTS5: use OR between words for broad matching (not phrase-only).
    # "budget objections" → "budget" OR "objections" — matches docs with either word.
    words = [w.replace('"', '""') for w in clean_query.split() if w.strip()]
    if len(words) > 1:
        fts_query = " OR ".join(f'"{w}"' for w in words)
    else:
        fts_query = f'"{words[0]}"' if words else '""'
    sql = "SELECT rowid, source, file_type, text, embed_date, rank FROM brain_fts WHERE brain_fts MATCH ?"
    params = [fts_query]
    if file_type:
        sql += " AND file_type = ?"
        params.append(file_type)
    sql += " ORDER BY rank LIMIT ?"
    params.append(top_k)
    try:
        rows = conn.execute(sql, params).fetchall()
    except Exception:
        conn.close()
        return []
    conn.close()
    results = []
    for r in rows:
        results.append({
            "rowid": r[0], "source": r[1] or "", "file_type": r[2] or "general",
            "text": (r[3] or "")[:500], "embed_date": r[4] or "",
            "fts_rank": abs(r[5]) if r[5] else 0,
        })
    return results


# ── Query Routing ────────────────────────────────────────────────────────

def detect_query_mode(query_text: str) -> str:
    if query_text.startswith('"') and query_text.endswith('"'):
        return "keyword"
    if query_text.startswith("'") and query_text.endswith("'"):
        return "keyword"
    words = query_text.split()
    proper_nouns = [w for w in words if w[0].isupper() and not w.isupper() and len(w) > 1]
    if proper_nouns and len(words) >= 2:
        return "hybrid"
    if len(words) <= 2:
        return "keyword"
    question_words = {"what", "which", "how", "why", "when", "where", "who", "find", "show", "list"}
    if words[0].lower() in question_words:
        return "semantic"
    return "hybrid"


def reciprocal_rank_fusion(ranked_lists: list[list[dict]], k: int = 60) -> list[dict]:
    scores = {}
    for results in ranked_lists:
        for rank, result in enumerate(results):
            key = result.get("source", "") + "|" + result.get("text", "")[:100]
            rrf_contribution = 1.0 / (k + rank + 1)
            if key not in scores:
                scores[key] = {"rrf_score": 0.0, "result": result}
            scores[key]["rrf_score"] += rrf_contribution
    merged = sorted(scores.values(), key=lambda x: x["rrf_score"], reverse=True)
    output = []
    for item in merged:
        r = item["result"].copy()
        r["rrf_score"] = round(item["rrf_score"], 4)
        output.append(r)
    return output


def embed_query(text: str) -> list[float]:
    """Embed a query string. Uses sentence-transformers locally.

    sqlite-vec planned for vector similarity search.
    """
    from gradata._embed import embed_texts_local
    return embed_texts_local([text])[0]


def compute_recency_weight(embed_date: str) -> float:
    try:
        doc_date = datetime.strptime(embed_date, "%Y-%m-%d")
    except (ValueError, TypeError):
        return RECENCY_FLOOR
    age_days = (datetime.now() - doc_date).days
    if age_days < 0:
        return 1.0
    if age_days > RECENCY_WINDOW_DAYS:
        return RECENCY_FLOOR
    return max(RECENCY_FLOOR, 1.0 - (age_days * RECENCY_DECAY))


def classify_confidence(score: float) -> str:
    if score >= CONFIDENCE_HIGH:
        return "high"
    elif score >= CONFIDENCE_MED:
        return "medium"
    elif score >= CONFIDENCE_LOW:
        return "low"
    return "below_threshold"


def infer_memory_type(file_type: str, source: str = "") -> str:
    source_lower = source.lower().replace("\\", "/")
    for pat in ["competitive-intelligence", "competitor-adaptations",
                "gap-analysis", "sdk-north-star", "sdk-improvements",
                "sdk-v2-improvements", "forecasting", "competitive-audit"]:
        if pat in source_lower:
            return "strategic"
    for pat in ["follow-up-cadence", "prospecting-tools", "versioning-protocol",
                "patterns.md", "protocol.md"]:
        if pat in source_lower:
            return "procedural"
    for pat in ["judgment-calibration", "outcome-retrospectives",
                "calibration-audit", "outreach-analytics",
                "loop-state", "signals", "follow-up tracker",
                "experiment tracker"]:
        if pat in source_lower:
            return "episodic"
    return MEMORY_TYPE_MAP.get(file_type, "semantic")


def get_memory_weight(memory_type: str, task) -> float:
    if not task:
        return 1.0
    weights = MEMORY_TYPE_WEIGHTS.get(task, MEMORY_TYPE_WEIGHTS["default"])
    return weights.get(memory_type, 1.0)


def brain_search(
    query: str, file_type: str | None = None, domain: str = "default",
    top_k: int = DEFAULT_TOP_K, threshold: float = SIMILARITY_THRESHOLD,
    use_recency: bool = True, memory_type: str | None = None,
    mode: str | None = None, ctx: "BrainContext | None" = None,
) -> list[dict]:
    """Search the brain using FTS5.

    All modes use FTS5 keyword search.
    Semantic/hybrid modes fall back to FTS5 with recency and memory weighting.
    sqlite-vec planned for true vector similarity search.
    """
    if mode is None:
        mode = detect_query_mode(query)

    # All paths use FTS5 keyword search
    fts_results = fts_search(query, file_type=file_type, top_k=top_k, ctx=ctx)
    for r in fts_results:
        r["retrieval_mode"] = mode
        r["raw_score"] = r.get("fts_rank", 0)
        recency_w = 1.0
        if use_recency and r.get("embed_date") and r["embed_date"] != "unknown":
            recency_w = compute_recency_weight(r["embed_date"])
        mem_type = infer_memory_type(r.get("file_type", ""), r.get("source", ""))
        memory_w = get_memory_weight(mem_type, memory_type)
        r["score"] = round(r.get("fts_rank", 0) * recency_w * memory_w, 4)
        r["confidence"] = "keyword_match" if mode == "keyword" else classify_confidence(min(r["score"], 1.0))
        r["recency_weight"] = round(recency_w, 3)
        r["memory_weight"] = round(memory_w, 3)
        r["memory_type"] = mem_type
        r["modified"] = r.get("embed_date", "unknown")
        r["session_num"] = -1
        r["outcome"] = "none"
        r["outcome_result"] = ""
        r["collection"] = "fts5"

    if mode != "keyword":
        # Re-sort by weighted score for semantic/hybrid modes
        fts_results.sort(key=lambda r: r.get("score", 0), reverse=True)
    return fts_results
