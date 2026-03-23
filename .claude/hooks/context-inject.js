#!/usr/bin/env node
/**
 * context-inject.js — UserPromptSubmit hook
 * Extracts entities from user message, queries brain vault,
 * injects relevant context before AI responds.
 *
 * Silent on failure — never blocks user input.
 * Target: <5s latency, <1500 tokens output.
 */
const { execSync } = require('child_process');
const path = require('path');

const PYTHON = 'C:/Users/olive/AppData/Local/Programs/Python/Python312/python.exe';
const SCRIPTS = 'C:/Users/olive/SpritesWork/brain/scripts';

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

// Call context compiler
try {
  // Escape message for shell (replace quotes, limit length)
  const safeMsg = message
    .substring(0, 300)
    .replace(/"/g, '\\"')
    .replace(/\n/g, ' ')
    .replace(/\r/g, '');

  const result = execSync(
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
