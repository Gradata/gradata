#!/usr/bin/env node
/**
 * codex-review.js -- PostToolUse hook (matcher: Write|Edit)
 * Spawns Codex CLI in read-only sandbox to review code changes.
 * Async: runs in background, surfaces issues via stderr.
 * Reviews code files AND structured markdown (CLAUDE.md, CARL rules,
 * SKILL.md, playbooks, templates) — skips routine data files.
 */

const path = require('path');
const fs = require('fs');

const os = require('os');

const cfg = require('../config.js');
const { execSafe, spawnSafe } = cfg;

const PROFILE = process.env.GRADATA_HOOK_PROFILE || 'standard';
if (PROFILE === 'minimal') process.exit(0);

// Bug 5 fix: check codex exists once, bail fast if not installed
let codexAvailable = null;
function hasCodex() {
  if (codexAvailable !== null) return codexAvailable;
  try {
    execSafe('codex --version', { timeout: 3000, stdio: ['pipe', 'pipe', 'pipe'] });
    codexAvailable = true;
  } catch {
    codexAvailable = false;
  }
  return codexAvailable;
}

const CODE_EXTENSIONS = new Set([
  '.js', '.ts', '.jsx', '.tsx', '.py', '.sh', '.bash',
  '.css', '.html', '.json', '.yaml', '.yml', '.sql',
  '.go', '.rs', '.rb', '.php', '.java', '.c', '.cpp',
]);

// Structured markdown that IS logic — always review these
const STRUCTURED_MD_PATTERNS = [
  'CLAUDE.md', 'SKILL.md', 'DOMAIN.md', 'ARCHITECTURE',
  '/carl/', '/playbooks/', '/templates/', '/domain/gates/',
  '/skills/', 'work-style.md', 'fallback-chains.md',
  'quality-rubrics.md', 'truth-protocol.md', 'action-waterfall.md',
];

// Routine data files — never review these
const SKIP_PATHS = [
  'node_modules', '.git', 'events.jsonl', 'system.db',
  'lessons-archive.md', 'loop-state.md', 'morning-brief.md',
  'startup-brief.md', 'MEMORY.md', 'prospects/', 'sessions/',
  '.vectorstore', 'system.db-shm', 'system.db-wal',
  'learnings-queue.json', '__pycache__',
];

function readStdin() {
  try {
    if (process.stdin.isTTY) return null;
    return JSON.parse(fs.readFileSync(0, 'utf8'));
  } catch { return null; }
}

function isStructuredMarkdown(filePath) {
  const normalized = filePath.replace(/\\/g, '/');
  return STRUCTURED_MD_PATTERNS.some(p => normalized.includes(p));
}

function isReviewable(filePath) {
  if (!filePath) return false;
  const normalized = filePath.replace(/\\/g, '/');
  const ext = path.extname(filePath).toLowerCase();

  // Structured markdown WINS over skip paths — these are logic files
  // (e.g. a playbook shouldn't be skipped just because its name matches a skip pattern)
  if (ext === '.md' && isStructuredMarkdown(filePath)) return true;

  // Then check skip paths for everything else
  if (SKIP_PATHS.some(p => normalized.includes(p))) return false;

  // Code files — always review
  if (CODE_EXTENSIONS.has(ext)) return true;

  return false;
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
    const diff = execSafe(`git diff HEAD -- "${filePath}"`, {
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
  if (!isReviewable(filePath)) process.exit(0);

  // Get the content that was written/edited
  const content = toolInput.content || toolInput.new_string || '';
  if (!content || content.length < 50) process.exit(0); // skip trivial edits

  // Try to get git diff for more context
  const diff = getFileDiff(filePath);
  const reviewContent = diff || content;
  const fileName = path.basename(filePath);
  const isMd = path.extname(filePath).toLowerCase() === '.md';

  // Build the review prompt — Codex reviews AND proposes fixes
  const baseInstructions = isMd ? [
    `You are reviewing a structured config/rules file that controls AI agent behavior.`,
    `File: ${fileName}`,
    `Look for: contradictory rules, missing guardrails, broken references, logic gaps.`,
  ] : [
    `You are reviewing a code change.`,
    `File: ${fileName}`,
    `Look for: bugs, security issues, logic errors, crashes.`,
  ];

  const prompt = [
    ...baseInstructions,
    `Skip style/formatting nits.`,
    ``,
    `If you find issues, respond in this exact format:`,
    `ISSUE: [one-line description]`,
    `SEVERITY: P0|P1`,
    `FIX:`,
    `\`\`\``,
    `[your proposed fix — show the corrected code/text, not a diff]`,
    `\`\`\``,
    `RATIONALE: [why your fix is better, one line]`,
    ``,
    `You can report multiple issues. If no issues found, respond with just: LGTM`,
    ``,
    `--- CHANGE ---`,
    reviewContent.slice(0, 8000),
  ].join('\n');

  // Bug 5: bail fast if codex not installed
  if (!hasCodex()) process.exit(0);

  // Bug 7: capture both stdout and stderr from codex
  let result = '';
  try {
    const child = spawnSafe(
      'codex', ['exec', '--ephemeral', '--sandbox', 'read-only', '-'],
      {
        input: prompt,
        encoding: 'utf8',
        timeout: 45000,
        shell: true,
      }
    );
    // Combine stdout + stderr — some CLI tools write to either
    result = (child.stdout || '') + (child.stderr || '');
  } catch { process.exit(0); }

  // Write structured review to a file Claude can read and act on
  const REVIEW_DIR = path.join(os.tmpdir(), 'gradata-codex-reviews');
  if (!fs.existsSync(REVIEW_DIR)) fs.mkdirSync(REVIEW_DIR, { recursive: true });

  // Bug 6: clean up old reviews (keep last 50)
  try {
    const files = fs.readdirSync(REVIEW_DIR)
      .filter(f => f.endsWith('.md'))
      .sort()
      .reverse();
    for (const old of files.slice(50)) {
      fs.unlinkSync(path.join(REVIEW_DIR, old));
    }
  } catch {}

  if (result && !result.includes('LGTM') && result.trim().length > 10) {
    const reviewFile = path.join(REVIEW_DIR, `${Date.now()}-${fileName}.md`);
    const review = [
      `# Codex Review: ${fileName}`,
      `**File:** ${filePath}`,
      `**Time:** ${new Date().toISOString()}`,
      ``,
      result.trim(),
      ``,
      `---`,
      `*Claude: evaluate each issue. If the fix is better, apply it. If not, explain why your version is correct.*`,
    ].join('\n');
    fs.writeFileSync(reviewFile, review);

    // Surface to Claude via stderr — include the fix proposals
    const lines = result.trim().split('\n').slice(0, 20);
    process.stderr.write(`\n[codex-review] ${fileName} — issues found. Review: ${reviewFile}\n`);
    for (const line of lines) {
      if (line.trim()) process.stderr.write(`  ${line.trim()}\n`);
    }
    process.stderr.write(`  → Claude: read the review file, evaluate fixes, apply if better.\n`);
  }
} catch (e) {
  // Surface errors so we know when codex isn't running
  process.stderr.write(`[codex-review] error: ${e.message}\n`);
}