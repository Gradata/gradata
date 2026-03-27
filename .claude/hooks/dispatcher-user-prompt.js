#!/usr/bin/env node
/**
 * dispatcher-user-prompt.js — Consolidates all UserPromptSubmit hooks
 * Reduces CMD window flashes from 6 to 1 on Windows.
 *
 * Hooks dispatched:
 *   1. session-start-reminder.js  (Node)
 *   2. capture_learning.py        (Python)
 *   3. context-inject.js          (Node)
 *   4. gate-inject.js             (Node)
 *   5. prospect-autoload.js       (Node)
 *   6. implicit-feedback.js       (Node)
 *   7. skill-router.js            (Node) — intent-based skill matching
 */
const path = require('path');
const cfg = require('./config.js');

const HOOKS_DIR = path.dirname(__filename);

const hooks = [
  { type: 'node',   script: path.join(HOOKS_DIR, 'session-start-reminder.js'), timeout: 5000 },
  { type: 'python', script: path.join(HOOKS_DIR, 'reflect', 'scripts', 'capture_learning.py'), timeout: 8000 },
  { type: 'node',   script: path.join(HOOKS_DIR, 'context-inject.js'),   timeout: 5000 },
  { type: 'node',   script: path.join(HOOKS_DIR, 'gate-inject.js'),      timeout: 3000 },
  { type: 'node',   script: path.join(HOOKS_DIR, 'prospect-autoload.js'), timeout: 3000 },
  { type: 'node',   script: path.join(HOOKS_DIR, 'implicit-feedback.js'), timeout: 3000 },
  { type: 'node',   script: path.join(HOOKS_DIR, 'skill-router.js'),      timeout: 3000 },
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
        process.stderr.write(`[dispatcher-user-prompt] ${path.basename(hook.script)}: ${res.stderr.trim()}\n`);
      }
    } catch (err) {
      process.stderr.write(`[dispatcher-user-prompt] ${path.basename(hook.script)} FAILED: ${err.message}\n`);
    }
  }
  if (results.length > 0) {
    process.stdout.write(JSON.stringify({ result: results.join('\n\n') }));
  }
});
