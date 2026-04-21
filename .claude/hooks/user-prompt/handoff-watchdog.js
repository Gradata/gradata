#!/usr/bin/env node
/**
 * handoff-watchdog.js — UserPromptSubmit hook
 *
 * Wires the Python SDK's HandoffWatchdog pattern (contrib/patterns/handoff.py,
 * issue #127) into Claude Code's runtime.
 *
 * Statusline already writes used_pct to a bridge file each render; we read it
 * here instead of re-estimating from the transcript. When pressure crosses
 * GRADATA_HANDOFF_THRESHOLD (default 0.65), emit a directive telling the
 * current agent to write a handoff doc to <BRAIN_DIR>/handoffs/ before the
 * context compacts. Fires once per session (sentinel in os.tmpdir()).
 *
 * Silent on failure. Never blocks the prompt.
 */
const fs = require('fs');
const path = require('path');
const os = require('os');

const cfg = require('../config.js');

let input = '';
try { input = fs.readFileSync(0, 'utf-8'); } catch (_) { process.exit(0); }

let session = '';
try {
  const parsed = JSON.parse(input);
  session = parsed.session_id || '';
} catch (_) { /* silent */ }
if (!session) process.exit(0);

// Read threshold (default 0.65, overridable via env). Clamp to [0.10, 0.95]
// to match the SDK's HandoffWatchdog bounds.
function readThreshold() {
  const raw = process.env.GRADATA_HANDOFF_THRESHOLD;
  if (!raw) return 0.65;
  const v = parseFloat(raw);
  if (Number.isNaN(v) || v < 0.10 || v > 0.95) return 0.65;
  return v;
}
const threshold = readThreshold();

// Statusline bridge file — written on each render, carries buffer-normalized
// used_pct. If absent, the statusline hasn't run yet this session; bail.
const bridgePath = path.join(os.tmpdir(), `claude-ctx-${session}.json`);
if (!fs.existsSync(bridgePath)) process.exit(0);

let usedPct = 0;
try {
  const bridge = JSON.parse(fs.readFileSync(bridgePath, 'utf-8'));
  usedPct = Number(bridge.used_pct) || 0;
} catch (_) { process.exit(0); }

if (usedPct / 100 < threshold) process.exit(0);

const handoffDir = path.join(cfg.BRAIN_DIR, 'handoffs');
try { fs.mkdirSync(handoffDir, { recursive: true }); } catch (_) { /* silent */ }
const handoffPath = path.join(handoffDir, `${session}.handoff.md`);

// Self-healing: the handoff is "done" only when the file actually exists on
// disk. If the agent ignored the directive on the first fire, we keep
// nagging on every subsequent prompt until the file is written. The sentinel
// just tracks whether we've *ever* fired so we can soften the wording on
// retries.
if (fs.existsSync(handoffPath)) process.exit(0);

const sentinel = path.join(os.tmpdir(), `gradata-handoff-fired-${session}.flag`);
const isRetry = fs.existsSync(sentinel);
try { fs.writeFileSync(sentinel, String(Date.now())); } catch (_) { /* silent */ }

// Emit directive — the current agent sees this as system context and writes
// the handoff doc itself. Shape mirrors gradata.contrib.patterns.handoff
// so the SessionStart injector can parse it back on the next session.
const directive = [
  '<handoff-watchdog threshold="' + Math.round(threshold * 100) + '" used="' + usedPct + '"' + (isRetry ? ' retry="true"' : '') + '>',
  (isRetry
    ? 'REMINDER: the handoff doc was requested on a previous prompt but has not been written yet. Write it now before responding — context pressure is still at ' + usedPct + '%.'
    : 'Context pressure has crossed the handoff threshold (' + usedPct + '% used, threshold ' + Math.round(threshold * 100) + '%).'),
  'Write a compact resume doc to:',
  '  ' + handoffPath,
  '',
  'Shape (match exactly so the next session can parse it):',
  '  # Handoff — <task-id>',
  '  _from_: <agent-name>  _at_: <ISO-timestamp>',
  '  _rules_ts_: <ISO-timestamp>',
  '',
  '  ## Where we left off',
  '  <2-4 sentences on current state>',
  '',
  '  ## Next action',
  '  <the exact next step — command, file, or decision>',
  '',
  '  ## Open questions',
  '  - <anything unresolved>',
  '',
  '  ## Artifacts',
  '  - <PRs, file paths, commit SHAs>',
  '',
  'Do this now, then continue with the user\'s current message. The next',
  'Claude Code session will inject this doc on SessionStart so you pick up',
  'exactly where this one left off.',
  '</handoff-watchdog>',
].join('\n');

process.stdout.write(JSON.stringify({ result: directive }));