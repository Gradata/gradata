#!/usr/bin/env node
/**
 * cost-tracking.js — Stop hook
 * Logs session token estimates and cost to brain/metrics/cost.jsonl.
 * Also emits COST_EVENT via events.py.
 * Profile: all (always runs)
 */
const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const BRAIN_PATH = 'C:/Users/olive/SpritesWork/brain';
const COST_FILE = path.join(BRAIN_PATH, 'metrics', 'cost.jsonl');
const PYTHON = 'C:/Users/olive/AppData/Local/Programs/Python/Python312/python.exe';
const EVENTS_PY = path.join(BRAIN_PATH, 'scripts', 'events.py');

// Model pricing per million tokens (input/output)
const PRICING = {
  'opus':   { input: 15.00, output: 75.00 },
  'sonnet': { input: 3.00,  output: 15.00 },
  'haiku':  { input: 0.80,  output: 4.00 },
};

try {
  let input = '';
  if (!process.stdin.isTTY) {
    input = fs.readFileSync('/dev/stdin', 'utf8');
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

} catch (e) {
  // Silent failure
}
