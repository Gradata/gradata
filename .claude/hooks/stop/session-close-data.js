#!/usr/bin/env node
/**
 * session-close-data.js — Stop hook
 * Lean version: emits SESSION_END event + meta-rule discovery.
 * Confidence scoring and gate validation are handled by wrap-up skill.
 * session-persist.js covers abrupt exits.
 */
const fs = require('fs');
const cfg = require('../config.js');
const { execSafe } = cfg;
const PYTHON = cfg.PYTHON;
const BRAIN = cfg.BRAIN_DIR;
const SCRIPTS = cfg.SCRIPTS;

// --- Detect session number from loop-state.md ---
let sessionNum = 0;
try {
  const ls = fs.readFileSync(`${BRAIN}/loop-state.md`, 'utf8').substring(0, 300);
  const m = ls.match(/Session\s+(\d+)/);
  if (m) sessionNum = parseInt(m[1]);
} catch (e) {}

const today = new Date().toISOString().split('T')[0];

// --- 1. Emit SESSION_END event (guarantees every session shows in event log) ---
try {
  const data = JSON.stringify({ session: sessionNum, date: today, hook: 'session-close-data' }).replace(/"/g, '\\"');
  execSafe(
    `"${PYTHON}" "${SCRIPTS}/events.py" emit SESSION_END "hook:session-close" "${data}" "[\\"system:shutdown\\"]"`,
    { timeout: 5000, stdio: 'ignore' }
  );
} catch (e) {
  process.stderr.write(`[session-close] SESSION_END emit failed: ${e.message}\n`);
}

// --- 2. Meta-rule discovery (best-effort, accumulates across sessions) ---
try {
  const metaPyCmd = [
    'import sys; sys.path.insert(0, r"' + BRAIN + '/scripts")',
    'from paths import SDK_SRC, LESSONS_FILE, DB_PATH',
    'sys.path.insert(0, str(SDK_SRC))',
    'from gradata.enhancements.meta_rules import discover_meta_rules, save_meta_rules, parse_lessons_from_markdown',
    'text = LESSONS_FILE.read_text(encoding="utf-8") if LESSONS_FILE.exists() else ""',
    'lessons = parse_lessons_from_markdown(text)',
    'metas = discover_meta_rules(lessons, current_session=' + sessionNum + ')',
    'saved = save_meta_rules(DB_PATH, metas) if metas else 0',
    'print(f"{len(metas)} meta-rules discovered, {saved} saved")',
  ].join('; ');

  execSafe(
    `"${PYTHON}" -c "${metaPyCmd}"`,
    { timeout: 10000, stdio: 'ignore' }
  );
} catch (e) {
  // Silent — meta-rule discovery is best-effort
}
