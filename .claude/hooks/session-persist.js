#!/usr/bin/env node
/**
 * session-persist.js — Stop hook
 * Saves minimum session handoff data even if session ends abruptly.
 * Creates brain/sessions/persist/session-NNN.json
 * Profile: all (always runs)
 */
const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const cfg = require('./config.js');
const BRAIN_PATH = cfg.BRAIN_DIR;
const PERSIST_DIR = path.join(BRAIN_PATH, 'sessions', 'persist');

try {
  // Ensure persist directory exists
  if (!fs.existsSync(PERSIST_DIR)) {
    fs.mkdirSync(PERSIST_DIR, { recursive: true });
  }

  // Detect session number from loop-state.md
  let sessionNum = 0;
  const loopState = path.join(BRAIN_PATH, 'loop-state.md');
  if (fs.existsSync(loopState)) {
    const text = fs.readFileSync(loopState, 'utf8');
    const match = text.match(/Session\s+(\d+)/);
    if (match) sessionNum = parseInt(match[1]);
  }

  const SPRITES_WORK = cfg.WORKING_DIR;

  // Get modified files from git
  let filesModified = [];
  try {
    const gitOutput = execSync(
      `git -C "${SPRITES_WORK}" diff --name-only HEAD 2>/dev/null`,
      { encoding: 'utf8', timeout: 5000 }
    ).trim();
    if (gitOutput) filesModified = gitOutput.split('\n').slice(0, 30);
  } catch (e) { /* git not available or no changes */ }

  // Get brain repo modified files
  try {
    const brainGit = execSync(
      `git -C "${BRAIN_PATH}" diff --name-only HEAD 2>/dev/null`,
      { encoding: 'utf8', timeout: 5000 }
    ).trim();
    if (brainGit) {
      filesModified = filesModified.concat(
        brainGit.split('\n').slice(0, 20).map(f => `brain/${f}`)
      );
    }
  } catch (e) { /* no brain changes */ }

  // Build short handoff from git log + loop-state
  let handoff = '';
  try {
    // Last 3 commit messages = what was done
    const log = execSync(
      `git -C "${SPRITES_WORK}" log --oneline -3 2>/dev/null`,
      { encoding: 'utf8', timeout: 5000 }
    ).trim();
    if (log) handoff += 'Recent commits:\n' + log + '\n';
  } catch (e) {}

  // Pipeline snapshot from loop-state
  let pipeline = '';
  let dueNext = '';
  if (fs.existsSync(loopState)) {
    const text = fs.readFileSync(loopState, 'utf8');

    // Extract "Due Next Session" section
    const dueMatch = text.match(/## Due Next Session\s*\n([\s\S]*?)(?=\n##|$)/);
    if (dueMatch) dueNext = dueMatch[1].trim();

    // Extract pipeline table rows (lines with | and a stage)
    const stages = ['proposal-made', 'demo-scheduled', 'demo-done', 'replied', 'no-show', 'onboarding'];
    const pipelineLines = text.split('\n').filter(line =>
      line.includes('|') && stages.some(s => line.includes(s))
    );
    if (pipelineLines.length) pipeline = pipelineLines.length + ' active deals';

    // Extract overdue items
    const overdueLines = text.split('\n').filter(line =>
      line.toUpperCase().includes('OVERDUE')
    );
    if (overdueLines.length) pipeline += ' | ' + overdueLines.length + ' overdue';
  }

  // Uncommitted changes summary
  let uncommitted = '';
  if (filesModified.length) {
    const byType = {};
    filesModified.forEach(f => {
      const ext = f.split('.').pop() || 'other';
      byType[ext] = (byType[ext] || 0) + 1;
    });
    uncommitted = Object.entries(byType).map(([k,v]) => `${v} .${k}`).join(', ');
  }

  const persistData = {
    session: sessionNum,
    timestamp: new Date().toISOString(),
    files_modified: filesModified,
    handoff: {
      what_was_done: handoff.trim(),
      pipeline: pipeline || 'unknown',
      due_next: dueNext || 'check loop-state.md',
      uncommitted: uncommitted || 'none',
      wrap_up_completed: false,
      note: 'Session ended without wrap-up. Check loop-state.md and startup-brief.md for full context.',
    },
  };

  const filename = `session-${String(sessionNum).padStart(3, '0')}.json`;
  fs.writeFileSync(
    path.join(PERSIST_DIR, filename),
    JSON.stringify(persistData, null, 2)
  );

} catch (e) {
  // Silent failure — never block session end
}
