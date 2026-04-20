#!/usr/bin/env python3
"""
audit_duplicates.py — Find duplicate/similar files in the codebase.

Scans source directories for files with similar names and/or content,
groups them into clusters, and suggests merge actions.

Usage:
    python brain/scripts/audit_duplicates.py [--fix]

Without --fix: report only (safe).
With --fix: interactive mode — prompts before each merge.
"""

import os
import sys
import hashlib
from pathlib import Path
from difflib import SequenceMatcher
from collections import defaultdict

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Directories to scan
SCAN_DIRS = [
    "src/gradata",
    "sdk/src",
    "sdk",
    ".claude/hooks",
    "brain/scripts",
    "tests",
]

# Skip these
IGNORE_DIRS = {
    "node_modules", "__pycache__", ".git", ".tmp", "dist", "build",
    ".egg-info", "venv", ".venv", "site-packages",
}

IGNORE_EXTENSIONS = {".pyc", ".pyo", ".so", ".dll", ".exe", ".bin"}


def normalize_name(filename: str) -> str:
    """Normalize filename for comparison."""
    name = Path(filename).stem
    # Strip " (1)" copy suffixes
    import re
    name = re.sub(r'\s*\(\d+\)\s*', '', name)
    # Normalize separators
    name = name.replace('-', '_').replace(' ', '_').lower()
    # Strip trailing numbers (version suffixes)
    name = re.sub(r'_*\d+$', '', name)
    return name


def name_similarity(a: str, b: str) -> float:
    """Similarity between two filenames (0.0 to 1.0)."""
    na, nb = normalize_name(a), normalize_name(b)
    if na == nb:
        return 1.0
    return SequenceMatcher(None, na, nb).ratio()


def content_similarity(path_a: Path, path_b: Path) -> float:
    """Similarity between file contents (0.0 to 1.0)."""
    try:
        a = path_a.read_text(encoding="utf-8", errors="replace")
        b = path_b.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return 0.0
    # Fast check: identical
    if a == b:
        return 1.0
    # For large files, compare first 5K chars
    if len(a) > 5000 or len(b) > 5000:
        a, b = a[:5000], b[:5000]
    return SequenceMatcher(None, a, b).ratio()


def file_hash(path: Path) -> str:
    """SHA256 of file content."""
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()[:12]
    except Exception:
        return "error"


def scan_files() -> list[Path]:
    """Collect all source files."""
    files = []
    for scan_dir in SCAN_DIRS:
        root = PROJECT_ROOT / scan_dir
        if not root.exists():
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            # Filter ignored dirs in-place
            dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS]
            for fname in filenames:
                fpath = Path(dirpath) / fname
                if fpath.suffix in IGNORE_EXTENSIONS:
                    continue
                files.append(fpath)
    return files


def find_duplicate_clusters(files: list[Path], name_threshold: float = 0.7) -> list[dict]:
    """Find clusters of similar files."""
    clusters = []
    used = set()

    for i, fa in enumerate(files):
        if i in used:
            continue
        group = [fa]
        for j, fb in enumerate(files):
            if j <= i or j in used:
                continue
            nsim = name_similarity(fa.name, fb.name)
            if nsim >= name_threshold:
                group.append(fb)
                used.add(j)

        if len(group) > 1:
            used.add(i)
            # Compute content similarity for the group
            pairs = []
            for a_idx in range(len(group)):
                for b_idx in range(a_idx + 1, len(group)):
                    csim = content_similarity(group[a_idx], group[b_idx])
                    nsim = name_similarity(group[a_idx].name, group[b_idx].name)
                    pairs.append({
                        "a": group[a_idx],
                        "b": group[b_idx],
                        "name_sim": nsim,
                        "content_sim": csim,
                    })
            clusters.append({
                "files": group,
                "pairs": pairs,
                "max_content_sim": max(p["content_sim"] for p in pairs),
            })

    # Also find exact content duplicates (different names)
    hash_map = defaultdict(list)
    for f in files:
        h = file_hash(f)
        if h != "error":
            hash_map[h].append(f)

    for h, dupes in hash_map.items():
        if len(dupes) > 1:
            # Check if already captured by name similarity
            dupe_set = set(str(d) for d in dupes)
            already = False
            for c in clusters:
                c_set = set(str(f) for f in c["files"])
                if dupe_set & c_set:
                    # Merge into existing cluster
                    for d in dupes:
                        if str(d) not in c_set:
                            c["files"].append(d)
                    already = True
                    break
            if not already:
                clusters.append({
                    "files": dupes,
                    "pairs": [{"a": dupes[0], "b": dupes[1], "name_sim": 0, "content_sim": 1.0}],
                    "max_content_sim": 1.0,
                })

    return sorted(clusters, key=lambda c: c["max_content_sim"], reverse=True)


