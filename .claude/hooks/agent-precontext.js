#!/usr/bin/env node
/**
 * agent-precontext.js -- PreToolUse hook (matcher: Agent)
 * Injects graduated agent rules into the agent's prompt before spawning.
 *
 * When an agent type has graduated PATTERN or RULE lessons, those lessons
 * are prepended to the agent's prompt so it starts with trained behavior.
 * This is the agent-level equivalent of brain.apply_brain_rules().
 *
 * Input: JSON from stdin with { tool_name, tool_input }
 * Output: JSON to stdout with modified tool_input (prompt prepended with rules)
 */

const path = require('path');
const fs = require('fs');

const cfg = require('./config.js');
const { execSafe } = cfg;
const PYTHON = cfg.PYTHON;

function readStdin() {
  try {
    if (process.stdin.isTTY) return null;
    return JSON.parse(fs.readFileSync(0, 'utf8'));
  } catch { return null; }
}

function extractAgentType(input) {
  if (input.subagent_type) return input.subagent_type;
  const desc = input.description || '';
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

  const input = data.tool_input || {};
  const agentType = extractAgentType(input);

  // Check if this agent type has a profile with graduated lessons
  const profilePath = path.join(cfg.BRAIN_DIR, 'agents', agentType, 'profile.json');
  if (!fs.existsSync(profilePath)) process.exit(0);

  try {
    const profile = JSON.parse(fs.readFileSync(profilePath, 'utf8'));
    // Only inject if agent has lessons
    if (!profile.lesson_count || profile.lesson_count === 0) process.exit(0);
  } catch { process.exit(0); }

  // Get the agent's graduated rules via Python
  const script = path.join(cfg.SCRIPTS, 'get_agent_context.py');
  if (!fs.existsSync(script)) process.exit(0);

  const result = execSafe(
    `"${PYTHON}" "${script}" --agent-type "${agentType}"`,
    { encoding: 'utf8', timeout: 5000, stdio: ['pipe', 'pipe', 'pipe'] }
  ).trim();

  if (!result || result.length < 10) process.exit(0);

  // Prepend agent training context to the prompt
  // PreToolUse hooks can modify tool_input by outputting JSON
  const modifiedInput = { ...input };
  modifiedInput.prompt = result + '\n\n---\n\n' + (input.prompt || '');

  // Output the modified tool input
  process.stdout.write(JSON.stringify(modifiedInput));

} catch (e) {
  // Silent — never block agent spawning
  process.exit(0);
}
