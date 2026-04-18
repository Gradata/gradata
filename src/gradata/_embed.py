"""
Brain Embed Script — Delta Embedding.
=======================================
Generates embeddings for brain files and stores them in SQLite.
FTS5 is the primary search engine. sqlite-vec planned for vector similarity.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from . import _paths as _p
from ._config import (
    API_KEY_ENV_VAR,
    EMBEDDING_DIMS,
    EMBEDDING_MODEL,
    EMBEDDING_PROVIDER,
    FILE_TYPE_MAP,
    INDEXABLE_EXTENSIONS,
    LOCAL_MODEL,
    MAX_TOKENS_PER_CHUNK,
    SKIP_DIRS,
    SKIP_FILES,
)

if TYPE_CHECKING:
    from ._paths import BrainContext


def get_file_hash(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


def classify_file(filepath: Path, base_dir: Path) -> str:
    try:
        rel = filepath.relative_to(base_dir)
        parts = rel.parts
        if len(parts) > 1:
            return FILE_TYPE_MAP.get(parts[0], "general")
        return "general"
    except ValueError:
        return "general"


def chunk_markdown(text: str, filepath: str, max_tokens: int = MAX_TOKENS_PER_CHUNK) -> list[dict]:
    estimated_tokens = len(text.split()) * 1.3
    file_type = classify_file(Path(filepath), _p.BRAIN_DIR)
    prefix = f"[Source: {Path(filepath).name} | Type: {file_type}]\n\n"
    if estimated_tokens <= max_tokens:
        return [{"id": filepath, "text": prefix + text, "chunk": 0, "total_chunks": 1}]
    sections = re.split(r"\n(?=## )", text)
    chunks = []
    for i, section in enumerate(sections):
        section = section.strip()
        if not section:
            continue
        chunks.append(
            {
                "id": f"{filepath}#chunk{i}",
                "text": prefix + section,
                "chunk": i,
                "total_chunks": len(sections),
            }
        )
    return chunks


def scan_brain_files(base_dir: Path) -> list[Path]:
    files = []
    for f in base_dir.rglob("*"):
        if f.is_dir():
            continue
        if any(skip in f.parts for skip in SKIP_DIRS):
            continue
        if f.name in SKIP_FILES:
            continue
        if f.suffix not in INDEXABLE_EXTENSIONS:
            continue
        files.append(f)
    return files


def find_changed_files(base_dir: Path) -> tuple[list[Path], list[str], dict]:
    manifest = {}
    if _p.MANIFEST_FILE.exists():
        manifest = json.loads(_p.MANIFEST_FILE.read_text(encoding="utf-8"))
    current_hashes = {}
    changed = []
    for f in scan_brain_files(base_dir):
        rel = str(f.relative_to(base_dir))
        file_hash = get_file_hash(f)
        current_hashes[rel] = file_hash
        if manifest.get(rel) != file_hash:
            changed.append(f)
    deleted = [k for k in manifest if k not in current_hashes]
    return changed, deleted, current_hashes


def extract_session_number(filepath: Path) -> int:
    name = filepath.stem
    match = re.search(r"S(\d+)", name)
    if match:
        return int(match.group(1))
    return -1


def parse_outcome_links() -> dict[str, dict]:
    links = {}
    if _p.OUTCOMES_DIR.exists():
        for f in _p.OUTCOMES_DIR.glob("*.md"):
            text = f.read_text(encoding="utf-8", errors="replace")
            outcome = "unknown"
            result_text = ""
            sources = []
            for line in text.split("\n"):
                line_lower = line.lower().strip()
                if "[outcome:" in line_lower:
                    match = re.search(r"\[outcome:\s*([\w-]+)\]", line_lower)
                    if match:
                        outcome = match.group(1)
                if "result:" in line_lower or "\u2192" in line:
                    result_text = line.strip()[:200]
                for wl in re.findall(r"\[\[([\w/.-]+)\]\]", line):
                    sources.append(wl)
            for src in sources:
                links[src] = {"outcome": outcome, "result": result_text}
    if _p.PATTERNS_FILE.exists():
        text = _p.PATTERNS_FILE.read_text(encoding="utf-8", errors="replace")
        for line in text.split("\n"):
            if "|" in line and "[PROVEN]" in line:
                parts = [p.strip() for p in line.split("|")]
                if len(parts) >= 7:
                    angle = parts[1] if len(parts) > 1 else ""
                    reply_rate = parts[4] if len(parts) > 4 else ""
                    if angle and angle not in ("Angle", "---", ""):
                        try:
                            rate_val = float(reply_rate.replace("%", "").strip())
                        except (ValueError, TypeError):
                            continue
                        links[f"angle:{angle}"] = {
                            "outcome": "proven" if rate_val > 1.0 else "weak",
                            "result": f"{reply_rate} reply rate",
                        }
    return links


def get_gemini_client():
    if EMBEDDING_PROVIDER == "local":
        return None
    from google import genai  # type: ignore[attr-defined]  # optional dep

    api_key = os.environ.get(API_KEY_ENV_VAR)
    if not api_key:
        logging.getLogger("gradata.embed").error("%s not set", API_KEY_ENV_VAR)
        return None
    return genai.Client(api_key=api_key)


_local_model = None


def embed_texts_local(texts: list[str]) -> list[list[float]]:
    global _local_model
    if _local_model is None:
        from sentence_transformers import SentenceTransformer
        _local_model = SentenceTransformer(LOCAL_MODEL)
    embeddings = _local_model.encode(texts)
    return [e.tolist() for e in embeddings]


def embed_texts(
    texts: list[str], client=None, task_type: str = "RETRIEVAL_DOCUMENT"
) -> list[list[float]]:
    if EMBEDDING_PROVIDER == "local":
        return embed_texts_local(texts)
    return embed_texts_gemini(texts, client, task_type)


def embed_texts_gemini(
    texts: list[str], client, task_type: str = "RETRIEVAL_DOCUMENT"
) -> list[list[float]]:
    import time

    from google.genai import types

    all_embeddings = []
    batch_size = 20
    total_batches = (len(texts) + batch_size - 1) // batch_size
    for batch_num, i in enumerate(range(0, len(texts), batch_size)):
        batch = texts[i : i + batch_size]
        result = client.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=batch,
            config=types.EmbedContentConfig(
                output_dimensionality=EMBEDDING_DIMS, task_type=task_type
            ),
        )
        all_embeddings.extend([e.values for e in result.embeddings])
        if batch_num < total_batches - 1:
            time.sleep(1.5)
    return all_embeddings


def _cosine_distance(a: list[float], b: list[float]) -> float:
    """Cosine distance between two vectors. 0=identical, 1=opposite."""
    import math

    dot = sum(x * y for x, y in zip(a, b, strict=False))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    similarity = dot / (norm_a * norm_b)
    return max(0.0, min(1.0, 1.0 - similarity))


def embed_pair(draft: str, final: str) -> dict:
    """Compute embeddings for a correction pair and return semantic delta.

    Returns: {
        "draft_embedding": list[float] | None,
        "final_embedding": list[float] | None,
        "cosine_distance": float,  # 0.0 = identical, 1.0 = opposite
        "semantic_delta": float,   # normalized 0-1 severity from embeddings
    }

    Falls back gracefully: if embedding model unavailable, returns None
    embeddings and cosine_distance=0.0.
    """
    fallback = {
        "draft_embedding": None,
        "final_embedding": None,
        "cosine_distance": 0.0,
        "semantic_delta": 0.0,
    }
    try:
        embeddings = embed_texts([draft, final])
        draft_emb, final_emb = embeddings[0], embeddings[1]
        if draft_emb is None or final_emb is None:
            return fallback

        cos_dist = _cosine_distance(draft_emb, final_emb)
        return {
            "draft_embedding": draft_emb,
            "final_embedding": final_emb,
            "cosine_distance": round(cos_dist, 4),
            "semantic_delta": round(min(1.0, cos_dist * 2.0), 4),
        }
    except Exception:
        return fallback


def _ensure_embeddings_table(conn):
    """Create SQLite table for storing embeddings (sqlite-vec upgrade planned)."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS brain_embeddings (
            id TEXT PRIMARY KEY,
            source TEXT,
            file_type TEXT,
            text TEXT,
            embedding BLOB,
            modified TEXT,
            embed_date TEXT,
            session_num INTEGER,
            chunk INTEGER,
            total_chunks INTEGER,
            outcome TEXT DEFAULT 'none',
            outcome_result TEXT DEFAULT ''
        )
    """)
    conn.commit()


def embed_files(files: list[Path], db_path, base_dir: Path, gemini_client):
    """Embed files and store in SQLite. db_path can be a Path or sqlite3 connection."""
    import sqlite3

    if not files:
        return 0
    outcome_links = parse_outcome_links()
    all_chunks = []
    for f in files:
        text = f.read_text(encoding="utf-8", errors="replace")
        rel = str(f.relative_to(base_dir))
        chunks = chunk_markdown(text, rel)
        outcome_data = outcome_links.get(rel) or outcome_links.get(f.stem, {})
        mod_time = datetime.fromtimestamp(f.stat().st_mtime)
        for chunk in chunks:
            chunk["source"] = rel
            chunk["file_type"] = classify_file(f, base_dir)
            chunk["modified"] = mod_time.isoformat()
            chunk["embed_date"] = mod_time.strftime("%Y-%m-%d")
            chunk["session_num"] = extract_session_number(f)
            chunk["outcome"] = outcome_data.get("outcome", "none")
            chunk["outcome_result"] = outcome_data.get("result", "")
        all_chunks.extend(chunks)
    if not all_chunks:
        return 0
    texts = [c["text"] for c in all_chunks]
    all_embeddings = embed_texts(texts, gemini_client)

    conn = sqlite3.connect(str(db_path))
    _ensure_embeddings_table(conn)
    for i, chunk in enumerate(all_chunks):
        embedding_blob = json.dumps(all_embeddings[i]).encode("utf-8")
        conn.execute(
            """
            INSERT OR REPLACE INTO brain_embeddings
            (id, source, file_type, text, embedding, modified, embed_date,
             session_num, chunk, total_chunks, outcome, outcome_result)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                chunk["id"],
                chunk["source"],
                chunk["file_type"],
                chunk["text"],
                embedding_blob,
                chunk["modified"],
                chunk["embed_date"],
                chunk["session_num"],
                chunk["chunk"],
                chunk["total_chunks"],
                chunk["outcome"],
                chunk["outcome_result"],
            ),
        )
    conn.commit()
    conn.close()
    return len(all_chunks)


