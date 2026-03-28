#!/usr/bin/env node
/**
 * dispatcher-post-tool.js — Consolidates all PostToolUse hooks
 * Reduces CMD window flashes from 12 to 1 on Windows.
 *
 * Hooks dispatched (with matchers):
 *   1.  gate-emit.js           (Read)
 *   2.  secret-scan.js         (Write|Edit)
 *   3.  obsidian-autolink.js   (Write|Edit)
 *   4.  output-event.js        (Write|Edit)
 *   5.  codex-review.js        (Write|Edit)
 *   6.  qwen-lint.js           (Write|Edit)
 *   7.  arch-review.js         (Write|Edit)
 *   8.  agent-graduation.js    (Agent)
 *   9.  post_commit_reminder.py (Bash)
 *   10. delta-auto-tag.js      (no matcher — all tools)
 *   11. tool-failure-emit.js   (mcp__*)
 *   12. suggest-compact.js     (no matcher — all tools)
 *   13. behavior-triggers.js   (Write|Edit|Bash) — behavioral skill triggers
 *   14. rule-verify-post-tool.py (Write|Edit|Bash) — rule verifier advisory checks
 */
const path = require('path');
const cfg = require('./config.js');

const HOOKS_DIR = path.dirname(__filename);

const hooks = [
  { matcher: 'Read',       type: 'node',   script: path.join(HOOKS_DIR, 'post-tool', 'gate-emit.js'),          timeout: 3000 },
  { matcher: 'Write|Edit', type: 'node',   script: path.join(HOOKS_DIR, 'pre-tool', 'secret-scan.js'),         timeout: 3000 },
  { matcher: 'Write|Edit', type: 'node',   script: path.join(HOOKS_DIR, 'post-tool', 'obsidian-autolink.js'),  timeout: 3000 },
  { matcher: 'Write|Edit', type: 'node',   script: path.join(HOOKS_DIR, 'post-tool', 'output-event.js'),       timeout: 5000 },
  { matcher: 'Write|Edit', type: 'node',   script: path.join(HOOKS_DIR, 'post-tool', 'codex-review.js'),       timeout: 20000 },
  { matcher: 'Write|Edit', type: 'node',   script: path.join(HOOKS_DIR, 'post-tool', 'qwen-lint.js'),          timeout: 15000 },
  { matcher: 'Write|Edit', type: 'node',   script: path.join(HOOKS_DIR, 'post-tool', 'arch-review.js'),        timeout: 30000 },
  { matcher: 'Agent',      type: 'node',   script: path.join(HOOKS_DIR, 'post-tool', 'agent-graduation.js'),   timeout: 10000 },
  { matcher: 'Bash',       type: 'python', script: path.join(HOOKS_DIR, 'reflect', 'scripts', 'post_commit_reminder.py'), timeout: 5000 },
  { matcher: null,         type: 'node',   script: path.join(HOOKS_DIR, 'post-tool', 'delta-auto-tag.js'),     timeout: 5000 },
  { matcher: 'mcp__*',     type: 'node',   script: path.join(HOOKS_DIR, 'post-tool', 'tool-failure-emit.js'),  timeout: 5000 },
  { matcher: null,         type: 'node',   script: path.join(HOOKS_DIR, 'post-tool', 'suggest-compact.js'),    timeout: 3000 },
  { matcher: 'Write|Edit|Bash', type: 'node', script: path.join(HOOKS_DIR, 'post-tool', 'behavior-triggers.js'), timeout: 5000 },
  { matcher: 'Write|Edit|Bash', type: 'python', script: path.join(HOOKS_DIR, 'post-tool', 'rule-verify-post-tool.py'), timeout: 5000 },
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
      const cmd = hook.type === 'python' ? cfg.PYTHON : process.execPath;
      const res = cfg.spawnSafe(cmd, [hook.script], {
        input: stdinBuf,
        timeout: hook.timeout,
        stdio: ['pipe', 'pipe', 'pipe'],
        encoding: 'utf8',
      });
      if (res.stdout && res.stdout.trim()) {
        try {
          const parsed = JSON.parse(res.stdout.trim());
          if (parsed.result) results.push(parsed.result);
        } catch (_) {}
      }
      if (res.stderr && res.stderr.trim()) {
        process.stderr.write(`[dispatcher-post-tool] ${path.basename(hook.script)}: ${res.stderr.trim()}\n`);
      }
    } catch (err) {
      process.stderr.write(`[dispatcher-post-tool] ${path.basename(hook.script)} FAILED: ${err.message}\n`);
    }
  }
  if (results.length > 0) {
    process.stdout.write(JSON.stringify({ result: results.join('\n\n') }));
  }
});
