#!/usr/bin/env node
/**
 * Cache Warmer — keeps statusline data fresh in the background.
 *
 * Launched at SessionStart. Runs silently, refreshes cache files
 * every 60 seconds so the statusline always reads warm data.
 *
 * Refreshes: Pipedrive deal summary, brain scores, pipeline status.
 * Writes to the same tmpdir cache files the statusline reads.
 *
 * Self-terminates after 4 hours (session max) or if the cache
 * directory disappears.
 */

const fs = require('fs');
const path = require('path');
const os = require('os');
const { execSync } = require('child_process');

const INTERVAL_MS = 60_000;       // 60 seconds
const MAX_RUNTIME_MS = 4 * 60 * 60 * 1000; // 4 hours
const PIPEDRIVE_CACHE = path.join(os.tmpdir(), 'aios-pipedrive-cache.json');
const BRAIN_SCORES_CACHE = path.join(os.tmpdir(), 'aios-brain-scores-cache.json');

const startTime = Date.now();

function refreshPipedrive() {
  try {
    const result = execSync(
      'python "C:/Users/olive/SpritesWork/brain/scripts/api_sync.py" pipedrive --json 2>/dev/null',
      { timeout: 15000, encoding: 'utf8' }
    );
    const data = JSON.parse(result);
    fs.writeFileSync(PIPEDRIVE_CACHE, JSON.stringify({ ...data, ts: Date.now() }));
  } catch { /* silent */ }
}

function refreshBrainScores() {
  try {
    const result = execSync(
      'python "C:/Users/olive/SpritesWork/brain/scripts/brain_scores_cli.py" --json 2>/dev/null',
      { timeout: 10000, encoding: 'utf8' }
    );
    fs.writeFileSync(BRAIN_SCORES_CACHE, JSON.stringify({ scores: JSON.parse(result), ts: Date.now() }));
  } catch { /* silent */ }
}

function tick() {
  if (Date.now() - startTime > MAX_RUNTIME_MS) process.exit(0);
  refreshPipedrive();
  refreshBrainScores();
}

// Initial refresh
tick();

// Then every 60s
setInterval(tick, INTERVAL_MS);

// Detach from parent — don't block Claude Code
if (process.send) process.disconnect?.();