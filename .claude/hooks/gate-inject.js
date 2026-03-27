#!/usr/bin/env node
/**
 * gate-inject.js — UserPromptSubmit hook
 * Auto-detects session intent from user message keywords and injects
 * the relevant gate file. Fixes PROCESS_SKIP (30% of corrections)
 * by ensuring gates load before building.
 *
 * Lightweight: pattern matching + fs.existsSync only. Target <100ms.
 * One-shot per intent per session via temp file markers.
 */
const fs = require('fs');
const path = require('path');
const os = require('os');
const cfg = require('./config.js');

// ── Read user message from stdin (hook protocol) ──
let input = '';
try {
  input = fs.readFileSync(0, 'utf-8');
} catch (e) {
  process.exit(0);
}

let message = '';
try {
  const parsed = JSON.parse(input);
  message = parsed.message || parsed.prompt || parsed.content || '';
} catch (e) {
  message = input.trim();
}

if (!message || message.length < 3) {
  process.exit(0);
}

const msgLower = message.toLowerCase();

// ── Intent detection (first match wins) ──
const intents = [
  {
    id: 'demo-prep',
    patterns: ['demo', 'prep', 'cheat sheet', 'call with', 'meeting with', 'presenting to', 'brief for'],
    gate: 'demo-prep.md',
    output: 'GATE AUTO-INJECT: Loading demo-prep gate (domain/gates/demo-prep.md). Follow the checklist.',
  },
  {
    id: 'email',
    patterns: ['email', 'draft', 'follow-up', 'follow up', 'write to', 'send to', 'reply to', 'outreach'],
    gate: 'pre-draft.md',
    output: 'GATE AUTO-INJECT: Loading prospect-email gate. Apply CCQ framework.',
  },
  {
    id: 'cold-call',
    patterns: ['cold call', 'call script', 'phone', 'dial', 'voicemail'],
    gate: 'cold-call.md',
    output: 'GATE AUTO-INJECT: Loading cold-call gate.',
  },
  {
    id: 'prospecting',
    patterns: ['find leads', 'build list', 'enrich', 'prospect', 'scrape'],
    gate: null, // no dedicated gate file yet
    output: 'GATE AUTO-INJECT: Loading prospecting gate.',
  },
];

for (const intent of intents) {
  const matched = intent.patterns.some(p => msgLower.includes(p));
  if (!matched) continue;

  // ── Already injected this intent this session? ──
  const marker = path.join(os.tmpdir(), 'gradata-gate-' + intent.id + '.marker');
  if (fs.existsSync(marker)) {
    process.exit(0);
  }

  // ── Gate file exists? ──
  if (intent.gate) {
    const gatePath = path.join(cfg.GATES_DIR, intent.gate);
    if (!fs.existsSync(gatePath)) {
      // Gate file missing — skip silently
      process.exit(0);
    }
  }

  // ── Inject and mark ──
  try {
    fs.writeFileSync(marker, new Date().toISOString());
  } catch (e) {
    // Can't write marker — inject anyway, just won't deduplicate
  }

  process.stdout.write(intent.output);
  process.exit(0);
}

// No intent matched — exit silently
