#!/usr/bin/env node
/**
 * session-init-data.js — SessionStart hook
 * Guarantees baseline data exists for every session:
 *   1. Saves a minimal daily_metrics row (snapshot.py save-minimal)
 *   2. Materializes the Follow-Up Tracker with real data
 * Both run silently — failures never block startup.
 */
const { execSync } = require('child_process');

const PYTHON = 'C:/Users/olive/AppData/Local/Programs/Python/Python312/python.exe';
const BRAIN = 'C:/Users/olive/SpritesWork/brain';

// 1. Snapshot: ensure at least one daily_metrics row
try {
  execSync(
    `"${PYTHON}" "${BRAIN}/scripts/snapshot.py" save-minimal --session 0`,
    { timeout: 8000, stdio: 'ignore' }
  );
} catch (e) {
  // Silent — don't block startup
}

// 2. Materialize Follow-Up Tracker
try {
  execSync(
    `"${PYTHON}" "${BRAIN}/scripts/materialize_tracker.py" --write`,
    { timeout: 8000, stdio: 'ignore' }
  );
} catch (e) {
  // Silent — don't block startup
}

// 3. API Delta Sync (Pipedrive, Gmail, Calendar, Instantly, Fireflies)
// Only runs if .env has API keys configured. Skips missing sources silently.
// Timeout 30s — network calls to 5 APIs.
try {
  execSync(
    `"${PYTHON}" "${BRAIN}/scripts/api_sync.py" sync --quiet`,
    { timeout: 30000, stdio: 'ignore' }
  );
} catch (e) {
  // Silent — MCP fallback still available during session
}
