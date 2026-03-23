"""
Brain Query Script — Hybrid Search (SDK Copy).
================================================
Three retrieval paths, auto-routed by query type:
  1. KEYWORD  — SQLite FTS5
  2. SEMANTIC — ChromaDB vector search
  3. HYBRID   — Both paths merged via Reciprocal Rank Fusion (RRF)

Portable — uses _paths and _config instead of hardcoded paths.
"""

import os
import re
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

from aios_brain._config import (
    CORE_COLLECTION, DOMAIN_COLLECTIONS,
    EMBEDDING_MODEL, EMBEDDING_DIMS, EMBEDDING_PROVIDER,
    DEFAULT_TOP_K, SIMILARITY_THRESHOLD, API_KEY_ENV_VAR,
    RECENCY_DECAY, RECENCY_FLOOR, RECENCY_WINDOW_DAYS,
    CONFIDENCE_HIGH, CONFIDENCE_MED, CONFIDENCE_LOW,
    MEMORY_TYPE_MAP, MEMORY_TYPE_WEIGHTS,
    FILE_TYPE_MAP, INDEXABLE_EXTENSIONS, SKIP_FILES, SKIP_DIRS,
    MAX_TOKENS_PER_CHUNK, LOCAL_MODEL,
)
import aios_brain._paths as _p


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


def fts_index(source: str, file_type: str, text: str, embed_date: str = ""):
    conn = sqlite3.connect(str(_p.DB_PATH))
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


def fts_index_batch(docs: list[dict]):
    conn = sqlite3.connect(str(_p.DB_PATH))
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


def fts_rebuild():
    conn = sqlite3.connect(str(_p.DB_PATH))
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
    brain_path = Path(_p.BRAIN_DIR)
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


def fts_search(query_text: str, file_type: str = None, top_k: int = 10) -> list[dict]:
    conn = sqlite3.connect(str(_p.DB_PATH))
    _ensure_fts_table(conn)
    clean_query = query_text.strip('"').strip("'")
    fts_query = clean_query.replace('"', '""')
    sql = "SELECT rowid, source, file_type, text, embed_date, rank FROM brain_fts WHERE brain_fts MATCH ?"
    params = [f'"{fts_query}"']
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


def get_chroma_client():
    import chromadb
    if not _p.CHROMA_DIR.exists():
        return None
    return chromadb.PersistentClient(path=str(_p.CHROMA_DIR))


