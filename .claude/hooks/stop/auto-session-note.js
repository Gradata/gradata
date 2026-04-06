#!/usr/bin/env node
/**
 * auto-session-note.js — Stop hook
 * Generates a markdown session note and bumps loop-state.md so Oliver
 * never needs to say "wrap up" for basic session tracking.
 *
 * Writes: brain/sessions/YYYY-MM-DD-SNN.md
 * Updates: brain/loop-state.md (bumps to next session, human sessions only)
 *
 * Runs AFTER session-persist.js (uses persist data as fallback).
 */
const fs = require('fs');
const path = require('path');
const cfg = require('../config.js');

const BRAIN = cfg.BRAIN_DIR;
const WORK = cfg.WORKING_DIR;
const SESSIONS = path.join(BRAIN, 'sessions');
const PERSIST = path.join(SESSIONS, 'persist');
const LOOP_STATE = cfg.LOOP_STATE; // Single source of truth: brain/loop-state.md

try {
  // --- 0. Skip non-interactive sessions (subagents, autoresearch, worktrees) ---
  // Only bump session count for human-interactive top-level sessions.
  // Subagents set CLAUDE_AGENT=1; worktrees run from different dirs.
  if (process.env.CLAUDE_AGENT || process.env.CLAUDE_WORKTREE) {
    process.exit(0);
  }
  // Autoresearch and background runs use branches, not main
  try {
    const branchResult = cfg.spawnSafe('git', ['-C', WORK, 'rev-parse', '--abbrev-ref', 'HEAD'], {
      encoding: 'utf8', timeout: 3000,
    });
    const branch = (branchResult.stdout || '').trim();
    if (branch && branch !== 'main' && branch !== 'HEAD') {
      // Non-main branch = likely autoresearch/worktree, skip bump
      process.exit(0);
    }
  } catch (_) {}

  // --- 1. Detect current session number ---
  let sessionNum = 0;
  if (fs.existsSync(LOOP_STATE)) {
    const text = fs.readFileSync(LOOP_STATE, 'utf8');
    const m = text.match(/Session\s+(\d+)/);
    if (m) sessionNum = parseInt(m[1]);
  }
  if (sessionNum === 0) process.exit(0); // can't write note without session number

  const today = new Date().toISOString().split('T')[0];
  const noteFile = path.join(SESSIONS, `${today}-S${sessionNum}.md`);

  // Don't overwrite existing note (manual wrap-up already ran)
  if (fs.existsSync(noteFile)) {
    bumpLoopState(sessionNum);
    process.exit(0);
  }

  // --- 2. Gather git data ---
  let commits = '';
  let filesChanged = [];
  let diffStat = '';

  // Commits since last session note (look for previous session file)
  try {
    const r = cfg.spawnSafe('git', ['-C', WORK, 'log', '--oneline', '-10', '--since=12 hours ago'], {
      encoding: 'utf8', timeout: 5000,
    });
    if (r.status === 0 && r.stdout && r.stdout.trim()) {
      commits = r.stdout.trim();
    }
  } catch (_) {}

  // Files changed (uncommitted)
  try {
    const r = cfg.spawnSafe('git', ['-C', WORK, 'diff', '--name-only', 'HEAD'], {
      encoding: 'utf8', timeout: 5000,
    });
    if (r.status === 0 && r.stdout) {
      filesChanged = r.stdout.trim().split('\n').filter(Boolean);
    }
  } catch (_) {}

  // Diff stat for committed changes today
  try {
    const r = cfg.spawnSafe('git', ['-C', WORK, 'diff', '--stat', '--since=12 hours ago', 'HEAD'], {
      encoding: 'utf8', timeout: 5000,
    });
    if (r.status === 0 && r.stdout && r.stdout.trim()) {
      diffStat = r.stdout.trim();
    }
  } catch (_) {}

  // Brain vault changes
  let brainChanges = [];
  try {
    const r = cfg.spawnSafe('git', ['-C', BRAIN, 'diff', '--name-only', 'HEAD'], {
      encoding: 'utf8', timeout: 5000,
    });
    if (r.status === 0 && r.stdout) {
      brainChanges = r.stdout.trim().split('\n').filter(Boolean);
    }
  } catch (_) {}

  // --- 3. Infer session type ---
  const allFiles = [...filesChanged, ...brainChanges];
  const type = inferSessionType(allFiles, commits);

  // --- 4. Read corrections from lessons (recent) ---
  let corrections = '';
  try {
    const lessonsPath = path.join(BRAIN, 'lessons.md');
    if (fs.existsSync(lessonsPath)) {
      const text = fs.readFileSync(lessonsPath, 'utf8');
      const lines = text.split('\n');
      // Find lessons from today's session
      const sessionLessons = lines.filter(l =>
        l.includes(`session: ${sessionNum}`) || l.includes(`S${sessionNum}`)
      );
      if (sessionLessons.length > 0) {
        corrections = `${sessionLessons.length} corrections captured`;
      }
    }
  } catch (_) {}

  // --- 5. Read persist file for extra context ---
  let persistData = null;
  const persistFile = path.join(PERSIST, `session-${String(sessionNum).padStart(3, '0')}.json`);
  try {
    if (fs.existsSync(persistFile)) {
      persistData = JSON.parse(fs.readFileSync(persistFile, 'utf8'));
    }
  } catch (_) {}

  // --- 6. Build markdown note ---
  const lines = [
    '---',
    `date: ${today}`,
    `session: ${sessionNum}`,
    `type: ${type}`,
    `auto_generated: true`,
    '---',
    '',
    `# Session ${sessionNum} — ${today}`,
    '',
    '## What Changed',
  ];

  if (commits) {
    lines.push('### Commits');
    commits.split('\n').forEach(c => lines.push(`- ${c}`));
    lines.push('');
  }

  if (filesChanged.length > 0) {
    lines.push(`### Uncommitted (${filesChanged.length} files)`);
    // Group by directory
    const byDir = {};
    filesChanged.slice(0, 30).forEach(f => {
      const dir = path.dirname(f) || '.';
      if (!byDir[dir]) byDir[dir] = [];
      byDir[dir].push(path.basename(f));
    });
    Object.entries(byDir).forEach(([dir, files]) => {
      lines.push(`- \`${dir}/\`: ${files.join(', ')}`);
    });
    lines.push('');
  }

  if (brainChanges.length > 0) {
    lines.push(`### Brain Vault (${brainChanges.length} files)`);
    brainChanges.slice(0, 15).forEach(f => lines.push(`- ${f}`));
    lines.push('');
  }

  if (corrections) {
    lines.push('## Corrections');
    lines.push(corrections);
    lines.push('');
  }

  if (!commits && filesChanged.length === 0 && brainChanges.length === 0) {
    lines.push('_No code changes detected this session._');
    lines.push('');
  }

  lines.push('---');
  lines.push('_Auto-generated by stop hook. No manual wrap-up performed._');

  fs.writeFileSync(noteFile, lines.join('\n'), 'utf8');

  // --- 7. Bump loop-state for next session ---
  bumpLoopState(sessionNum);

} catch (e) {
  process.stderr.write(`[auto-session-note] FAILED: ${e.message}\n`);
}

