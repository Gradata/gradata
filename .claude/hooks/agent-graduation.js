#!/usr/bin/env node
/**
 * agent-graduation.js -- PostToolUse hook (matcher: Agent)
 * Records agent outcomes for the graduation pipeline.
 *
 * When an agent completes, this hook captures:
 * - Agent type (from subagent_type or description)
 * - Output preview (first 200 chars of result)
 * - Outcome: "approved" for now (human review adds "edited"/"rejected" later)
 *
 * Data flows to: brain/agents/{type}/outcomes.jsonl via record_agent_outcome.py
 * Silent on failure -- never breaks the tool chain.
 */

const { execSync } = require('child_process');
const path = require('path');
const fs = require('fs');

const cfg = require('./config.js');
const PYTHON = cfg.PYTHON;
const SCRIPT = path.join(cfg.SCRIPTS, 'record_agent_outcome.py');

function readStdin() {
  try {
    if (process.stdin.isTTY) return null;
    return JSON.parse(fs.readFileSync(0, 'utf8'));
  } catch { return null; }
}

function extractAgentType(data) {
  const input = data.tool_input || {};

  // Direct subagent_type
  if (input.subagent_type) return input.subagent_type;

  // Extract from description (e.g., "Phase 8 competitive research")
  const desc = input.description || '';

  // Map common description patterns to agent types
  const patterns = [
    [/research/i, 'research'],
    [/audit/i, 'auditor'],
    [/review/i, 'reviewer'],
    [/explor/i, 'explorer'],
    [/debug/i, 'debugger'],
    [/plan/i, 'planner'],
    [/writ/i, 'writer'],
    [/test/i, 'tester'],
    [/build/i, 'builder'],
    [/prep/i, 'prep'],
  ];

  for (const [regex, type] of patterns) {
    if (regex.test(desc)) return type;
  }

  return 'general';
}

try {
  const data = readStdin();
  if (!data || data.tool_name !== 'Agent') process.exit(0);

  const agentType = extractAgentType(data);
  const output = (data.tool_output || '').toString();
  const preview = output.substring(0, 200).replace(/"/g, "'");

  // Skip if no meaningful output
  if (!preview || preview.length < 20) process.exit(0);

  // Detect session number
  let session = 0;
  try {
    const ls = fs.readFileSync(cfg.LOOP_STATE, 'utf8').substring(0, 200);
    const m = ls.match(/Session\s+(\d+)/);
    if (m) session = parseInt(m[1]) + 1;
  } catch {}

  // Record outcome via dedicated script (avoids inline Python quoting issues)
  const cmd = [
    `"${PYTHON}"`,
    `"${SCRIPT}"`,
    `--agent-type "${agentType}"`,
    `--preview "${preview}"`,
    `--outcome approved`,
    `--session ${session}`,
  ].join(' ');

  execSync(cmd, {
    timeout: 10000,
    stdio: ['pipe', 'pipe', 'pipe'],
  });

} catch (e) {
  // Surface errors so we know when graduation isn't running
  process.stderr.write(`[agent-graduation] error: ${e.message}\n`);
}
