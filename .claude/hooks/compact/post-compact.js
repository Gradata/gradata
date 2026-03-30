#!/usr/bin/env node
/**
 * post-compact.js — PreCompact hook (saves critical state before compression)
 *
 * When Claude Code compresses context, critical state can be lost.
 * This hook fires BEFORE compaction and saves a compact state snapshot
 * to a temp file. The context-inject.js hook detects the snapshot on the
 * next UserPromptSubmit and re-injects the critical context.
 *
 * Inspired by Audrey's PostCompact pattern.
 * Hook type: PreCompact (blocking — saves before compression)
 */
const fs = require('fs');
const path = require('path');
const os = require('os');

const cfg = require('../config.js');
const BRAIN_DIR = cfg.BRAIN_DIR;
const LOOP_STATE = cfg.LOOP_STATE;
const STARTUP_BRIEF = cfg.STARTUP_BRIEF;
const SNAPSHOT_FILE = cfg.COMPACT_SNAPSHOT;

const snapshot = {
  ts: new Date().toISOString(),
  session: null,
  tasks: [],
  handoff: null,
  halfDone: null,
  overdue: null,
};

// 1. Session number from loop-state
try {
  const ls = fs.readFileSync(LOOP_STATE, 'utf-8').slice(0, 500);
  const sessionMatch = ls.match(/Session\s+(\d+)/);
  if (sessionMatch) {
    snapshot.session = parseInt(sessionMatch[1]) + 1;
  }
} catch (e) { /* silent */ }

// 2. Next tasks from loop-state
try {
  const ls = fs.readFileSync(LOOP_STATE, 'utf-8');
  const taskSection = ls.match(/## Next Session Tasks\s*\n([\s\S]*?)(?=\n## |\n$)/);
  if (taskSection) {
    snapshot.tasks = taskSection[1]
      .split('\n')
      .filter(l => l.trim().startsWith('- '))
      .slice(0, 5)
      .map(l => l.trim());
  }
} catch (e) { /* silent */ }

// 3. Handoff context from startup-brief
try {
  const sb = fs.readFileSync(STARTUP_BRIEF, 'utf-8').slice(0, 1500);
  const handoff = sb.match(/\*\*Last session:\*\*\s*(.+)/);
  if (handoff) snapshot.handoff = handoff[1].trim();
  const halfDone = sb.match(/\*\*What was half-done:\*\*\s*(.+)/);
  if (halfDone) snapshot.halfDone = halfDone[1].trim().slice(0, 200);
  const overdue = sb.match(/\*\*Overdue:\*\*\s*(.+)/);
  if (overdue) snapshot.overdue = overdue[1].trim();
} catch (e) { /* silent */ }

// Write snapshot for context-inject.js to pick up
try {
  fs.writeFileSync(SNAPSHOT_FILE, JSON.stringify(snapshot, null, 2));
} catch (e) { /* silent */ }

// Output reminder for the compaction summary
const lines = [];
if (snapshot.session) lines.push(`Session: S${snapshot.session}`);
if (snapshot.tasks.length) lines.push(`Tasks: ${snapshot.tasks.slice(0, 3).join(' | ')}`);
if (snapshot.overdue) lines.push(`OVERDUE: ${snapshot.overdue}`);

if (lines.length > 0) {
  console.log('IMPORTANT: Context state saved before compaction.');
  lines.forEach(l => console.log('  ' + l));
}