def rel(p: Path) -> str:
    """Relative path from project root."""
    try:
        return str(p.relative_to(PROJECT_ROOT)).replace("\\", "/")
    except ValueError:
        return str(p)


def print_report(clusters: list[dict]):
    """Print duplicate report."""
    if not clusters:
        print("\n  No duplicates found.")
        return

    total_files = sum(len(c["files"]) for c in clusters)
    print(f"\n  Found {len(clusters)} duplicate clusters ({total_files} files total)\n")

    for i, cluster in enumerate(clusters, 1):
        max_sim = cluster["max_content_sim"]
        severity = "EXACT COPY" if max_sim > 0.95 else "HIGH" if max_sim > 0.7 else "MEDIUM" if max_sim > 0.5 else "LOW"

        print(f"  {'='*60}")
        print(f"  Cluster {i}: {severity} ({max_sim:.0%} content similarity)")
        print(f"  {'='*60}")

        for f in cluster["files"]:
            size = f.stat().st_size if f.exists() else 0
            h = file_hash(f)
            print(f"    {rel(f)}")
            print(f"      {size:,} bytes | hash: {h}")

        for pair in cluster["pairs"]:
            print(f"    ---")
            print(f"    {rel(pair['a'])}")
            print(f"      vs {rel(pair['b'])}")
            print(f"      Name: {pair['name_sim']:.0%} | Content: {pair['content_sim']:.0%}")

        # Suggest action
        if max_sim > 0.95:
            keeper = max(cluster["files"], key=lambda f: f.stat().st_mtime if f.exists() else 0)
            others = [f for f in cluster["files"] if f != keeper]
            print(f"\n    ACTION: Keep {rel(keeper)}, delete {', '.join(rel(o) for o in others)}")
        elif max_sim > 0.5:
            print(f"\n    ACTION: Review and merge manually. Diff the files to see what's different.")
        print()


def interactive_fix(clusters: list[dict]):
    """Interactive merge mode."""
    for i, cluster in enumerate(clusters, 1):
        max_sim = cluster["max_content_sim"]
        if max_sim < 0.5:
            continue

        print(f"\n  Cluster {i}: {len(cluster['files'])} files, {max_sim:.0%} similar")
        for j, f in enumerate(cluster["files"]):
            mtime = f.stat().st_mtime if f.exists() else 0
            from datetime import datetime
            ts = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
            print(f"    [{j}] {rel(f)} (modified: {ts})")

        if max_sim > 0.95:
            print("\n  These are near-identical. Which one to KEEP? (number, or 's' to skip)")
            choice = input("  > ").strip()
            if choice == 's':
                continue
            try:
                keep_idx = int(choice)
                keeper = cluster["files"][keep_idx]
                for j, f in enumerate(cluster["files"]):
                    if j != keep_idx and f.exists():
                        print(f"    Deleting {rel(f)}")
                        f.unlink()
                print(f"    Kept: {rel(keeper)}")
            except (ValueError, IndexError):
                print("    Skipped.")
        else:
            print("\n  These overlap but differ. Run `diff` to compare? (y/n/s)")
            choice = input("  > ").strip()
            if choice == 'y':
                a, b = cluster["files"][0], cluster["files"][1]
                os.system(f'diff --color "{a}" "{b}" | head -60')


def main():
    fix_mode = "--fix" in sys.argv

    print("\n  Duplicate File Audit")
    print(f"  Project: {PROJECT_ROOT}")
    print(f"  Scanning: {', '.join(SCAN_DIRS)}")

    files = scan_files()
    print(f"  Files found: {len(files)}")

    clusters = find_duplicate_clusters(files)

    if fix_mode:
        print_report(clusters)
        if clusters:
            print("\n  Entering interactive fix mode...\n")
            interactive_fix(clusters)
    else:
        print_report(clusters)
        if clusters:
            print("  Run with --fix for interactive merge mode.\n")


if __name__ == "__main__":
    main()
