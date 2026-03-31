#!/usr/bin/env node
/**
 * dispatcher-pre-tool.js — Consolidates all PreToolUse hooks
 * Reduces CMD window flashes from 4 to 1 on Windows.
 *
 * Hooks dispatched (with matchers):
 *   1. quality-gate.js         (Write)
 *   2. brain-recall.js         (Write)
 *   3. mcp-health.js           (mcp__*)
 *   4. agent-precontext.js     (Agent)
 *   5. secret-scan.js          (Write|Edit) — BLOCKS writes containing secrets
 *   6. config-protection.js    (Write|Edit) — BLOCKS linter config weakening
 */
const path = require('path');
const cfg = require('./config.js');

const HOOKS_DIR = path.dirname(__filename);

const hooks = [
  { matcher: 'Write',  script: path.join(HOOKS_DIR, 'pre-tool', 'quality-gate.js'),     timeout: 3000 },
  { matcher: 'Write',  script: path.join(HOOKS_DIR, 'pre-tool', 'brain-recall.js'),     timeout: 5000 },
  { matcher: 'mcp__*', script: path.join(HOOKS_DIR, 'pre-tool', 'mcp-health.js'),       timeout: 3000 },
  { matcher: 'Agent',  script: path.join(HOOKS_DIR, 'pre-tool', 'agent-precontext.js'), timeout: 5000 },
  { matcher: 'Write|Edit', script: path.join(HOOKS_DIR, 'pre-tool', 'rule-enforcement.js'),      timeout: 2000 },
  { matcher: 'Write|Edit', script: path.join(HOOKS_DIR, 'pre-tool', 'secret-scan.js'),          timeout: 3000 },
  { matcher: 'Write|Edit', script: path.join(HOOKS_DIR, 'ecc', 'config-protection.js'), timeout: 3000 },
];

function matchesTool(matcher, toolName) {
  if (!matcher) return true;
  if (matcher === 'mcp__*') return toolName.startsWith('mcp__');
  const parts = matcher.split('|');
  return parts.includes(toolName);
}

let stdinBuf = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', d => stdinBuf += d);
process.stdin.on('end', () => {
  let toolName = '';
  try {
    const parsed = JSON.parse(stdinBuf);
    toolName = parsed.tool_name || '';
  } catch (_) {}

  const results = [];
  for (const hook of hooks) {
    if (!matchesTool(hook.matcher, toolName)) continue;
    try {
      const res = cfg.spawnSafe(process.execPath, [hook.script], {
        input: stdinBuf,
        timeout: hook.timeout,
        stdio: ['pipe', 'pipe', 'pipe'],
        encoding: 'utf8',
      });
      if (res.stdout && res.stdout.trim()) {
        try {
          const parsed = JSON.parse(res.stdout.trim());
          // PreToolUse hooks can block — if any says "deny", propagate it
          if (parsed.decision === 'block') {
            process.stdout.write(res.stdout.trim());
            return;
          }
          if (parsed.result) results.push(parsed.result);
        } catch (_) {
          results.push(res.stdout.trim());
        }
      }
      if (res.stderr && res.stderr.trim()) {
        process.stderr.write(`[dispatcher-pre-tool] ${path.basename(hook.script)}: ${res.stderr.trim()}\n`);
      }
    } catch (err) {
      process.stderr.write(`[dispatcher-pre-tool] ${path.basename(hook.script)} FAILED: ${err.message}\n`);
    }
  }
  if (results.length > 0) {
    process.stdout.write(JSON.stringify({ result: results.join('\n\n') }));
  }
});
