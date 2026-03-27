#!/usr/bin/env node
/**
 * context-inject.js — UserPromptSubmit hook
 * Extracts entities from user message, queries brain vault,
 * injects relevant context before AI responds.
 *
 * Silent on failure — never blocks user input.
 * Target: <5s latency, <1500 tokens output.
 */
const path = require('path');

const cfg = require('./config.js');
const { execSafe } = cfg;
const PYTHON = cfg.PYTHON;
const SCRIPTS = cfg.SCRIPTS;

// Read user message from stdin (hook protocol)
let input = '';
try {
  input = require('fs').readFileSync(0, 'utf-8');
} catch (e) {
  process.exit(0);
}

let message = '';
try {
  const parsed = JSON.parse(input);
  message = parsed.message || parsed.prompt || parsed.content || '';
} catch (e) {
  message = input.trim();
}

// Skip empty messages and very short ones (likely system commands)
if (!message || message.length < 10 || message.startsWith('/')) {
  process.exit(0);
}

// Skip system/meta questions that don't need brain context
const skipPatterns = [
  /^wrap\s*up/i,
  /^commit/i,
  /^push/i,
  /^status/i,
  /^git\s/i,
  /^save/i,
  /^remember/i,
];
for (const pat of skipPatterns) {
  if (pat.test(message)) {
    process.exit(0);
  }
}

// Check for post-compaction snapshot (Audrey PostCompact pattern)
const SNAPSHOT_FILE = path.join(require('os').tmpdir(), 'gradata-compact-snapshot.json');
try {
  if (require('fs').existsSync(SNAPSHOT_FILE)) {
    const snap = JSON.parse(require('fs').readFileSync(SNAPSHOT_FILE, 'utf-8'));
    // Only use if fresh (< 30 min old)
    const age = (Date.now() - new Date(snap.ts).getTime()) / 60000;
    if (age < 30) {
      const parts = [];
      if (snap.session) parts.push(`Session: S${snap.session}`);
      if (snap.tasks && snap.tasks.length) parts.push(`Tasks: ${snap.tasks.slice(0, 3).join(' | ')}`);
      if (snap.halfDone) parts.push(`Half-done: ${snap.halfDone}`);
      if (snap.overdue) parts.push(`OVERDUE: ${snap.overdue}`);
      if (parts.length) {
        process.stdout.write('CONTEXT RESTORED (post-compaction):\n  ' + parts.join('\n  ') + '\n');
      }
    }
    // Consume the snapshot (one-shot)
    require('fs').unlinkSync(SNAPSHOT_FILE);
  }
} catch (e) { /* silent */ }

// Inject meta-rules (loaded once per session, cached in temp file)
try {
  const metaCachePath = path.join(require('os').tmpdir(), 'gradata-meta-rules-cache.txt');
  const fs = require('fs');
  let metaText = '';
  let cacheAge = Infinity;
  if (fs.existsSync(metaCachePath)) {
    const stat = fs.statSync(metaCachePath);
    cacheAge = (Date.now() - stat.mtimeMs) / 60000; // minutes
    if (cacheAge < 120) { // 2 hour cache
      metaText = fs.readFileSync(metaCachePath, 'utf-8').trim();
    }
  }
  if (!metaText || cacheAge >= 120) {
    // Refresh cache from system.db
    const metaPyCmd = [
      'import sys; sys.path.insert(0, r"' + SCRIPTS + '")',
      'from paths import SDK_SRC, DB_PATH',
      'sys.path.insert(0, str(SDK_SRC))',
      'from gradata.enhancements.meta_rules import load_meta_rules, format_meta_rules_for_prompt',
      'metas = load_meta_rules(DB_PATH)',
      'print(format_meta_rules_for_prompt(metas))',
    ].join('; ');
    const result = execSafe(
      `"${PYTHON}" -c "${metaPyCmd}"`,
      { timeout: 5000, encoding: 'utf-8', stdio: ['pipe', 'pipe', 'ignore'] }
    ).trim();
    if (result) {
      fs.writeFileSync(metaCachePath, result);
      metaText = result;
    }
  }
  if (metaText) {
    process.stdout.write(metaText + '

');
  }
} catch (e) {
  // Silent — meta-rule injection is best-effort
}

// Call context compiler
try {
  // Escape message for shell (replace quotes, limit length)
  const safeMsg = message
    .substring(0, 300)
    .replace(/"/g, '\\"')
    .replace(/\n/g, ' ')
    .replace(/\r/g, '');

  const result = execSafe(
    `"${PYTHON}" "${path.join(SCRIPTS, 'context_compile.py')}" --message "${safeMsg}"`,
    {
      timeout: 5000,
      encoding: 'utf-8',
      cwd: SCRIPTS,
      stdio: ['pipe', 'pipe', 'ignore'],  // capture stdout, ignore stderr
    }
  );

  if (result && result.trim()) {
    // Output as system context (Claude receives this)
    process.stdout.write(result.trim());
  }
} catch (e) {
  // Silent — context injection is best-effort
  process.exit(0);
}
