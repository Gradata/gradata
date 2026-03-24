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

const PYTHON = 'C:/Users/olive/AppData/Local/Programs/Python/Python312/python.exe';
const BRAIN = 'C:/Users/olive/SpritesWork/brain';

// --- Detect session number from loop-state.md ---
let sessionNum = 0;
try {
  const ls = fs.readFileSync(`${BRAIN}/loop-state.md`, 'utf8').substring(0, 300);
  const m = ls.match(/Session\s+(\d+)/);
  if (m) sessionNum = parseInt(m[1]) + 1; // loop-state records LAST closed, we're closing current
} catch (e) {}

const today = new Date().toISOString().split('T')[0]; // YYYY-MM-DD

// --- 1. Confidence scoring ---
try {
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

// --- 2. Session gate validator ---
if (sessionNum > 0) {
  try {
    execSync(
      `"${PYTHON}" "${BRAIN}/scripts/wrap_up_validator.py" --session ${sessionNum} --date ${today} --session-type full`,
      { timeout: 30000, stdio: 'ignore' }
    );
  } catch (e) {
    // Silent — gate validation is best-effort, never blocks exit
  }
}
