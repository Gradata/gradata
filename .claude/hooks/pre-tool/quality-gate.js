#!/usr/bin/env node
/**
 * quality-gate.js — PreToolUse hook (matcher: Write)
 * Surfaces a reminder when writing to prospect-facing paths.
 * Non-blocking — reminder only.
 * Profile: strict only
 */

const PROFILE = process.env.GRADATA_HOOK_PROFILE || 'standard';
if (PROFILE !== 'strict') process.exit(0);

const PROSPECT_PATHS = [
  'brain/prospects/',
  'domain/pipeline/',
  'docs/Demo Prep/',
  'brain/demos/',
  '/prospects/',
  '/emails/',
  '/templates/',
  '/demos/',
  '/Email Templates/',
  '/messages/',
];

try {
  let input = '';
  if (!process.stdin.isTTY) {
    const fs = require('fs');
    input = fs.readFileSync(0, 'utf8');
  }

  let toolData = {};
  try { toolData = JSON.parse(input); } catch (e) { /* no data */ }

  const filePath = toolData.file_path || toolData.path || '';

  const isProspectFacing = PROSPECT_PATHS.some(p => filePath.includes(p));

  if (isProspectFacing) {
    process.stderr.write(`[quality-gate] Writing to prospect-facing path: ${filePath}. Ensure pre-flight gate completed.\n`);
    process.stderr.write(`[quality-gate] MANDATORY: Run adversarial review (skills/dev/adversarial-review/SKILL.md) before marking output as done.\n`);
  }
} catch (e) {
  // Silent failure
}
