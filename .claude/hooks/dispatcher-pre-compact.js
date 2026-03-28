#!/usr/bin/env node
/**
 * dispatcher-pre-compact.js — Consolidates all PreCompact hooks
 * Reduces CMD window flashes from 2 to 1 on Windows.
 *
 * Hooks dispatched:
 *   1. check_learnings.py  (Python)
 *   2. post-compact.js     (Node)
 */
const path = require('path');
const cfg = require('./config.js');

const HOOKS_DIR = path.dirname(__filename);

const hooks = [
  { type: 'python', script: path.join(HOOKS_DIR, 'reflect', 'scripts', 'check_learnings.py'), timeout: 10000 },
  { type: 'node',   script: path.join(HOOKS_DIR, 'compact', 'post-compact.js'), timeout: 3000 },
];

let stdinBuf = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', d => stdinBuf += d);
process.stdin.on('end', () => {
  const results = [];
  for (const hook of hooks) {
    try {
      const cmd = hook.type === 'python' ? cfg.PYTHON : process.execPath;
      const args = [hook.script];
      const res = cfg.spawnSafe(cmd, args, {
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
        process.stderr.write(`[dispatcher-pre-compact] ${path.basename(hook.script)}: ${res.stderr.trim()}\n`);
      }
    } catch (err) {
      process.stderr.write(`[dispatcher-pre-compact] ${path.basename(hook.script)} FAILED: ${err.message}\n`);
    }
  }
  if (results.length > 0) {
    process.stdout.write(JSON.stringify({ result: results.join('\n\n') }));
  }
});
