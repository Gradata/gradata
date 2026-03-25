/**
 * config.js — Shared hook configuration (SDK-portable)
 * =====================================================
 * Single source of truth for all paths used by hooks.
 * Every hook should: const cfg = require('./config.js');
 *
 * All paths resolve from environment variables with platform-aware defaults.
 * To make SDK-portable: set BRAIN_DIR, WORKING_DIR, PYTHON_PATH env vars.
 */
const path = require('path');
const os = require('os');

// ── Core Paths (env-var driven, with current-machine defaults) ──
const BRAIN_DIR = process.env.BRAIN_DIR || 'C:/Users/olive/SpritesWork/brain';
const WORKING_DIR = process.env.WORKING_DIR || 'C:/Users/olive/OneDrive/Desktop/Sprites Work';
const PYTHON = process.env.PYTHON_PATH || 'C:/Users/olive/AppData/Local/Programs/Python/Python312/python.exe';

// ── Derived Paths ──
const SCRIPTS = path.join(BRAIN_DIR, 'scripts');
const PROSPECTS_DIR = path.join(BRAIN_DIR, 'prospects');
const SYSTEM_DB = path.join(BRAIN_DIR, 'system.db');
const LOOP_STATE = path.join(BRAIN_DIR, 'loop-state.md');
const EVENTS_JSONL = path.join(BRAIN_DIR, 'events.jsonl');
const SESSIONS_DIR = path.join(BRAIN_DIR, 'sessions');
const DOMAIN_DIR = path.join(WORKING_DIR, 'domain');
const STARTUP_BRIEF = path.join(DOMAIN_DIR, 'pipeline', 'startup-brief.md');
const GATES_DIR = path.join(DOMAIN_DIR, 'gates');
const HOOKS_DIR = path.join(WORKING_DIR, '.claude', 'hooks');
const LESSONS_FILE = path.join(WORKING_DIR, '.claude', 'lessons.md');
const COMPACT_SNAPSHOT = path.join(os.tmpdir(), 'aios-compact-snapshot.json');

module.exports = {
  BRAIN_DIR,
  WORKING_DIR,
  PYTHON,
  SCRIPTS,
  PROSPECTS_DIR,
  SYSTEM_DB,
  LOOP_STATE,
  EVENTS_JSONL,
  SESSIONS_DIR,
  DOMAIN_DIR,
  STARTUP_BRIEF,
  GATES_DIR,
  HOOKS_DIR,
  LESSONS_FILE,
  COMPACT_SNAPSHOT,
};
