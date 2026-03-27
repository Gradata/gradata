#!/usr/bin/env node
/**
 * arch-review.js -- PostToolUse hook (matcher: Write|Edit)
 * Opinionated architecture review: suggests better routes, patterns, and
 * SDK compliance. Complements codex-review.js (which catches bugs).
 *
 * Only fires on substantial code changes (>200 chars) to SDK or brain/scripts files.
 * Uses codex exec for the review, with a different prompt focused on architecture.
 */

const path = require('path');
const fs = require('fs');

const cfg = require('./config.js');
const { execSafe } = cfg;

const PROFILE = process.env.GRADATA_HOOK_PROFILE || 'standard';
if (PROFILE === 'minimal') process.exit(0);

// Only review code files in these paths
const REVIEW_PATHS = [
  'sdk/src/', 'sdk/tests/', 'brain/scripts/',
  '.claude/hooks/', '.claude/agents/',
];

const CODE_EXTENSIONS = new Set([
  '.js', '.ts', '.py', '.sh', '.bash',
]);

const SKIP_PATHS = [
  'node_modules', '.git', '__pycache__',
  'events.jsonl', 'system.db', '.vectorstore',
];

function readStdin() {
  try {
    if (process.stdin.isTTY) return null;
    return JSON.parse(fs.readFileSync(0, 'utf8'));
  } catch { return null; }
}

function isArchReviewable(filePath) {
  if (!filePath) return false;
  const ext = path.extname(filePath).toLowerCase();
  if (!CODE_EXTENSIONS.has(ext)) return false;
  const normalized = filePath.replace(/\\/g, '/');
  if (SKIP_PATHS.some(p => normalized.includes(p))) return false;
  return REVIEW_PATHS.some(p => normalized.includes(p));
}

function getFileDiff(filePath) {
  try {
    const normalized = filePath.replace(/\\/g, '/');
    let cwd;
    if (normalized.includes('SpritesWork/brain')) {
      cwd = 'C:/Users/olive/SpritesWork/brain';
    } else {
      cwd = process.env.WORKING_DIR || 'C:/Users/olive/OneDrive/Desktop/Sprites Work';
    }
    return execSafe(`git diff HEAD -- "${filePath}"`, {
      encoding: 'utf8', timeout: 5000, cwd,
    }) || null;
  } catch { return null; }
}

try {
  const toolData = readStdin();
  if (!toolData) process.exit(0);

  const toolName = toolData.tool_name || '';
  if (toolName !== 'Write' && toolName !== 'Edit') process.exit(0);

  const toolInput = toolData.tool_input || {};
  const filePath = toolInput.file_path || '';
  if (!isArchReviewable(filePath)) process.exit(0);

  const content = toolInput.content || toolInput.new_string || '';
  if (!content || content.length < 200) process.exit(0); // only substantial changes

  const diff = getFileDiff(filePath);
  const reviewContent = diff || content;
  const fileName = path.basename(filePath);
  const normalized = filePath.replace(/\\/g, '/');

  // Determine context for the review
  let context = 'general';
  if (normalized.includes('sdk/src/gradata/patterns/')) context = 'Layer 0 pattern';
  else if (normalized.includes('sdk/src/gradata/enhancements/')) context = 'Layer 1 enhancement';
  else if (normalized.includes('brain/scripts/')) context = 'brain script (should be thin shim over SDK)';
  else if (normalized.includes('.claude/hooks/')) context = 'hook (should be lightweight, <30s timeout)';

  const prompt = [
    `You are an opinionated architecture reviewer for the Gradata SDK.`,
    `Context: ${context}`,
    `File: ${fileName}`,
    ``,
    `Architecture rules:`,
    `- Layer 0 (patterns/) must NOT import from Layer 1 (enhancements/)`,
    `- Layer 1 (enhancements/) CAN import from Layer 0`,
    `- brain/scripts/ should be thin shims that delegate to SDK pure functions`,
    `- Pure computation belongs in SDK. I/O (file reads, DB queries, API calls) belongs in brain/scripts/`,
    `- All new features must wire into the event system`,
    `- Functions should be pure when possible (no I/O, no side effects)`,
    `- Domain-specific logic must be configurable, not hardcoded`,
    ``,
    `Review this change for:`,
    `1. Layer violations (wrong import direction)`,
    `2. Logic that should be in SDK but is in brain/scripts/ (or vice versa)`,
    `3. Missing testability (pure functions should be extractable for testing)`,
    `4. Better patterns available (existing SDK utilities being reimplemented)`,
    `5. Domain coupling (hardcoded sales terms in Layer 0)`,
    ``,
    `Only suggest improvements that materially improve architecture.`,
    `Skip style/formatting. Be brief (max 5 lines). If architecture is sound, say "CLEAN".`,
    ``,
    `--- CODE CHANGE ---`,
    reviewContent.slice(0, 6000),
  ].join('\n');

  const result = execSafe(
    `codex exec --ephemeral --sandbox read-only -`,
    {
      input: prompt,
      encoding: 'utf8',
      timeout: 45000,
      stdio: ['pipe', 'pipe', 'pipe'],
    }
  );

  if (result && !result.includes('CLEAN') && result.trim().length > 10) {
    const lines = result.trim().split('\n').slice(0, 8);
    process.stderr.write(`\n[arch-review] ${fileName} (${context}):\n`);
    for (const line of lines) {
      if (line.trim()) process.stderr.write(`  ${line.trim()}\n`);
    }
  }
} catch (e) {
  // Silent on failure — architecture review is best-effort
  if (e.message && !e.message.includes('ETIMEDOUT')) {
    process.stderr.write(`[arch-review] error: ${e.message}\n`);
  }
}
