#!/usr/bin/env node
/**
 * handoff-inject.js — SessionStart hook
 *
 * Pairs with user-prompt/handoff-watchdog.js: when the previous session
 * crossed GRADATA_HANDOFF_THRESHOLD and wrote a handoff doc to
 * <BRAIN_DIR>/handoffs/, this hook injects it on the next session's
 * SessionStart and moves the file to handoffs/consumed/ so it only
 * fires once.
 *
 * Mirrors gradata.contrib.patterns.handoff.pick_latest_unconsumed +
 * consume_handoff so SDK consumers and Claude Code agree on the file layout.
 *
 * Self-contained — BRAIN_DIR is resolved from BRAIN_DIR or GRADATA_BRAIN_DIR
 * env vars, falling back to ~/.gradata/brain.
 */
const fs = require('fs');
const path = require('path');
const os = require('os');

function resolveBrainDir() {
  const env = process.env.BRAIN_DIR || process.env.GRADATA_BRAIN_DIR;
  if (env) return env;
  return path.join(os.homedir(), '.gradata', 'brain');
}
const BRAIN_DIR = resolveBrainDir();

const handoffDir = path.join(BRAIN_DIR, 'handoffs');
if (!fs.existsSync(handoffDir)) process.exit(0);

// Pick latest *.handoff.md at the top level (skip consumed/).
let latest = null;
try {
  const entries = fs.readdirSync(handoffDir, { withFileTypes: true });
  let best = 0;
  for (const e of entries) {
    if (!e.isFile() || !e.name.endsWith('.handoff.md')) continue;
    const p = path.join(handoffDir, e.name);
    const m = fs.statSync(p).mtimeMs;
    if (m > best) { best = m; latest = p; }
  }
} catch (_) { process.exit(0); }

if (!latest) process.exit(0);

let body = '';
try { body = fs.readFileSync(latest, 'utf-8'); } catch (_) { process.exit(0); }
if (!body.trim()) process.exit(0);

// Move to consumed/ (preserve for audit — matches SDK consume_handoff).
try {
  const consumedDir = path.join(handoffDir, 'consumed');
  fs.mkdirSync(consumedDir, { recursive: true });
  fs.renameSync(latest, path.join(consumedDir, path.basename(latest)));
} catch (_) { /* best-effort: a stale file is preferable to breaking startup */ }

const injection = [
  '<handoff from-prev-session path="' + latest + '">',
  body.trim(),
  '</handoff>',
  '',
  'The previous session crossed the context-pressure threshold and left this',
  'handoff. Resume from "Next action" — do not re-plan.',
].join('\n');

process.stdout.write(JSON.stringify({ result: injection }));
