#!/usr/bin/env node
/**
 * session-history-sync.js — Stop hook
 * Persists rule effectiveness data to claude-mem at session end.
 */
const fs = require('fs');
const os = require('os');
const http = require('http');

// Use per-user subdirectory to prevent symlink attacks on shared systems
const path = require('path');
const GRADATA_TMP = path.join(os.tmpdir(), `gradata-${process.getuid ? process.getuid() : 'win'}`);
try { fs.mkdirSync(GRADATA_TMP, { recursive: true, mode: 0o700 }); } catch (_) {}
const EFFECTIVENESS_FILE = path.join(GRADATA_TMP, 'rule-effectiveness.json');

let effectiveness = {};
try {
  effectiveness = JSON.parse(fs.readFileSync(EFFECTIVENESS_FILE, 'utf8'));
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
  req.on('response', () => {
    try { fs.unlinkSync(EFFECTIVENESS_FILE); } catch (_) {}
  });
  req.on('error', () => {});
  req.on('timeout', () => req.destroy());
  req.write(payload);
  req.end();
} catch (e) {}