def remove_deleted(deleted_keys: list[str], db_path):
    """Remove embeddings for deleted files from SQLite."""
    import sqlite3

    if not deleted_keys:
        return
    conn = sqlite3.connect(str(db_path))
    _ensure_embeddings_table(conn)
    for key in deleted_keys:
        conn.execute("DELETE FROM brain_embeddings WHERE source = ?", (key,))
    conn.commit()
    conn.close()


def get_stats(db_path) -> dict:
    """Get embedding stats from SQLite."""
    import sqlite3

    conn = sqlite3.connect(str(db_path))
    _ensure_embeddings_table(conn)
    count = conn.execute("SELECT COUNT(*) FROM brain_embeddings").fetchone()[0]
    conn.close()
    return {"collection": "brain_embeddings", "total_chunks": count}


def main(
    brain_dir: Path | None = None,
    full: bool = False,
    dry_run: bool = False,
    stats_only: bool = False,
    ctx: BrainContext | None = None,
):
    """Run embedding. Called by Brain.embed() or CLI.

    Embeddings stored in SQLite (brain_embeddings table).
    FTS5 is the primary search engine. sqlite-vec planned for vector similarity.
    """
    if brain_dir is not None:
        _p.set_brain_dir(brain_dir)
    base_dir = ctx.brain_dir if ctx else _p.BRAIN_DIR
    db_path = ctx.db_path if ctx else _p.DB_PATH
    manifest_file = ctx.manifest_file if ctx else _p.MANIFEST_FILE

    if stats_only:
        s = get_stats(db_path)
        print(f"Collection: {s['collection']} | Chunks: {s['total_chunks']}")
        return 0

    if full:
        changed = scan_brain_files(base_dir)
        deleted = []
        current_hashes = {str(f.relative_to(base_dir)): get_file_hash(f) for f in changed}
        print(f"Full re-embed: {len(changed)} files")
    else:
        changed, deleted, current_hashes = find_changed_files(base_dir)
        print(f"Delta: {len(changed)} changed, {len(deleted)} deleted")

    if dry_run:
        if changed:
            print("\nWould embed:")
            for f in changed:
                print(f"  {f.relative_to(base_dir)}")
        if deleted:
            print("\nWould remove:")
            for d in deleted:
                print(f"  {d}")
        return 0

    if not changed and not deleted:
        print("Nothing to embed. Brain is current.")
        return 0

    gemini_client = get_gemini_client()
    chunks_embedded = embed_files(changed, db_path, base_dir, gemini_client)
    print(f"Embedded {chunks_embedded} chunks from {len(changed)} files")

    if deleted:
        remove_deleted(deleted, db_path)
        print(f"Removed embeddings for {len(deleted)} deleted files")

    manifest_file.write_text(json.dumps(current_hashes, indent=2), encoding="utf-8")
    print(f"Manifest updated: {len(current_hashes)} files tracked")
    return chunks_embedded
