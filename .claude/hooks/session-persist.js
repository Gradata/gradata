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

const BRAIN_PATH = 'C:/Users/olive/SpritesWork/brain';
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

  // Get modified files from git
  let filesModified = [];
  try {
    const gitOutput = execSync(
      `git -C "${path.join('C:', 'Users', 'olive', 'OneDrive', 'Desktop', 'Sprites Work')}" diff --name-only HEAD 2>&1`,
      { encoding: 'utf8', timeout: 5000 }
    ).trim();
    if (gitOutput) filesModified = gitOutput.split('\n').slice(0, 30);
  } catch (e) { /* git not available or no changes */ }

  // Get brain repo modified files
  try {
    const brainGit = execSync(
      `git -C "${BRAIN_PATH}" diff --name-only HEAD 2>&1`,
      { encoding: 'utf8', timeout: 5000 }
    ).trim();
    if (brainGit) {
      filesModified = filesModified.concat(
        brainGit.split('\n').slice(0, 20).map(f => `brain/${f}`)
      );
    }
  } catch (e) { /* no brain changes */ }

  const persistData = {
    session: sessionNum,
    timestamp: new Date().toISOString(),
    files_modified: filesModified,
  };

  const filename = `session-${String(sessionNum).padStart(3, '0')}.json`;
  fs.writeFileSync(
    path.join(PERSIST_DIR, filename),
    JSON.stringify(persistData, null, 2)
  );

} catch (e) {
  // Silent failure — never block session end
}
