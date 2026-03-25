#!/usr/bin/env node
/**
 * peer-announce.js — SessionStart hook
 * Auto-announces this session to other peers via claude-peers MCP.
 * Broadcasts: session number, session type (weekday=pipeline, weekend=systems),
 * working directory, and handoff context from loop-state.md.
 *
 * Also listens for active peers and surfaces them at startup.
 * Lightweight: reads 2 files + 1 MCP call. Target <3s.
 */
const fs = require('fs');
const { execSync } = require('child_process');
const cfg = require('./config.js');

// Detect session number
let sessionNum = 'unknown';
try {
  const ls = fs.readFileSync(cfg.LOOP_STATE, 'utf-8').slice(0, 500);
  const m = ls.match(/Session\s+(\d+)/);
  if (m) sessionNum = `S${parseInt(m[1]) + 1}`;
} catch (e) { /* silent */ }

// Detect session type from day of week
const day = new Date().getDay();
const isWeekend = day === 0 || day === 6;
const sessionType = isWeekend ? 'systems' : 'pipeline';

// Get handoff context
let handoff = '';
try {
  const ls = fs.readFileSync(cfg.LOOP_STATE, 'utf-8');
  const taskSection = ls.match(/## Next Session Tasks\s*\n([\s\S]*?)(?=\n## |\n$)/);
  if (taskSection) {
    const tasks = taskSection[1]
      .split('\n')
      .filter(l => l.trim().startsWith('- '))
      .slice(0, 3)
      .map(l => l.trim().replace(/^- /, ''));
    if (tasks.length) handoff = tasks.join('; ');
  }
} catch (e) { /* silent */ }

// Build summary
const summary = `${sessionNum} [${sessionType}] ${handoff}`.trim().slice(0, 200);

// Set summary via peers MCP (best-effort)
// The MCP server exposes set_summary tool — we call it indirectly by writing
// a marker file that context-inject.js can pick up to prompt Claude to call it
try {
  const markerPath = require('path').join(require('os').tmpdir(), 'aios-peer-summary.txt');
  fs.writeFileSync(markerPath, summary);
} catch (e) { /* silent */ }

// Output peer info for Claude
console.log(`PEER ANNOUNCE: ${summary}`);
console.log(`Peers MCP active — use list_peers to see other sessions, send_message to coordinate.`);
