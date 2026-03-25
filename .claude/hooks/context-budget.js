#!/usr/bin/env node
/**
 * context-budget.js — SessionStart hook
 * Enforces file size limits on startup-loaded files.
 * Warns when any single file exceeds 12k tokens or total Tier 0+1 exceeds 30k.
 * Profile: all (always runs)
 */
const fs = require('fs');
const path = require('path');

const cfg = require('./config.js');
const SPRITES_WORK = cfg.WORKING_DIR;

// Files loaded every message (Tier 0)
const TIER_0 = [
  'CLAUDE.md',
];

// Files loaded at startup then released (Tier 1)
const TIER_1 = [
  '.claude/work-style.md',
  '.claude/lessons.md',
  'domain/pipeline/startup-brief.md',
  'domain/DOMAIN.md',
];

const MAX_FILE_TOKENS = 12000;
const MAX_TOTAL_TOKENS = 30000;

function estimateTokens(text) {
  // ~1.3 tokens per word for prose, ~chars/4 for code
  // Use blended estimate: words * 1.3
  const words = text.split(/\s+/).length;
  return Math.round(words * 1.3);
}

try {
  let totalTokens = 0;
  const warnings = [];

  const allFiles = [...TIER_0.map(f => ({ path: f, tier: 0 })), ...TIER_1.map(f => ({ path: f, tier: 1 }))];

  for (const file of allFiles) {
    const fullPath = path.join(SPRITES_WORK, file.path);
    if (!fs.existsSync(fullPath)) continue;

    const content = fs.readFileSync(fullPath, 'utf8');
    const tokens = estimateTokens(content);
    totalTokens += tokens;

    if (tokens > MAX_FILE_TOKENS) {
      warnings.push(`[context-budget] ${file.path}: ~${tokens} tokens (limit: ${MAX_FILE_TOKENS}) — Tier ${file.tier}`);
    }
  }

  if (totalTokens > MAX_TOTAL_TOKENS) {
    warnings.push(`[context-budget] Total startup load: ~${totalTokens} tokens (limit: ${MAX_TOTAL_TOKENS})`);
  }

  if (warnings.length > 0) {
    process.stderr.write('\n' + warnings.join('\n') + '\n');
  }
} catch (e) {
  // Silent failure
}
