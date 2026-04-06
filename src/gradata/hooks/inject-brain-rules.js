#!/usr/bin/env node
/**
 * inject-brain-rules.js — SessionStart hook
 *
 * Reads graduated rules from brain/lessons.md, scores them against
 * the current session context, and injects the top-N most relevant
 * as a <brain-rules> block into the session.
 *
 * Scoring formula (aligned with Python rule_ranker.py):
 *   30% scope match   — does the task type match the rule category?
 *   25% confidence     — RULE:0.92 > PATTERN:0.65
 *   20% context        — QMD keyword boost (applied separately)
 *   15% recency        — recently fired rules rank higher
 *   10% fire count     — battle-tested rules rank higher
 *
 * Budget: max 10 rules, ~500 tokens. Prevents context bloat.
 */
const fs = require('fs');
const path = require('path');
const cfg = require('../config.js');

const BRAIN = cfg.BRAIN_DIR;
const LESSONS_PATH = path.join(BRAIN, 'lessons.md');
const MAX_RULES = 10;
const MIN_CONFIDENCE = 0.60; // Only PATTERN and RULE level

try {
  if (!fs.existsSync(LESSONS_PATH)) {
    // No lessons yet — nothing to inject
    process.exit(0);
  }

  const text = fs.readFileSync(LESSONS_PATH, 'utf8');
  const lines = text.split('\n');

  // Parse lessons
  const lessons = [];
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim();
    if (!line) continue;

    // Match: [2026-03-30] [RULE:1.00] PROCESS: description
    const match = line.match(/^\[(\d{4}-\d{2}-\d{2})\]\s+\[(RULE|PATTERN|INSTINCT):([\d.]+)\]\s+(\w+):\s+(.+)/);
    if (!match) continue;

    const [, date, state, confStr, category, description] = match;
    const confidence = parseFloat(confStr);

    // Skip INSTINCT — not proven enough
    if (state === 'INSTINCT') continue;
    if (confidence < MIN_CONFIDENCE) continue;

    // Parse fire count and sessions since fire from next line
    let fireCount = 0;
    let sessionsSinceFire = 999;
    if (i + 1 < lines.length) {
      const metaLine = lines[i + 1].trim();
      const fcMatch = metaLine.match(/Fire count:\s*(\d+)/);
      const ssMatch = metaLine.match(/Sessions since fire:\s*(\d+)/);
      if (fcMatch) fireCount = parseInt(fcMatch[1]);
      if (ssMatch) sessionsSinceFire = parseInt(ssMatch[1]);
    }

    lessons.push({
      date, state, confidence, category, description,
      fireCount, sessionsSinceFire,
    });
  }

  if (lessons.length === 0) {
    process.exit(0);
  }

  // Score each lesson
  // We don't know the task type yet at session start, so scope match
  // is based on category breadth (generic categories score higher)
  const genericCategories = new Set([
    'PROCESS', 'TONE', 'CONTENT', 'STRUCTURE', 'FORMAT',
    'SESSION_CORRECTION', 'QUALITY',
  ]);

  const scored = lessons.map(l => {
    // Scope: generic categories are always relevant
    const scopeScore = genericCategories.has(l.category) ? 1.0 : 0.5;

    // Confidence: normalize 0.6-1.0 → 0-1
    const confScore = Math.min(1.0, (l.confidence - 0.6) / 0.4);

    // Recency: sessions since fire, decay exponentially
    const recencyScore = Math.exp(-l.sessionsSinceFire / 50);

    // Fire count: log scale, capped
    const fireScore = Math.min(1.0, Math.log(l.fireCount + 1) / Math.log(100));

    // Weights aligned with Python rule_ranker.py (30/25/20/15/10)
    // Context relevance (20%) is added later via QMD boost if available
    const total = (0.30 * scopeScore) + (0.25 * confScore) + (0.15 * recencyScore) + (0.10 * fireScore);

    return { ...l, score: total };
  });

  // Sort by score, take top N
  scored.sort((a, b) => b.score - a.score);
  const topRules = scored.slice(0, MAX_RULES);

  // If we have too many rules, try QMD for smarter retrieval
  let rulesBlock;
  let method = 'score';

  // Try QMD for context-aware boosting (synchronous to avoid race condition)
  try {
    const { execSync } = require('child_process');
    const qmdPayload = '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"ctx_search","arguments":{"query":"current working context","limit":5}},"id":1}';
    const curlResult = execSync(
      `curl -s -m 2 -X POST http://localhost:8181/mcp -H "Content-Type: application/json" -d '${qmdPayload}'`,
      { encoding: 'utf8', timeout: 3000 }
    );
    const r = JSON.parse(curlResult);
    const qmdText = (r.result && r.result.content && r.result.content[0] && r.result.content[0].text) || '';
    if (qmdText.length > 10) {
      method = 'qmd+score';
      const contextKeywords = qmdText.toLowerCase().split(/\W+/).filter(w => w.length > 3);
      for (const s of scored) {
        const desc = (s.description || '').toLowerCase();
        const matches = contextKeywords.filter(kw => desc.includes(kw)).length;
        if (matches > 0) {
          s.score += 0.15 * Math.min(1.0, matches / Math.max(1, contextKeywords.length));
        }
      }
      scored.sort((a, b) => b.score - a.score);
    }
  } catch (_) {
    // QMD not available — continue with score-only ranking
  }

  // Format as brain-rules block
  rulesBlock = topRules.map(r =>
    `[${r.state}:${r.confidence.toFixed(2)}] ${r.category}: ${r.description}`
  ).join('\n');

  const output = {
    result: `<brain-rules source="gradata" method="${method}" count="${topRules.length}" budget="top-${MAX_RULES}">\n${rulesBlock}\n</brain-rules>`,
  };

  process.stdout.write(JSON.stringify(output));

} catch (e) {
  // Silent failure — never block session start
  process.stderr.write(`[inject-brain-rules] ${e.message}\n`);
}
