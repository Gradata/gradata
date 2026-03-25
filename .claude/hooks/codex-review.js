#!/usr/bin/env node
/**
 * codex-review.js -- PostToolUse hook (matcher: Write|Edit)
 * Spawns Codex CLI in read-only sandbox to review code changes.
 * Async: runs in background, surfaces issues via stderr.
 * Only reviews code files (js, py, ts, jsx, tsx, sh, css, html).
 */

const { execSync } = require('child_process');
const path = require('path');
const fs = require('fs');

const PROFILE = process.env.AIOS_HOOK_PROFILE || 'standard';
if (PROFILE === 'minimal') process.exit(0);

const CODE_EXTENSIONS = new Set([
  '.js', '.ts', '.jsx', '.tsx', '.py', '.sh', '.bash',
  '.css', '.html', '.json', '.yaml', '.yml', '.sql',
  '.go', '.rs', '.rb', '.php', '.java', '.c', '.cpp',
]);

// Skip files that aren't code (data files, markdown prose, DBs)
const SKIP_PATHS = [
  'node_modules', '.git', 'events.jsonl', 'system.db',
  'lessons-archive.md', 'loop-state.md', 'morning-brief.md',
  'startup-brief.md', 'MEMORY.md', 'prospects/', 'sessions/',
  '.vectorstore', 'system.db-shm', 'system.db-wal',
];

function readStdin() {
  try {
    if (process.stdin.isTTY) return null;
    return JSON.parse(fs.readFileSync(0, 'utf8'));
  } catch { return null; }
}

function isCodeFile(filePath) {
  if (!filePath) return false;
  const ext = path.extname(filePath).toLowerCase();
  if (!CODE_EXTENSIONS.has(ext)) return false;
  const normalized = filePath.replace(/\\/g, '/');
  return !SKIP_PATHS.some(p => normalized.includes(p));
}

function getFileDiff(filePath) {
  try {
    // Detect which git repo the file belongs to
    const normalized = filePath.replace(/\\/g, '/');
    let cwd;
    if (normalized.includes('SpritesWork/brain')) {
      cwd = 'C:/Users/olive/SpritesWork/brain';
    } else {
      cwd = process.env.WORKING_DIR || 'C:/Users/olive/OneDrive/Desktop/Sprites Work';
    }
    const diff = execSync(`git diff HEAD -- "${filePath}"`, {
      encoding: 'utf8',
      timeout: 5000,
      cwd,
    });
    return diff || null;
  } catch { return null; }
}

try {
  const toolData = readStdin();
  if (!toolData) process.exit(0);

  const toolName = toolData.tool_name || '';
  if (toolName !== 'Write' && toolName !== 'Edit') process.exit(0);

  const toolInput = toolData.tool_input || {};
  const filePath = toolInput.file_path || '';
  if (!isCodeFile(filePath)) process.exit(0);

  // Get the content that was written/edited
  const content = toolInput.content || toolInput.new_string || '';
  if (!content || content.length < 50) process.exit(0); // skip trivial edits

  // Try to get git diff for more context
  const diff = getFileDiff(filePath);
  const reviewContent = diff || content;
  const fileName = path.basename(filePath);

  // Build the review prompt
  const prompt = [
    `Review this code change for bugs, security issues, and logic errors.`,
    `File: ${fileName}`,
    `Only report REAL issues (P0: crashes/security, P1: bugs/logic errors).`,
    `Skip style/formatting. Be brief. If no issues, say "LGTM".`,
    ``,
    `--- CODE CHANGE ---`,
    reviewContent.slice(0, 8000), // cap at 8K to keep cost low
  ].join('\n');

  // Spawn codex exec asynchronously
  const result = execSync(
    `codex exec --ephemeral --sandbox read-only -`,
    {
      input: prompt,
      encoding: 'utf8',
      timeout: 45000,
      stdio: ['pipe', 'pipe', 'pipe'],
    }
  );

  // Parse result and surface issues
  if (result && !result.includes('LGTM') && result.trim().length > 10) {
    const lines = result.trim().split('\n').slice(0, 10); // cap output
    process.stderr.write(`\n[codex-review] ${fileName}:\n`);
    for (const line of lines) {
      if (line.trim()) process.stderr.write(`  ${line.trim()}\n`);
    }
  }
} catch (e) {
  // Surface errors so we know when codex isn't running
  process.stderr.write(`[codex-review] error: ${e.message}\n`);
}