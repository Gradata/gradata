#!/usr/bin/env node
/**
 * dispatcher-session-start.js — Consolidates all SessionStart hooks
 * Reduces CMD window flashes to 1 on Windows.
 *
 * Hooks dispatched:
 *   1. session_start_reminder.py  (Python)
 *   2. session-init-data.js       (Node)
 *   3. config-validate.js         (Node) — validates settings.json integrity
 */
const path = require('path');
const cfg = require('./config.js');

const HOOKS_DIR = path.dirname(__filename);

const hooks = [
  { type: 'python', script: path.join(HOOKS_DIR, 'reflect', 'scripts', 'session_start_reminder.py'), timeout: 10000 },
  { type: 'node',   script: path.join(HOOKS_DIR, 'session-start', 'session-init-data.js'), timeout: 10000 },
  { type: 'node',   script: path.join(HOOKS_DIR, 'session-start', 'config-validate.js'),  timeout: 3000 },
];

// Read stdin once
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
        } catch (_) {
          // Not JSON, ignore
        }
      }
      if (res.stderr && res.stderr.trim()) {
        process.stderr.write(`[dispatcher-session-start] ${path.basename(hook.script)}: ${res.stderr.trim()}\n`);
      }
    } catch (err) {
      process.stderr.write(`[dispatcher-session-start] ${path.basename(hook.script)} FAILED: ${err.message}\n`);
    }
  }
  // Merge results: concatenate all result strings
  if (results.length > 0) {
    process.stdout.write(JSON.stringify({ result: results.join('\n\n') }));
  }
});
