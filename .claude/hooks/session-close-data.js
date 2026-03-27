#!/usr/bin/env node
/**
 * session-close-data.js — Stop hook
 * Runs TWO things automatically on every session close:
 * 1. Confidence scoring (update_confidence)
 * 2. Session gate validator (wrap_up_validator.py)
 *
 * This ensures gate data is always fresh in the statusline,
 * even if the wrap-up skill gets skipped or rushed.
 * Silent on failure — never blocks session end.
 */
const fs = require('fs');
const os = require('os');
const path = require('path');

const cfg = require('./config.js');
const { execSafe } = cfg;
const PYTHON = cfg.PYTHON;
const BRAIN = cfg.BRAIN_DIR;
const SCRIPTS = cfg.SCRIPTS;

// --- Detect session number from loop-state.md ---
let sessionNum = 0;
try {
  const ls = fs.readFileSync(`${BRAIN}/loop-state.md`, 'utf8').substring(0, 300);
  const m = ls.match(/Session\s+(\d+)/);
  if (m) sessionNum = parseInt(m[1]); // loop-state is updated by wrap-up to CURRENT session
} catch (e) {}

const today = new Date().toISOString().split('T')[0]; // YYYY-MM-DD

// --- Check wrap-up-completed marker (P1-5 guard) ---
const markerPath = path.join(os.tmpdir(), `gradata-wrapup-done-S${sessionNum}.marker`);
const wrapUpAlreadyRan = sessionNum > 0 && fs.existsSync(markerPath);

// --- 0. Emit SESSION_END event --- guarantees every session shows in event log
try {
  const data = JSON.stringify({ session: sessionNum, date: today, hook: 'session-close-data' }).replace(/"/g, '\\"');
  execSafe(
    `"${PYTHON}" "${SCRIPTS}/events.py" emit SESSION_END "hook:session-close" "${data}" "[\\"system:shutdown\\"]"`,
    { timeout: 5000, stdio: 'ignore' }
  );
} catch (e) {
  process.stderr.write(`[session-close] SESSION_END emit failed: ${e.message}\n`);
}

// --- 1. Detect session type (needed for both confidence scoring and gate validation) ---
// Maps to SDK categories: "sales" | "system" | "pipeline" | "mixed"
let sessionType = 'system'; // default to system
try {
  const lsPath = `${BRAIN}/loop-state.md`;
  if (fs.existsSync(lsPath)) {
    const lsContent = fs.readFileSync(lsPath, 'utf8').substring(0, 1000);
    const typeMatch = lsContent.match(/session[_-]?type:\s*(full|systems?|sales|prospect|pipeline|mixed)/i);
    if (typeMatch) {
      const raw = typeMatch[1].toLowerCase();
      // Normalize: "full"/"prospect"/"sales" -> "sales", "systems" -> "system"
      sessionType = (raw === 'full' || raw === 'prospect' || raw === 'sales') ? 'sales'
        : (raw === 'systems') ? 'system' : raw;
    }
  }
} catch (e) {}

// Fallback: query OUTPUT events for prospect field
if (sessionType === 'system' && sessionNum > 0) {
  try {
    const checkCmd = `"${PYTHON}" -c "import sys; sys.path.insert(0, r'${BRAIN}/scripts'); import sqlite3; from paths import DB_PATH; conn = sqlite3.connect(str(DB_PATH)); rows = conn.execute(\\"SELECT data_json FROM events WHERE type='OUTPUT' AND session=${sessionNum}\\").fetchall(); conn.close(); import json; prospect = any(json.loads(r[0]).get('prospect') for r in rows if r[0]); print('sales' if prospect else 'system')"`;
    const detected = execSafe(checkCmd, { timeout: 5000 }).toString().trim();
    if (detected === 'sales') sessionType = 'sales';
  } catch (e) {}
}

// --- 2. Confidence scoring (skip if wrap-up skill already ran) ---
if (!wrapUpAlreadyRan) try {
  const pyCmd = [
    'import sys; sys.path.insert(0, r"' + BRAIN + '/scripts")',
    'from wrap_up import update_confidence',
    'result = update_confidence(session_type="' + sessionType + '")',
    'import json; print(json.dumps(result, default=str))',
  ].join('; ');

  execSafe(
    `"${PYTHON}" -c "${pyCmd}"`,
    { timeout: 12000, stdio: 'ignore' }
  );
} catch (e) {
  // Silent — confidence scoring is best-effort
}

// --- 3. Session gate validator ---
// If wrap-up skill ran (marker exists), it already validated to 100%.
// Only re-validate if wrap-up was skipped (safety net).
if (sessionNum > 0 && !wrapUpAlreadyRan) {
  try {
    const result = execSafe(
      `"${PYTHON}" "${BRAIN}/scripts/wrap_up_validator.py" --session ${sessionNum} --date ${today} --session-type ${sessionType} --json`,
      { timeout: 30000, stdio: ['pipe', 'pipe', 'pipe'] }
    ).toString().trim();

    // Parse result and warn if not 100%
    try {
      const parsed = JSON.parse(result);
      const passed = parsed.passed || 0;
      const total = parsed.total || 0;
      if (total > 0 && passed < total) {
        const failed = (parsed.failures || []).slice(0, 3).join(', ');
        process.stderr.write(
          `\n⚠️  GATE WARNING: ${passed}/${total} passed. Wrap-up may have been skipped.\n` +
          `   Failing: ${failed}\n` +
          `   Run wrap-up before ending session for 100% gates.\n`
        );
      }
    } catch (parseErr) {
      // Validator ran but output wasn't JSON — still OK
    }
  } catch (e) {
    // Silent — gate validation is best-effort on exit
  }
} else if (wrapUpAlreadyRan) {
  // Wrap-up already validated to 100% — no re-run needed
}
