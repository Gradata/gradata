#!/usr/bin/env node
/**
 * cost-tracking.js — Stop hook
 * Logs session token estimates and cost to brain/metrics/cost.jsonl.
 * Also emits COST_EVENT via events.py.
 * Profile: all (always runs)
 */
const fs = require('fs');
const path = require('path');
const cfg = require('../config.js');
const { execSafe } = cfg;
const BRAIN_PATH = cfg.BRAIN_DIR;
const COST_FILE = path.join(BRAIN_PATH, 'metrics', 'cost.jsonl');
const PYTHON = cfg.PYTHON;

// Model pricing per million tokens (input/output)
const PRICING = {
  'opus':   { input: 15.00, output: 75.00 },
  'sonnet': { input: 3.00,  output: 15.00 },
  'haiku':  { input: 0.80,  output: 4.00 },
};

try {
  let input = '';
  if (!process.stdin.isTTY) {
    try { input = fs.readFileSync(0, 'utf8'); } catch (_) { /* no stdin */ }
  }

  // Parse session info from stdin if available
  let sessionData = {};
  try { sessionData = JSON.parse(input); } catch (e) { /* no stdin data */ }

  const model = sessionData.model || 'opus';
  const inputTokens = sessionData.input_tokens || 0;
  const outputTokens = sessionData.output_tokens || 0;

  const pricing = PRICING[model] || PRICING['opus'];
  const cost = (inputTokens / 1_000_000 * pricing.input) + (outputTokens / 1_000_000 * pricing.output);

  const entry = {
    ts: new Date().toISOString(),
    session: sessionData.session || 0,
    model,
    input_tokens: inputTokens,
    output_tokens: outputTokens,
    estimated_cost_usd: Math.round(cost * 1000) / 1000,
  };

  // Ensure directory exists
  const dir = path.dirname(COST_FILE);
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });

  // Append to cost.jsonl
  fs.appendFileSync(COST_FILE, JSON.stringify(entry) + '\n');

  // Emit COST_EVENT via events.py CLI
  const entryStr = JSON.stringify(entry);
  try {
    execSafe(
      `"${PYTHON}" "${BRAIN_PATH}/scripts/events.py" emit COST_EVENT hook:cost-tracking '${entryStr}'`,
      { timeout: 3000, stdio: 'ignore' }
    );
  } catch (_) {
    // COST_EVENT emission is best-effort
  }

} catch (e) {
  // Silent failure
}
