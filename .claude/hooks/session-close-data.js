#!/usr/bin/env node
/**
 * session-close-data.js — Stop hook
 * Runs confidence scoring automatically so it happens even if Claude skips wrap-up.
 * Calls wrap_up.py's update_confidence() via a Python one-liner.
 * Silent on failure — never blocks session end.
 */
const { execSync } = require('child_process');

const PYTHON = 'C:/Users/olive/AppData/Local/Programs/Python/Python312/python.exe';
const BRAIN = 'C:/Users/olive/SpritesWork/brain';

try {
  // Run update_confidence directly — wrap_up.py requires --session which we
  // may not know. Instead, import the function and let it auto-detect session.
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