// ── Helpers ──

function bumpLoopState(currentSession) {
  const next = currentSession + 1;
  const today = new Date().toISOString().split('T')[0];
  const content = [
    `# Session ${next} — ${today}`,
    '',
    '## Status',
    `Previous session: S${currentSession} (auto-closed)`,
    '',
    '## Next Session Tasks',
    'Check loop-state.md and memory for context.',
  ].join('\n');

  try {
    fs.writeFileSync(LOOP_STATE, content, 'utf8');
  } catch (_) {}
}

function inferSessionType(files, commits) {
  const all = files.join(' ') + ' ' + (commits || '');
  const lower = all.toLowerCase();

  // Sales signals
  const salesSignals = ['leads/', 'instantly', 'pipedrive', 'prospect', 'campaign', 'email',
    'apollo', 'clay', 'zerobounce', 'prospeo'];
  const salesScore = salesSignals.filter(s => lower.includes(s)).length;

  // System signals
  const systemSignals = ['sdk/', 'src/gradata', 'tests/', 'brain.py', '_core.py',
    'hooks/', '.claude/', 'scripts/', 'pyproject'];
  const systemScore = systemSignals.filter(s => lower.includes(s)).length;

  if (salesScore > systemScore) return 'sales';
  if (systemScore > salesScore) return 'system';
  if (salesScore > 0 && systemScore > 0) return 'mixed';
  return 'unknown';
}
