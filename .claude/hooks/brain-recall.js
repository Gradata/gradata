#!/usr/bin/env node
/**
 * brain-recall.js — PreToolUse hook (matcher: Write)
 * Auto-searches brain for relevant context before prospect-facing writes.
 *
 * Checks if the Write target is in prospects/, emails/, templates/, etc.
 * If so, runs FTS5 keyword search and surfaces context via hook output.
 *
 * Runs fast (FTS5 keyword, no API calls) — <200ms typical.
 */
const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');
const os = require('os');

const cfg = require('./config.js');
const PYTHON = cfg.PYTHON;
const SCRIPTS = cfg.SCRIPTS;

// Read tool input from stdin
let input = '';
try {
  input = fs.readFileSync(0, 'utf8');
} catch (e) {
  process.exit(0);
}

let toolInput;
try {
  toolInput = JSON.parse(input);
} catch (e) {
  process.exit(0);
}

const filePath = (toolInput.tool_input?.file_path || '').replace(/\\/g, '/');

// Only trigger for prospect-related writes
const prospectPatterns = [
  '/prospects/', '/emails/', '/templates/', '/demos/',
  '/Email Templates/', '/messages/'
];

const isProspectWrite = prospectPatterns.some(p => filePath.includes(p));
if (!isProspectWrite) {
  process.exit(0);
}

// Extract search term from file name
const parts = filePath.split('/');
const fileName = parts[parts.length - 1].replace(/\.(md|html|txt)$/, '').replace(/[-_]/g, ' ');
const safeName = fileName.replace(/['"]/g, '');

// Write a temp Python script (avoids shell escaping issues on Windows)
const tmpScript = path.join(os.tmpdir(), 'brain_recall_tmp.py');
fs.writeFileSync(tmpScript, `
import sys
sys.path.insert(0, r'${SCRIPTS}')
from query import fts_search
results = fts_search('${safeName}', top_k=3)
for r in results[:3]:
    ft = r.get('file_type', '?')
    src = r.get('source', '?')
    txt = r.get('text', '')[:150].replace('\\n', ' ')
    print(f"[{ft}] {src}: {txt}")
`);

try {
  const output = execSync(
    `"${PYTHON}" "${tmpScript}"`,
    { timeout: 5000, encoding: 'utf8' }
  ).trim();

  if (output) {
    console.log(`Brain recall for "${safeName}":\n${output}`);
  }
} catch (e) {
  // Silent — recall is best-effort, never blocks writes
} finally {
  try { fs.unlinkSync(tmpScript); } catch (e) {}
}
