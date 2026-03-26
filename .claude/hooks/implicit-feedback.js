/**
 * Implicit Feedback Detector — UserPromptSubmit hook
 *
 * Scans Oliver's prompts for pushback, reminders, gaps, and challenges
 * that indicate missed lessons. Emits IMPLICIT_FEEDBACK events to brain.
 *
 * These signals are invisible to the draft→final correction pipeline.
 * Novel signal source — neither Mem0 nor Letta captures this.
 */

const { execSync } = require('child_process');
const fs = require('fs');

// Read user prompt from stdin (Claude Code passes it as JSON)
let input = '';
try {
  input = fs.readFileSync(0, 'utf8');
} catch { process.exit(0); }

let data;
try {
  data = JSON.parse(input);
} catch { process.exit(0); }

const text = (data.prompt || data.content || data.message || '').toLowerCase();
if (!text || text.length < 10) process.exit(0);

const signals = [];

// Pushback: user is correcting or disagreeing
const pushback = [
  /are you sure/i, /that'?s (?:wrong|not right|incorrect)/i,
  /no[,.]?\s+(?:not that|don't|stop)/i, /why (?:did|didn't|aren't) you/i,
  /not accurate/i,
];
for (const p of pushback) { if (p.test(text)) signals.push('PUSHBACK'); }

// Reminder: user is repeating an instruction
const reminder = [
  /make sure/i, /don'?t forget/i, /remember to/i,
  /i (?:already|just) (?:told|said|asked)/i, /like i said/i,
];
for (const p of reminder) { if (p.test(text)) signals.push('REMINDER'); }

// Gap: user pointing out something missed
const gap = [
  /what about/i, /you (?:forgot|missed|skipped|dropped|ignored)/i,
  /did you (?:check|verify|test|review)/i,
];
for (const p of gap) { if (p.test(text)) signals.push('GAP'); }

// Challenge: user questioning quality
const challenge = [
  /are we (?:sure|missing)/i, /won'?t (?:that|people|this)/i,
  /i feel like/i, /is that (?:right|correct)/i,
];
for (const p of challenge) { if (p.test(text)) signals.push('CHALLENGE'); }

if (signals.length === 0) process.exit(0);

// Deduplicate
const unique = [...new Set(signals)];
const snippet = text.slice(0, 100).replace(/["\\\n]/g, ' ');

// Log event to brain
try {
  execSync(
    `python "C:/Users/olive/SpritesWork/brain/scripts/events.py" ` +
    `--type IMPLICIT_FEEDBACK --source implicit-feedback-hook ` +
    `--data "{\\"signals\\": \\"${unique.join(',')}\\", \\"snippet\\": \\"${snippet}\\"}"`,
    { timeout: 5000, stdio: 'ignore' }
  );
} catch { /* best-effort */ }

// Output for Claude to see
console.log(`IMPLICIT FEEDBACK [${unique.join(', ')}]: Check if this signals a missed lesson.`);
