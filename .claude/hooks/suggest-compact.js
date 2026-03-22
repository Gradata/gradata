#!/usr/bin/env node
/**
 * suggest-compact.js — PostToolUse hook
 * Counts tool calls. At 50, suggests compaction. Then every 25 after.
 * Profile: standard, strict
 */
const fs = require('fs');
const path = require('path');
const os = require('os');

const PROFILE = process.env.AIOS_HOOK_PROFILE || 'standard';
if (PROFILE === 'minimal') process.exit(0);

const COUNTER_FILE = path.join(os.tmpdir(), 'aios-tool-count.json');
const FIRST_THRESHOLD = 50;
const REPEAT_INTERVAL = 25;

try {
  let state = { count: 0, last_suggested: 0 };
  if (fs.existsSync(COUNTER_FILE)) {
    state = JSON.parse(fs.readFileSync(COUNTER_FILE, 'utf8'));
  }

  state.count += 1;

  const shouldSuggest =
    (state.count >= FIRST_THRESHOLD && state.last_suggested === 0) ||
    (state.last_suggested > 0 && state.count - state.last_suggested >= REPEAT_INTERVAL);

  if (shouldSuggest) {
    state.last_suggested = state.count;
    fs.writeFileSync(COUNTER_FILE, JSON.stringify(state));
    // Output suggestion to stderr (visible to user)
    process.stderr.write(`\n[compact] ${state.count} tool calls this session. Consider /compact at a logical boundary.\n`);
  } else {
    fs.writeFileSync(COUNTER_FILE, JSON.stringify(state));
  }
} catch (e) {
  // Silent failure — hooks should never block
}
