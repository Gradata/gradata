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
const { execSync } = require('child_process');
const fs = require('fs');
const os = require('os');
const path = require('path');

const cfg = require('./config.js');
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
const markerPath = path.join(os.tmpdir(), `aios-wrapup-done-S${sessionNum}.marker`);
const wrapUpAlreadyRan = sessionNum > 0 && fs.existsSync(markerPath);

// --- 0. Emit SESSION_END event --- guarantees every session shows in event log
try {
  const data = JSON.stringify({ session: sessionNum, date: today, hook: 'session-close-data' }).replace(/"/g, '\\"');
  execSync(
    `"${PYTHON}" "${SCRIPTS}/events.py" emit SESSION_END "hook:session-close" "${data}" "[\\"system:shutdown\\"]"`,
    { timeout: 5000, stdio: 'ignore' }
  );
} catch (e) {
  process.stderr.write(`[session-close] SESSION_END emit failed: ${e.message}\n`);
}

// --- 1. Confidence scoring (skip if wrap-up skill already ran) ---
if (!wrapUpAlreadyRan) try {
  const pyCmd = [
    'import sys; sys.path.insert(0, r"' + BRAIN + '/scripts")',
    'from wrap_up import update_confidence',
    'result = update_confidence()',
    'import json; print(json.dumps(result, default=str))',
  ].join('; ');

  execSync(
    `"${PYTHON}" -c "${pyCmd}"`,
    { timeout: 12000, stdio: 'ignore' }
  );
} catch (e) {
  // Silent — confidence scoring is best-effort
}

// --- 2. Session gate validator (skip if wrap-up skill already ran) ---
if (sessionNum > 0 && !wrapUpAlreadyRan) {
  // Detect session type: check if any OUTPUT events have prospect data
  let sessionType = 'systems'; // default to systems
  try {
    const lsPath = `${BRAIN}/loop-state.md`;
    if (fs.existsSync(lsPath)) {
      const lsContent = fs.readFileSync(lsPath, 'utf8').substring(0, 1000);
      const typeMatch = lsContent.match(/session[_-]?type:\s*(full|systems|sales|prospect|mixed)/i);
      if (typeMatch) {
        sessionType = typeMatch[1].toLowerCase() === 'systems' ? 'systems' : 'full';
      }
    }
  } catch (e) {}

  // Fallback: query OUTPUT events for prospect field
  if (sessionType === 'systems') {
    try {
      const checkCmd = `"${PYTHON}" -c "import sys; sys.path.insert(0, r'${BRAIN}/scripts'); import sqlite3; from paths import DB_PATH; conn = sqlite3.connect(str(DB_PATH)); rows = conn.execute(\\"SELECT data_json FROM events WHERE type='OUTPUT' AND session=${sessionNum}\\").fetchall(); conn.close(); import json; prospect = any(json.loads(r[0]).get('prospect') for r in rows if r[0]); print('full' if prospect else 'systems')"`;
      const detected = execSync(checkCmd, { timeout: 5000 }).toString().trim();
      if (detected === 'full') sessionType = 'full';
    } catch (e) {}
  }

  try {
    execSync(
      `"${PYTHON}" "${BRAIN}/scripts/wrap_up_validator.py" --session ${sessionNum} --date ${today} --session-type ${sessionType}`,
      { timeout: 30000, stdio: 'ignore' }
    );
  } catch (e) {
    // Silent — gate validation is best-effort, never blocks exit
  }
}
