#!/usr/bin/env node
/**
 * session-init-data.js — SessionStart hook
 * Guarantees baseline data exists for every session:
 *   1. Emits HEALTH_CHECK event (proves event pipeline is alive)
 *   2. Saves a minimal daily_metrics row (snapshot.py save-minimal)
 *   3. Materializes the Follow-Up Tracker with real data
 *   4. API Delta Sync
 * All run silently — failures never block startup.
 */
const cfg = require('../config.js');
const { execSafe } = cfg;
const PYTHON = cfg.PYTHON;
const BRAIN = cfg.BRAIN_DIR;
const SCRIPTS = cfg.SCRIPTS;

// 1. Emit HEALTH_CHECK event — proves event pipeline works this session
try {
  execSafe(
    `"${PYTHON}" "${SCRIPTS}/events.py" emit HEALTH_CHECK "hook:session-init" "{\\"status\\":\\"ok\\",\\"hook\\":\\"session-init-data\\"}" "[\\"system:startup\\"]"`,
    { timeout: 5000, stdio: 'ignore' }
  );
} catch (e) {
  process.stderr.write(`[session-init] HEALTH_CHECK emit failed: ${e.message}\n`);
}

// 2. Snapshot: ensure at least one daily_metrics row
try {
  execSafe(
    `"${PYTHON}" "${BRAIN}/scripts/snapshot.py" save-minimal --session 0`,
    { timeout: 8000, stdio: 'ignore' }
  );
} catch (e) {
  // Silent — don't block startup
}

// 3. Materialize Follow-Up Tracker
try {
  execSafe(
    `"${PYTHON}" "${BRAIN}/scripts/materialize_tracker.py" --write`,
    { timeout: 8000, stdio: 'ignore' }
  );
} catch (e) {
  // Silent — don't block startup
}

// 4. API Delta Sync (Pipedrive, Gmail, Calendar, Instantly, Fireflies)
// Only runs if .env has API keys configured. Skips missing sources silently.
// Timeout 30s — network calls to 5 APIs.
try {
  execSafe(
    `"${PYTHON}" "${BRAIN}/scripts/api_sync.py" sync --quiet`,
    { timeout: 30000, stdio: 'ignore' }
  );
} catch (e) {
  // Silent — MCP fallback still available during session
}

// 5. Auto-compute deal health after sync (uses fresh Pipedrive data)
try {
  execSafe(
    `"${PYTHON}" "${BRAIN}/scripts/deal_calibration.py" --quiet`,
    { timeout: 8000, stdio: 'ignore' }
  );
} catch (e) {
  // Silent — deal health is informational, not critical
}

// 6. Ablation scheduling — check if any rule is due for validation
// Moved from SKILL.md Phase 0.5 to keep the pipeline alive without startup bloat.
try {
  const fs = require('fs');
  let sessionNum = 0;
  try {
    const ls = fs.readFileSync(`${BRAIN}/loop-state.md`, 'utf8').substring(0, 300);
    const m = ls.match(/Session\s+(\d+)/);
    if (m) sessionNum = parseInt(m[1]);
  } catch (_) {}
  if (sessionNum > 0) {
    execSafe(
      `"${PYTHON}" "${BRAIN}/scripts/ablation_lifecycle.py" check --session ${sessionNum}`,
      { timeout: 3000, stdio: 'ignore' }
    );
  }
} catch (e) {
  // Silent — ablation scheduling is best-effort
}
