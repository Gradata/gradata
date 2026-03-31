#!/usr/bin/env node
/**
 * rule-enforcement.js -- PreToolUse hook (matcher: Write|Edit)
 * Injects RULE-tier lesson reminders before code changes.
 *
 * Reads brain/lessons.md, finds all RULE-tier entries, and prepends
 * them as a reminder in the tool result. This makes graduated rules
 * visible and enforceable — not just suggestions buried in context.
 *
 * This is fix #4: rules become enforcement, not just suggestions.
 */
const fs = require('fs');
const cfg = require('../config.js');
const BRAIN = cfg.BRAIN_DIR;

function readStdin() {
  try {
    if (process.stdin.isTTY) return null;
    return JSON.parse(fs.readFileSync(0, 'utf8'));
  } catch { return null; }
}

const input = readStdin();
if (!input) process.exit(0);

// Read lessons.md and extract RULE-tier entries
const lessonsPath = `${BRAIN}/lessons.md`;
let rules = [];

try {
  if (fs.existsSync(lessonsPath)) {
    const text = fs.readFileSync(lessonsPath, 'utf8');
    const lines = text.split('\n');
    for (const line of lines) {
      // Match: [2026-03-30] [RULE:0.92] PROCESS: Never jump straight to...
      const m = line.match(/^\[[\d-]+\]\s+\[RULE:[\d.]+\]\s+(\w+):\s+(.+)/);
      if (m) {
        rules.push({ category: m[1], text: m[2].trim() });
      }
    }
  }
} catch (e) {
  // Silent — don't block edits
}

if (rules.length === 0) process.exit(0);

// Format as a brief reminder (not a wall of text)
const reminder = rules
  .map(r => `[RULE] ${r.category}: ${r.text.substring(0, 120)}`)
  .join('\n');

const output = {
  result: `\n⚡ BRAIN RULES (graduated from corrections):\n${reminder}\n`
};

process.stdout.write(JSON.stringify(output));