def embed_query(text: str, gemini_client=None) -> list[float]:
    if EMBEDDING_PROVIDER == "local":
        from chromadb.utils import embedding_functions
        ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=LOCAL_MODEL)
        return ef([text])[0]
    from google.genai import types
    result = gemini_client.models.embed_content(
        model=EMBEDDING_MODEL, contents=[text],
        config=types.EmbedContentConfig(output_dimensionality=EMBEDDING_DIMS, task_type="RETRIEVAL_QUERY"),
    )
    return result.embeddings[0].values


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
    query: str, file_type: str | None = None, domain: str = "sprites",
    top_k: int = DEFAULT_TOP_K, threshold: float = SIMILARITY_THRESHOLD,
    use_recency: bool = True, memory_type: str | None = None,
    mode: str | None = None,
) -> list[dict]:
    if mode is None:
        mode = detect_query_mode(query)

    # KEYWORD-ONLY PATH
    if mode == "keyword":
        fts_results = fts_search(query, file_type=file_type, top_k=top_k)
        for r in fts_results:
            r["retrieval_mode"] = "keyword"
            r["raw_score"] = r.get("fts_rank", 0)
            r["score"] = r.get("fts_rank", 0)
            r["confidence"] = "keyword_match"
            r["recency_weight"] = 1.0
            r["memory_weight"] = 1.0
            r["memory_type"] = infer_memory_type(r.get("file_type", ""), r.get("source", ""))
            r["modified"] = r.get("embed_date", "unknown")
            r["session_num"] = -1
            r["outcome"] = "none"
            r["outcome_result"] = ""
            r["collection"] = "fts5"
        return fts_results

    # SEMANTIC PATH
    def _vector_search() -> list[dict]:
        try:
            import chromadb
        except ImportError:
            return [{"error": "chromadb not installed. Run: pip install chromadb"}]

        client = get_chroma_client()
        if client is None:
            return [{"error": "Vector store not initialized. Run brain.embed() first."}]

        gemini_client = None
        if EMBEDDING_PROVIDER != "local":
            try:
                from google import genai
            except ImportError:
                return [{"error": "google-genai not installed. Run: pip install google-genai"}]
            api_key = os.environ.get(API_KEY_ENV_VAR)
            if not api_key:
                return [{"error": f"{API_KEY_ENV_VAR} not set. Set EMBEDDING_PROVIDER=local for API-free mode."}]
            gemini_client = genai.Client(api_key=api_key)

        query_embedding = embed_query(query, gemini_client)
        where_filter = {"file_type": file_type} if file_type else None
        fetch_k = top_k * 3 if use_recency else top_k
        results = []

        def process_collection_results(col_results, collection_name):
            for i, doc_id in enumerate(col_results["ids"][0]):
                distance = col_results["distances"][0][i]
                raw_score = 1 - distance
                if raw_score < threshold:
                    continue
                meta = col_results["metadatas"][0][i]
                recency_w = 1.0
                if use_recency:
                    recency_w = compute_recency_weight(meta.get("embed_date", ""))
                doc_file_type = meta.get("file_type", "unknown")
                doc_source = meta.get("source", doc_id)
                doc_memory_type = infer_memory_type(doc_file_type, doc_source)
                memory_w = get_memory_weight(doc_memory_type, memory_type)
                final_score = raw_score * recency_w * memory_w
                confidence = classify_confidence(final_score)
                results.append({
                    "source": doc_source, "file_type": doc_file_type,
                    "memory_type": doc_memory_type,
                    "text": col_results["documents"][0][i][:500],
                    "raw_score": round(raw_score, 3), "score": round(final_score, 3),
                    "confidence": confidence, "recency_weight": round(recency_w, 3),
                    "memory_weight": round(memory_w, 3),
                    "modified": meta.get("modified", "unknown"),
                    "embed_date": meta.get("embed_date", "unknown"),
                    "session_num": meta.get("session_num", -1),
                    "outcome": meta.get("outcome", "none"),
                    "outcome_result": meta.get("outcome_result", ""),
                    "collection": collection_name, "retrieval_mode": "semantic",
                })

        try:
            core = client.get_collection(CORE_COLLECTION)
            core_results = core.query(
                query_embeddings=[query_embedding],
                n_results=min(fetch_k, core.count() or 1),
                where=where_filter,
                include=["documents", "metadatas", "distances"],
            )
            process_collection_results(core_results, "core")
        except Exception:
            pass

        domain_name = DOMAIN_COLLECTIONS.get(domain)
        if domain_name:
            try:
                domain_col = client.get_collection(domain_name)
                domain_results = domain_col.query(
                    query_embeddings=[query_embedding],
                    n_results=min(fetch_k, domain_col.count() or 1),
                    where=where_filter,
                    include=["documents", "metadatas", "distances"],
                )
                process_collection_results(domain_results, domain_name)
            except Exception:
                pass

        results.sort(key=lambda r: r["score"], reverse=True)
        return results[:top_k]

    if mode == "semantic":
        return _vector_search()

    # HYBRID PATH
    semantic_results = _vector_search()
    keyword_results = fts_search(query, file_type=file_type, top_k=top_k)
    for r in keyword_results:
        r["retrieval_mode"] = "keyword"
    merged = reciprocal_rank_fusion([semantic_results, keyword_results])
    for r in merged:
        if use_recency and r.get("embed_date") and r["embed_date"] != "unknown":
            recency_w = compute_recency_weight(r["embed_date"])
            r["rrf_score"] = round(r.get("rrf_score", 0) * recency_w, 4)
            r["recency_weight"] = round(recency_w, 3)
        r["retrieval_mode"] = "hybrid"
        r["score"] = r.get("rrf_score", r.get("score", 0))
        r["confidence"] = classify_confidence(r["score"]) if r["score"] < 1 else "hybrid_match"
    merged.sort(key=lambda r: r.get("score", 0), reverse=True)
    return merged[:top_k]
