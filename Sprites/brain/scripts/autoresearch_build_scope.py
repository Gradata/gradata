"""One-time setup for autoresearch consolidation loop.

Runs pytest under coverage, then writes a whitelist of files with >= THRESHOLD
line coverage. The autoresearch agent is only permitted to modify files in the
whitelist — low-coverage files stay read-only to prevent silent regressions.

Output:
    .tmp/autoresearch/consolidation/scope_whitelist.txt  (one path per line)
    .tmp/autoresearch/consolidation/scope_report.json    (full report)

Usage:
    python brain/scripts/autoresearch_build_scope.py [--threshold 80]
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

os.environ["PYTHONUTF8"] = "1"

OUT_DIR = Path(".tmp/autoresearch/consolidation")
WHITELIST = OUT_DIR / "scope_whitelist.txt"
REPORT = OUT_DIR / "scope_report.json"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--threshold", type=float, default=80.0,
                    help="Min line coverage %% to include in whitelist (default 80)")
    ap.add_argument("--source", default="src/gradata",
                    help="Source directory to measure (default src/gradata)")
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"[scope] running coverage over {args.source}...")
    env = {**os.environ, "PYTHONUTF8": "1"}

    r1 = subprocess.run(
        ["coverage", "run", f"--source={args.source}", "-m", "pytest", "tests/",
         "--ignore=tests/test_rule_to_hook.py", "-q", "--tb=no", "--no-header"],
        capture_output=True, text=True, env=env,
        encoding="utf-8", errors="replace",
    )
    r2 = subprocess.run(
        ["coverage", "run", f"--source={args.source}", "-a",
         "-m", "pytest", "tests/test_rule_to_hook.py", "-q", "--tb=no", "--no-header"],
        capture_output=True, text=True, env=env,
        encoding="utf-8", errors="replace",
    )
    for i, r in enumerate((r1, r2), 1):
        if r.returncode not in (0, 1, 5):  # 0=ok, 1=tests_failed (we accept), 5=no_tests
            print(f"[scope] pytest leg {i} errored (rc={r.returncode}).", file=sys.stderr)
            print(r.stdout[-1500:], file=sys.stderr)
            return 1

    j = subprocess.run(
        ["coverage", "json", "-o", "-", "--quiet"],
        capture_output=True, text=True,
    )
    if j.returncode != 0 or not j.stdout.strip():
        print("[scope] coverage json failed.", file=sys.stderr)
        return 2

    data = json.loads(j.stdout)
    files = data.get("files", {})
    whitelist: list[str] = []
    rows = []
    for path, info in files.items():
        pct = info.get("summary", {}).get("percent_covered", 0.0)
        rows.append((path, round(pct, 1)))
        if pct >= args.threshold:
            whitelist.append(path)

    rows.sort(key=lambda r: r[1])

    WHITELIST.write_text("\n".join(sorted(whitelist)) + "\n", encoding="utf-8")
    REPORT.write_text(json.dumps({
        "threshold": args.threshold,
        "total_files": len(files),
        "whitelisted": len(whitelist),
        "excluded": len(files) - len(whitelist),
        "rows": rows,
    }, indent=2), encoding="utf-8")

    print(f"[scope] threshold={args.threshold}%  "
          f"whitelist={len(whitelist)}/{len(files)} files  "
          f"wrote {WHITELIST}")
    print(f"[scope] lowest-coverage excluded (first 10):")
    for p, pct in rows[:10]:
        if pct < args.threshold:
            print(f"  {pct:>5.1f}%  {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
