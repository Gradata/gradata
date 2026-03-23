"""
Brain Embed Script — Delta Embedding (SDK Copy).
==================================================
Embeds new/changed brain files into ChromaDB.
Portable — uses _paths and _config instead of hardcoded paths.
"""

import hashlib
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

from aios_brain._config import (
    CORE_COLLECTION, EMBEDDING_MODEL, EMBEDDING_DIMS, EMBEDDING_PROVIDER,
    MAX_TOKENS_PER_CHUNK, FILE_TYPE_MAP, SKIP_FILES, SKIP_DIRS,
    INDEXABLE_EXTENSIONS, API_KEY_ENV_VAR, LOCAL_MODEL,
)
import aios_brain._paths as _p


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
    source_name = Path(filepath).stem
    file_type = classify_file(Path(filepath), _p.BRAIN_DIR)
    prefix = f"[Source: {Path(filepath).name} | Type: {file_type}]\n\n"
    if estimated_tokens <= max_tokens:
        return [{"id": filepath, "text": prefix + text, "chunk": 0, "total_chunks": 1}]
    sections = re.split(r'\n(?=## )', text)
    chunks = []
    for i, section in enumerate(sections):
        section = section.strip()
        if not section:
            continue
        chunks.append({"id": f"{filepath}#chunk{i}", "text": prefix + section,
                       "chunk": i, "total_chunks": len(sections)})
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
    match = re.search(r'S(\d+)', name)
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
                    match = re.search(r'\[outcome:\s*([\w-]+)\]', line_lower)
                    if match:
                        outcome = match.group(1)
                if "result:" in line_lower or "\u2192" in line:
                    result_text = line.strip()[:200]
                for wl in re.findall(r'\[\[([\w/.-]+)\]\]', line):
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
    from google import genai
    api_key = os.environ.get(API_KEY_ENV_VAR)
    if not api_key:
        print(f"[ERR] {API_KEY_ENV_VAR} not set.")
        return None
    return genai.Client(api_key=api_key)


_local_ef = None

def _get_local_ef():
    global _local_ef
    if _local_ef is None:
        from chromadb.utils import embedding_functions
        _local_ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=LOCAL_MODEL)
    return _local_ef


def embed_texts_local(texts: list[str]) -> list[list[float]]:
    ef = _get_local_ef()
    return ef(texts)


def embed_texts(texts: list[str], client=None, task_type: str = "RETRIEVAL_DOCUMENT") -> list[list[float]]:
    if EMBEDDING_PROVIDER == "local":
        return embed_texts_local(texts)
    return embed_texts_gemini(texts, client, task_type)


def embed_texts_gemini(texts: list[str], client, task_type: str = "RETRIEVAL_DOCUMENT") -> list[list[float]]:
    import time
    from google.genai import types
    all_embeddings = []
    batch_size = 20
    total_batches = (len(texts) + batch_size - 1) // batch_size
    for batch_num, i in enumerate(range(0, len(texts), batch_size)):
        batch = texts[i:i + batch_size]
        result = client.models.embed_content(
            model=EMBEDDING_MODEL, contents=batch,
            config=types.EmbedContentConfig(output_dimensionality=EMBEDDING_DIMS, task_type=task_type),
        )
        all_embeddings.extend([e.values for e in result.embeddings])
        if batch_num < total_batches - 1:
            time.sleep(1.5)
    return all_embeddings


def embed_files(files: list[Path], collection, base_dir: Path, gemini_client):
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
    collection.upsert(
        ids=[c["id"] for c in all_chunks],
        embeddings=all_embeddings,
        documents=[c["text"] for c in all_chunks],
        metadatas=[{
            "source": c["source"], "file_type": c["file_type"],
            "modified": c["modified"], "embed_date": c["embed_date"],
            "session_num": c["session_num"], "chunk": c["chunk"],
            "total_chunks": c["total_chunks"],
            "outcome": c["outcome"], "outcome_result": c["outcome_result"],
        } for c in all_chunks],
    )
    return len(all_chunks)


def remove_deleted(deleted_keys: list[str], collection):
    if not deleted_keys:
        return
    for key in deleted_keys:
        results = collection.get(where={"source": key})
        if results["ids"]:
            collection.delete(ids=results["ids"])


def get_stats(collection) -> dict:
    return {"collection": collection.name, "total_chunks": collection.count()}


def main(brain_dir: Path = None, full: bool = False, dry_run: bool = False, stats_only: bool = False):
    """Run embedding. Called by Brain.embed() or CLI."""
    if brain_dir is not None:
        _p.set_brain_dir(brain_dir)
    base_dir = _p.BRAIN_DIR
    chroma_dir = _p.CHROMA_DIR
    manifest_file = _p.MANIFEST_FILE

    try:
        import chromadb
    except ImportError:
        print("[ERR] chromadb not installed. Run: pip install chromadb")
        return -1

    client = chromadb.PersistentClient(path=str(chroma_dir))
    core = client.get_or_create_collection(name=CORE_COLLECTION, metadata={"hnsw:space": "cosine"})

    if stats_only:
        s = get_stats(core)
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
    chunks_embedded = embed_files(changed, core, base_dir, gemini_client)
    print(f"Embedded {chunks_embedded} chunks from {len(changed)} files")

    if deleted:
        remove_deleted(deleted, core)
        print(f"Removed embeddings for {len(deleted)} deleted files")

    manifest_file.write_text(json.dumps(current_hashes, indent=2), encoding="utf-8")
    print(f"Manifest updated: {len(current_hashes)} files tracked")
    return chunks_embedded
