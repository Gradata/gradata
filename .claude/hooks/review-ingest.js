#!/usr/bin/env node
/**
 * review-ingest.js — PostToolUse hook (no matcher = fires on all tools)
 *
 * Checks the review queue for completed verdicts from Terminal 2 (reviewer)
 * and emits REVIEW events into system.db for graduation tracking.
 *
 * Only runs in Terminal 1 (work orchestrator). Skips in reviewer terminal.
 * Lightweight: reads directory, checks for new -review.json files, emits events.
 *
 * Review queue: C:/Users/olive/SpritesWork/brain/review-queue/
 * Verdict files: {timestamp}-{id}-review.json
 * After ingesting: renames to {timestamp}-{id}-review.ingested.json
 */

// Only run in work terminal
if (process.env.AIOS_ROLE === 'reviewer') { process.exit(0); }

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');
const cfg = require('./config.js');

const QUEUE_DIR = path.join(cfg.BRAIN_DIR, 'review-queue');
const PYTHON = cfg.PYTHON;
const SCRIPTS = cfg.SCRIPTS;

// Pass through stdin
let input = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', chunk => input += chunk);
process.stdin.on('end', () => {
  let reviewSummary = '';
  try {
    reviewSummary = ingestReviews();
  } catch (e) {
    // Silent failure — never break the tool chain
  }
  // Output review findings as visible message + pass through input
  if (reviewSummary) {
    process.stdout.write(reviewSummary + '\n' + input);
  } else {
    process.stdout.write(input);
  }
});

function ingestReviews() {
  if (!fs.existsSync(QUEUE_DIR)) return '';

  const files = fs.readdirSync(QUEUE_DIR)
    .filter(f => f.endsWith('-review.json'));

  if (files.length === 0) return '';

  const summaries = [];

  for (const file of files) {
    try {
      const filePath = path.join(QUEUE_DIR, file);
      const verdict = JSON.parse(fs.readFileSync(filePath, 'utf8'));

      // Emit REVIEW event to system.db
      const data = JSON.stringify({
        task_id: verdict.task_id || 'unknown',
        verdict: verdict.verdict || 'unknown',
        score: verdict.score || 0,
        findings_count: (verdict.findings || []).length,
        corrections_count: (verdict.corrections || []).length,
        risk_level: verdict.risk_level || 'low',
        escalated: verdict.escalate || false,
        findings: (verdict.findings || []).slice(0, 5),  // Cap at 5 for event size
      });

      const tags = [
        `verdict:${verdict.verdict || 'unknown'}`,
        `risk:${verdict.risk_level || 'low'}`,
      ];
      if (verdict.escalate) tags.push('escalated:true');

      // Use Python emit to write to system.db + events.jsonl
      try {
        execSync(
          `"${PYTHON}" -c "` +
          `import sys; sys.path.insert(0, '${SCRIPTS.replace(/\\/g, '\\\\')}'); ` +
          `from events import emit; ` +
          `emit('REVIEW', 'review-ingest', ${JSON.stringify(data)}, ` +
          `tags=${JSON.stringify(JSON.stringify(tags))})"`,
          { timeout: 5000, stdio: ['pipe', 'pipe', 'pipe'] }
        );
      } catch (emitErr) {
        // Fallback: append to events.jsonl directly
        const event = {
          ts: new Date().toISOString(),
          type: 'REVIEW',
          source: 'review-ingest',
          data: JSON.parse(data),
          tags: tags,
        };
        const jsonlPath = path.join(cfg.BRAIN_DIR, 'events.jsonl');
        fs.appendFileSync(jsonlPath, JSON.stringify(event) + '\n');
      }

      // Build human-readable summary
      const v = verdict.verdict || 'unknown';
      const s = verdict.score || '?';
      const findings = verdict.findings || [];
      const corrections = verdict.corrections || [];
      const esc = verdict.escalate ? ' [ESCALATED]' : '';

      let summary = `REVIEWER ${v.toUpperCase()} (${s}/10)${esc}`;
      if (findings.length > 0) {
        summary += ': ' + findings.slice(0, 3).join('; ');
        if (findings.length > 3) summary += ` (+${findings.length - 3} more)`;
      }
      if (corrections.length > 0) {
        summary += ' | Fix: ' + corrections.slice(0, 2).join('; ');
      }
      summaries.push(summary);

      // Mark as ingested
      const ingestedPath = filePath.replace('-review.json', '-review.ingested.json');
      fs.renameSync(filePath, ingestedPath);

    } catch (fileErr) {
      // Skip malformed files
    }
  }

  if (summaries.length === 0) return '';
  return summaries.join('\n');
}

// Timeout safety
setTimeout(() => process.exit(0), 4000);
