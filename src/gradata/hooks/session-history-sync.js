#!/usr/bin/env node
/**
 * session-history-sync.js — Stop hook
 * Persists rule effectiveness data to claude-mem at session end.
 */
const fs = require('fs');
const os = require('os');
const http = require('http');

const EFFECTIVENESS_FILE = require('path').join(os.tmpdir(), 'gradata-rule-effectiveness.json');

let effectiveness = {};
try {
  if (fs.existsSync(EFFECTIVENESS_FILE)) {
    effectiveness = JSON.parse(fs.readFileSync(EFFECTIVENESS_FILE, 'utf8'));
  }
} catch (e) { process.exit(0); }

if (Object.keys(effectiveness).length === 0) process.exit(0);

try {
  const payload = JSON.stringify({
    type: 'rule_effectiveness',
    data: effectiveness,
    ts: new Date().toISOString(),
  });
  const req = http.request({
    hostname: 'localhost', port: 37777, path: '/api/memory',
    method: 'POST', timeout: 3000,
    headers: { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(payload) },
  });
  req.on('error', () => {});
  req.on('timeout', () => req.destroy());
  req.write(payload);
  req.end();
  fs.unlinkSync(EFFECTIVENESS_FILE);
} catch (e) {}
