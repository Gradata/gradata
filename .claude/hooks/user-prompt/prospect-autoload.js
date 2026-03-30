#!/usr/bin/env node
/**
 * prospect-autoload.js — UserPromptSubmit hook
 *
 * Scans Oliver's message for known prospect names and auto-surfaces
 * their brain file context. Removes the need to say "load the prospect file"
 * or "remind me about Tim."
 *
 * How it works:
 *   1. Reads prospect filenames from brain/prospects/
 *   2. Extracts first+last names and company names
 *   3. Fuzzy-matches against Oliver's message
 *   4. If match found, emits the prospect file summary as hook output
 *
 * Fires on: UserPromptSubmit (every message)
 * Cost: <50ms (directory scan + string matching, no LLM or DB calls)
 */

const fs = require('fs');
const path = require('path');
const cfg = require('../config.js');

const PROSPECTS_DIR = path.join(cfg.BRAIN_DIR, 'prospects');

// Pass through stdin (required for UserPromptSubmit hooks)
let input = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', chunk => input += chunk);
process.stdin.on('end', () => {
  let context = '';
  try {
    context = findProspectContext(input);
  } catch (e) {
    // Silent — never break the prompt chain
  }
  if (context) {
    process.stdout.write(context + '\n' + input);
  } else {
    process.stdout.write(input);
  }
});

function findProspectContext(userMessage) {
  if (!userMessage || userMessage.length < 3) return '';
  const msg = userMessage.toLowerCase();

  // Skip system/startup messages
  if (msg.includes('session') && (msg.includes('start') || msg.includes('system'))) return '';
  if (msg.includes('wrap up')) return '';

  // Build prospect lookup
  let files;
  try {
    files = fs.readdirSync(PROSPECTS_DIR).filter(f => f.endsWith('.md'));
  } catch { return ''; }

  const matches = [];

  for (const file of files) {
    const base = file.replace('.md', '');
    const parts = base.split(' — ');
    if (parts.length < 2) continue;

    const fullName = parts[0].trim();
    const company = parts.slice(1).join(' — ').trim();
    const nameParts = fullName.split(' ');
    const firstName = nameParts[0] || '';
    const lastName = nameParts[nameParts.length - 1] || '';

    // Match strategies (most specific first)
    let matched = false;

    // Full name match (e.g., "Tim Sok")
    if (fullName.length >= 5 && msg.includes(fullName.toLowerCase())) {
      matched = true;
    }
    // Company match (e.g., "Henge", "Vantaca") — min 4 chars to avoid "i" etc.
    else if (company.length >= 4 && msg.includes(company.toLowerCase())) {
      matched = true;
    }
    // Last name match (only if 5+ chars to avoid false positives)
    else if (lastName.length >= 5 && msg.includes(lastName.toLowerCase())) {
      matched = true;
    }

    if (matched) {
      matches.push({ file, base, fullName, company });
    }
  }

  if (matches.length === 0) return '';

  // Load up to 2 matched prospect files (cap context injection)
  const summaries = [];
  for (const match of matches.slice(0, 2)) {
    try {
      const filePath = path.join(PROSPECTS_DIR, match.file);
      const content = fs.readFileSync(filePath, 'utf8');
      // Take first 40 lines as summary (frontmatter + key info)
      const lines = content.split('\n').slice(0, 40);
      summaries.push(
        `[AUTO-LOADED: ${match.fullName} @ ${match.company}]\n` +
        lines.join('\n')
      );
    } catch {}
  }

  if (summaries.length === 0) return '';
  return summaries.join('\n\n---\n\n');
}

// Timeout safety
setTimeout(() => process.exit(0), 3000);
