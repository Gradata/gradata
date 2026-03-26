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

// Skip in reviewer terminal — reviewer's review agents don't graduate in the work brain
if (process.env.AIOS_ROLE === 'reviewer') { process.exit(0); }

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
  // Handle both inline output and background agent output (file path or summary)
  let output = '';
  const rawOutput = data.tool_output || data.tool_result || '';
  if (typeof rawOutput === 'object' && rawOutput !== null) {
    // Background agents return structured result with summary/output_file
    output = rawOutput.summary || rawOutput.result || rawOutput.output || JSON.stringify(rawOutput).substring(0, 500);
  } else {
    output = rawOutput.toString();
  }
  const preview = output.substring(0, 200).replace(/"/g, "'").replace(/\n/g, ' ');

  // Skip if no meaningful output — but be lenient for background agents
  // Background agents may have short summaries like "Agent completed"
  if (!preview || preview.length < 10) process.exit(0);

  // Detect session number from loop-state (current session, not +1)
  // loop-state is updated at wrap-up to the CURRENT session number
  let session = 0;
  try {
    const ls = fs.readFileSync(cfg.LOOP_STATE, 'utf8').substring(0, 300);
    const m = ls.match(/Session\s+(\d+)/);
    if (m) session = parseInt(m[1]);
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
