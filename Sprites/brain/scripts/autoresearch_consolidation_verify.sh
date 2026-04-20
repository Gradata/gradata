#!/usr/bin/env bash
# Autoresearch verify — composite metric + strengthened cheat-proof gate.
#
# Emits 4 components on stdout (all lower-is-better):
#   DURATION   - total pytest wall-clock (s)
#   LOC        - total source LoC (lower = less duplication)
#   IMPORTS    - intra-package import edges in src/gradata/ (lower = less coupling)
#   FILES      - source file count
#
# Gate (commit is KEEP-eligible only if ALL pass):
#   1. pytest: pass/skip/fail counts match baseline
#   2. ruff error count does not EXCEED baseline (override with BASELINE_RUFF)
#   3. smoke test exits 0
#
# Windows quirks handled:
#   - PYTHONUTF8=1 forces UTF-8 decoding for subprocess readers
#   - test_rule_to_hook.py run in isolation (order-pollution workaround)

set -u
export PYTHONUTF8=1

EXPECTED_PASSED="${EXPECTED_PASSED:-3672}"
EXPECTED_SKIPPED="${EXPECTED_SKIPPED:-21}"
EXPECTED_FAILED="${EXPECTED_FAILED:-0}"
BASELINE_RUFF="${BASELINE_RUFF:-64}"

parse_count() {
  echo "$1" | grep -oE "[0-9]+ $2" | tail -1 | grep -oE '[0-9]+' || echo 0
}

# ---- Gate 1: pytest (split for order-pollution workaround) ----
START=$(python -c "import time; print(time.time())")
MAIN_OUT=$(pytest tests/ -q --no-header --tb=no \
  --ignore=tests/test_rule_to_hook.py 2>&1) || true
ISOL_OUT=$(pytest tests/test_rule_to_hook.py -q --no-header --tb=no 2>&1) || true
END=$(python -c "import time; print(time.time())")
DUR=$(python -c "print(f'{$END - $START:.3f}')")

PASSED=$(( $(parse_count "$MAIN_OUT" passed) + $(parse_count "$ISOL_OUT" passed) ))
SKIPPED=$(( $(parse_count "$MAIN_OUT" skipped) + $(parse_count "$ISOL_OUT" skipped) ))
FAILED=$(( $(parse_count "$MAIN_OUT" failed) + $(parse_count "$ISOL_OUT" failed) ))
ERRORS=$(( $(parse_count "$MAIN_OUT" error) + $(parse_count "$ISOL_OUT" error) ))

# ---- Gate 2: ruff (count must not exceed baseline) ----
RUFF_OUT=$(ruff check src/gradata/ --output-format=concise --exit-zero 2>&1)
RUFF_COUNT=$(echo "$RUFF_OUT" | grep -cE '^[^[:space:]].*:[0-9]+:[0-9]+:' || echo 0)

# ---- Gate 3: smoke test ----
SMOKE_OUT=$(python brain/scripts/autoresearch_smoke_test.py 2>&1) || SMOKE_RC=$?
SMOKE_RC="${SMOKE_RC:-0}"

# ---- Metric: LoC ----
LOC=$(python - <<'PY'
import os, pathlib
total = 0
exts = {'.py', '.ts', '.tsx', '.js', '.jsx'}
for root, _, files in os.walk('src'):
    if any(s in root for s in ('__pycache__', 'node_modules', '.venv', 'dist', 'build')):
        continue
    for f in files:
        if pathlib.Path(f).suffix in exts:
            try:
                total += sum(1 for _ in open(os.path.join(root, f), encoding='utf-8', errors='ignore'))
            except OSError:
                pass
print(total)
PY
)

# ---- Metric: intra-package import edges (live) ----
IMPORTS=$(python - <<'PY'
import ast, os, pathlib
pkg_root = pathlib.Path('src/gradata')
count = 0
for p in pkg_root.rglob('*.py'):
    if '__pycache__' in p.parts:
        continue
    try:
        tree = ast.parse(p.read_text(encoding='utf-8', errors='ignore'))
    except SyntaxError:
        continue
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module and node.module.startswith('gradata'):
                count += len(node.names) or 1
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith('gradata'):
                    count += 1
print(count)
PY
)

# ---- Metric: source file count ----
FILES=$(python - <<'PY'
import os, pathlib
count = 0
exts = {'.py', '.ts', '.tsx', '.js', '.jsx'}
for root, _, files in os.walk('src'):
    if any(s in root for s in ('__pycache__', 'node_modules', '.venv', 'dist', 'build')):
        continue
    for f in files:
        if pathlib.Path(f).suffix in exts:
            count += 1
print(count)
PY
)

echo "DURATION=$DUR"
echo "LOC=$LOC"
echo "IMPORTS=$IMPORTS"
echo "FILES=$FILES"
echo "PASSED=$PASSED"
echo "SKIPPED=$SKIPPED"
echo "FAILED=$FAILED"
echo "ERRORS=$ERRORS"
echo "RUFF_COUNT=$RUFF_COUNT"
echo "RUFF_BASELINE=$BASELINE_RUFF"
echo "SMOKE_RC=$SMOKE_RC"

# ---- Gate ----
GATE_FAIL=0
FAIL_REASONS=""

if [ "$PASSED" != "$EXPECTED_PASSED" ] \
  || [ "$SKIPPED" != "$EXPECTED_SKIPPED" ] \
  || [ "$FAILED" != "$EXPECTED_FAILED" ] \
  || [ "$ERRORS" != "0" ]; then
  GATE_FAIL=1
  FAIL_REASONS="$FAIL_REASONS pytest(pass=$PASSED/skip=$SKIPPED/fail=$FAILED/err=$ERRORS)"
fi

if [ "$RUFF_COUNT" -gt "$BASELINE_RUFF" ]; then
  GATE_FAIL=1
  FAIL_REASONS="$FAIL_REASONS ruff($RUFF_COUNT>$BASELINE_RUFF)"
fi

if [ "$SMOKE_RC" != "0" ]; then
  GATE_FAIL=1
  FAIL_REASONS="$FAIL_REASONS smoke(rc=$SMOKE_RC)"
fi

if [ "$GATE_FAIL" = "1" ]; then
  echo "STATUS=crash"
  echo "FAIL_REASONS=$FAIL_REASONS"
  echo "--- pytest main tail ---"; echo "$MAIN_OUT" | tail -20
  echo "--- pytest isolated tail ---"; echo "$ISOL_OUT" | tail -10
  echo "--- ruff tail ---"; echo "$RUFF_OUT" | tail -10
  echo "--- smoke tail ---"; echo "$SMOKE_OUT" | tail -10
  exit 1
fi

echo "STATUS=ok"
exit 0
