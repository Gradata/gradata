#!/usr/bin/env node
/**
 * Cache Warmer — keeps statusline data fresh in the background.
 *
 * Launched at SessionStart. The hook calls this script directly;
 * it spawns a detached child to do the actual work and exits
 * immediately so the hook doesn't block.
 *
 * Refreshes: Pipedrive deal summary, brain scores, pipeline status.
 * Writes to the same tmpdir cache files the statusline reads.
 *
 * Self-terminates after 4 hours (session max).
 */

const fs = require('fs');
const path = require('path');
const os = require('os');
const { execSync, spawn } = require('child_process');

const PID_FILE = path.join(os.tmpdir(), 'aios-cache-warmer.pid');

// When called without --worker, spawn a detached child and exit immediately
if (!process.argv.includes('--worker')) {
  // Kill existing worker if running (prevent zombie pile-up)
  try {
    if (fs.existsSync(PID_FILE)) {
      const oldPid = parseInt(fs.readFileSync(PID_FILE, 'utf8').trim());
      if (oldPid) process.kill(oldPid, 'SIGTERM');
    }
  } catch { /* process already dead — fine */ }

  const child = spawn(process.execPath, [__filename, '--worker'], {
    detached: true,
    stdio: 'ignore',
    windowsHide: true
  });
  child.unref();
  process.exit(0);
}

// --- Worker mode (runs in background) ---

// Write PID so future launches can kill us
fs.writeFileSync(PID_FILE, String(process.pid));
process.on('exit', () => { try { fs.unlinkSync(PID_FILE); } catch {} });

const INTERVAL_MS = 60_000;       // 60 seconds
const MAX_RUNTIME_MS = 4 * 60 * 60 * 1000; // 4 hours
const PIPEDRIVE_CACHE = path.join(os.tmpdir(), 'aios-pipedrive-cache.json');
const BRAIN_SCORES_CACHE = path.join(os.tmpdir(), 'aios-brain-scores-cache.json');

const startTime = Date.now();

function refreshPipedrive() {
  try {
    const result = execSync(
      'python "C:/Users/olive/SpritesWork/brain/scripts/api_sync.py" pipedrive --json',
      { timeout: 15000, encoding: 'utf8', stdio: ['pipe', 'pipe', 'pipe'] }
    );
    const data = JSON.parse(result);
    fs.writeFileSync(PIPEDRIVE_CACHE, JSON.stringify({ ...data, ts: Date.now() }));
  } catch { /* silent */ }
}

function refreshBrainScores() {
  try {
    const result = execSync(
      'python "C:/Users/olive/SpritesWork/brain/scripts/brain_scores_cli.py" --json',
      { timeout: 10000, encoding: 'utf8', stdio: ['pipe', 'pipe', 'pipe'] }
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
