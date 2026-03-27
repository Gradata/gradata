#!/usr/bin/env node
/**
 * dispatcher-stop.js — Consolidates all Stop hooks
 * Reduces CMD window flashes from 5 to 1 on Windows.
 *
 * Hooks dispatched:
 *   1. cost-tracking.js      (Node)
 *   2. session-persist.js    (Node)
 *   3. session-close-data.js (Node)
 *   4. brain-maintain.js     (Node)
 *   5. session-checklist.js  (Node)
 */
const path = require('path');
const cfg = require('./config.js');

const HOOKS_DIR = path.dirname(__filename);

const hooks = [
  { script: path.join(HOOKS_DIR, 'cost-tracking.js'),      timeout: 5000 },
  { script: path.join(HOOKS_DIR, 'session-persist.js'),     timeout: 5000 },
  { script: path.join(HOOKS_DIR, 'session-close-data.js'),  timeout: 15000 },
  { script: path.join(HOOKS_DIR, 'brain-maintain.js'),      timeout: 30000 },
  { script: path.join(HOOKS_DIR, 'session-checklist.js'),   timeout: 10000 },
];

let stdinBuf = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', d => stdinBuf += d);
process.stdin.on('end', () => {
  const results = [];
  for (const hook of hooks) {
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
          if (parsed.result) results.push(parsed.result);
        } catch (_) {}
      }
      if (res.stderr && res.stderr.trim()) {
        process.stderr.write(`[dispatcher-stop] ${path.basename(hook.script)}: ${res.stderr.trim()}\n`);
      }
    } catch (err) {
      process.stderr.write(`[dispatcher-stop] ${path.basename(hook.script)} FAILED: ${err.message}\n`);
    }
  }
  if (results.length > 0) {
    process.stdout.write(JSON.stringify({ result: results.join('\n\n') }));
  }
});
