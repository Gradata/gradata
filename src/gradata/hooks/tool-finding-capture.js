#!/usr/bin/env node
/**
 * tool-finding-capture.js — PostToolUse hook
 * Bridges tool findings (qwen-lint, test failures) into brain corrections.
 * Tiered: test failures=always, lint=if acted on, arch=never auto.
 */
const fs = require('fs');
const path = require('path');
const os = require('os');

const STATE_FILE = path.join(os.tmpdir(), 'gradata-tool-findings.json');
const FINDING_TTL_MS = 10 * 60 * 1000;

let input = '';
try { input = fs.readFileSync(0, 'utf8'); } catch (e) { process.exit(0); }

let data = {};
try { data = JSON.parse(input); } catch (e) { process.exit(0); }

const toolName = data.tool_name || '';
const toolInput = data.tool_input || {};
const toolOutput = typeof data.tool_output === 'string' ? data.tool_output : JSON.stringify(data.tool_output || '');
const filePath = toolInput.file_path || toolInput.path || '';

let findings = [];
try {
  findings = JSON.parse(fs.readFileSync(STATE_FILE, 'utf8'));
  findings = findings.filter(f => Date.now() - f.ts < FINDING_TTL_MS);
} catch (e) { findings = []; }

if (toolName === 'Bash') {
  const cmd = (toolInput.command || '').toLowerCase();
  const out = toolOutput.toLowerCase();
  if ((cmd.includes('pytest') || cmd.includes('test')) && (out.includes('failed') || out.includes('error'))) {
    findings.push({ source: 'test-failure', file: '', finding: toolOutput.substring(0, 500), severity: 'high', auto: true, ts: Date.now() });
  }
}

if (toolName === 'Bash' && toolOutput.includes('[qwen-lint]')) {
  const lines = toolOutput.split('\n').filter(l => l.includes('[qwen-lint]'));
  for (const line of lines.slice(0, 5)) {
    const fileMatch = line.match(/([^\s]+\.[a-z]+)/);
    findings.push({ source: 'qwen-lint', file: fileMatch ? fileMatch[1] : '', finding: line.substring(0, 200), severity: 'medium', auto: false, ts: Date.now() });
  }
}

if (toolName === 'Edit' || toolName === 'Write') {
  const triggers = findings.filter(f => !f.auto && f.file && filePath.includes(f.file));
  if (triggers.length > 0) {
    const result = triggers.map(f =>
      'TOOL FINDING ACTED: ' + f.source + ' finding on ' + f.file + ' was fixed. Create brain correction with source="' + f.source + '".'
    );
    const matchedTs = new Set(triggers.map(f => f.ts));
    findings = findings.filter(f => !matchedTs.has(f.ts));
    try { fs.writeFileSync(STATE_FILE, JSON.stringify(findings)); } catch (e) {}
    process.stdout.write(JSON.stringify({ result: result.join('\n') }));
    process.exit(0);
  }
}

try { fs.writeFileSync(STATE_FILE, JSON.stringify(findings)); } catch (e) {}
