"""Autoresearch verify — code-health metric for Gradata SDK refactor loop.

Computes::

    health_score = loc + 2*duplicate_blocks + 3*complex_functions

over the MODIFIABLE scope (see program-codehealth.md). Runs correctness gate
(fast pytest subset), semantic gate (frozen paths untouched vs branch parent),
and api gate (public exports still importable).

Prints on success (exit 0)::

    health_score=<float>
    loc=<int>
    duplicate_blocks=<int>
    complex_functions=<int>

On failure prints the failing gate name and exits non-zero.
"""

from __future__ import annotations

import ast
import hashlib
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC = REPO_ROOT / "src" / "gradata"
PYTHON = sys.executable
TMP = REPO_ROOT / ".tmp" / "autoresearch"
TMP.mkdir(parents=True, exist_ok=True)

BRANCH_PARENT = "feat/token-optimization-autoresearch"

MODIFIABLE_GLOBS = [
    "src/gradata/contrib/patterns/**/*.py",
    "src/gradata/enhancements/**/*.py",
    "src/gradata/rules/**/*.py",
    "src/gradata/_db.py",
    "src/gradata/brain_inspection.py",
    "src/gradata/contrib/enhancements/**/*.py",
]

FROZEN_GLOBS = [
    "src/gradata/hooks/",
    "src/gradata/brain.py",
    "src/gradata/contrib/patterns/rag.py",
    "src/gradata/enhancements/reporting.py",
    "src/gradata/enhancements/rule_context_bridge.py",
    "domain/",
    "brain/",
    "lessons.md",
]

# Files within modifiable globs that are actually frozen (overlap carve-out).
MODIFIABLE_EXCLUDE = {
    "src/gradata/contrib/patterns/rag.py",
    "src/gradata/enhancements/reporting.py",
    "src/gradata/enhancements/rule_context_bridge.py",
}

# Public import surfaces verified by api_gate.
API_SMOKE_IMPORTS = [
    "gradata.contrib.patterns.orchestrator",
    "gradata.contrib.patterns.memory",
    "gradata.contrib.patterns.loop_detection",
    "gradata.contrib.patterns.q_learning_router",
    "gradata.contrib.patterns.tree_of_thoughts",
    "gradata.enhancements.diff_engine",
    "gradata.enhancements.meta_rules",
    "gradata.contrib.enhancements.quality_gates",
    "gradata.contrib.enhancements.truth_protocol",
    "gradata.rules.rule_graph",
    "gradata.rules.rule_tree",
    "gradata._db",
    "gradata.brain_inspection",
]

CC_THRESHOLD = 10  # cyclomatic complexity above this counts as "complex"
DUP_BLOCK_MIN_LINES = 6


def _collect_files() -> list[Path]:
    files: list[Path] = []
    seen: set[str] = set()
    for pattern in MODIFIABLE_GLOBS:
        for path in REPO_ROOT.glob(pattern):
            rel = path.relative_to(REPO_ROOT).as_posix()
            if rel in MODIFIABLE_EXCLUDE:
                continue
            if rel in seen:
                continue
            if not path.is_file():
                continue
            seen.add(rel)
            files.append(path)
    return sorted(files)


def _count_loc(files: list[Path]) -> int:
    total = 0
    for f in files:
        for line in f.read_text(encoding="utf-8", errors="ignore").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            total += 1
    return total


def _normalize_tokens(src: str) -> list[str]:
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return []
    tokens: list[str] = []
    for node in ast.walk(tree):
        tokens.append(type(node).__name__)
    return tokens


def _count_duplicate_blocks(files: list[Path]) -> int:
    """Sliding-window token hashes; any hash seen in ≥2 files counts once."""
    block_hashes: Counter[str] = Counter()
    for f in files:
        text = f.read_text(encoding="utf-8", errors="ignore")
        lines = text.splitlines()
        if len(lines) < DUP_BLOCK_MIN_LINES:
            continue
        # token-normalized line hashes
        norm_lines = []
        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            norm = "".join(c for c in stripped if not c.isspace())
            norm_lines.append(norm)
        for i in range(len(norm_lines) - DUP_BLOCK_MIN_LINES + 1):
            window = "|".join(norm_lines[i : i + DUP_BLOCK_MIN_LINES])
            h = hashlib.sha1(window.encode()).hexdigest()[:16]
            block_hashes[h] += 1
    return sum(1 for h, count in block_hashes.items() if count >= 2)


def _count_complex_functions(files: list[Path]) -> int:
    try:
        from radon.complexity import cc_visit
    except ImportError:
        return 0
    total = 0
    for f in files:
        try:
            src = f.read_text(encoding="utf-8", errors="ignore")
            for item in cc_visit(src):
                if item.complexity > CC_THRESHOLD:
                    total += 1
        except Exception:
            continue
    return total


def correctness_gate() -> bool:
    proc = subprocess.run(
        [
            PYTHON,
            "-m",
            "pytest",
            "tests/test_brain.py",
            "tests/test_core_behavioral.py",
            "-q",
            "--tb=no",
            "-x",
        ],
        capture_output=True,
        text=True,
        timeout=300,
        cwd=str(REPO_ROOT),
    )
    if proc.returncode != 0:
        sys.stderr.write(proc.stdout[-2000:])
        sys.stderr.write(proc.stderr[-2000:])
        return False
    return True


def semantic_gate() -> bool:
    for path in FROZEN_GLOBS:
        proc = subprocess.run(
            ["git", "diff", "--name-only", BRANCH_PARENT, "--", path],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
        )
        if proc.stdout.strip():
            sys.stderr.write(f"semantic_gate violation in {path}:\n{proc.stdout}\n")
            return False
    return True


def api_gate() -> bool:
    code = f"import sys\nsys.path.insert(0, {str(SRC.parent)!r})\n" + "\n".join(
        f"import {mod}" for mod in API_SMOKE_IMPORTS
    )
    proc = subprocess.run(
        [PYTHON, "-c", code],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=str(REPO_ROOT),
    )
    if proc.returncode != 0:
        sys.stderr.write(f"api_gate import failure:\n{proc.stderr}\n")
        return False
    return True


def main() -> int:
    if not correctness_gate():
        print("correctness_gate=FAIL")
        return 2
    if not semantic_gate():
        print("semantic_gate=FAIL")
        return 3
    if not api_gate():
        print("api_gate=FAIL")
        return 4

    files = _collect_files()
    loc = _count_loc(files)
    dup = _count_duplicate_blocks(files)
    cc = _count_complex_functions(files)
    score = loc + 2 * dup + 3 * cc

    print(f"health_score={score}")
    print(f"loc={loc}")
    print(f"duplicate_blocks={dup}")
    print(f"complex_functions={cc}")
    print(f"files_scanned={len(files)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
