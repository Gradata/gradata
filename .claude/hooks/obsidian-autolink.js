#!/usr/bin/env node
/**
 * obsidian-autolink.js — PostToolUse hook (matcher: Write|Edit)
 *
 * Automatically adds Obsidian wiki links and standardized frontmatter
 * to prospect and session files when they're written/edited.
 *
 * Fires on: Write|Edit to brain/prospects/ or brain/sessions/
 * Does:
 *   1. Prospect files: ensures YAML frontmatter (type, name, company, stage, tags)
 *   2. Session files: adds [[Prospect — Company]] wiki links for known prospect names
 *   3. Both: adds [[session]] or [[prospect]] cross-links where references exist
 *
 * Lightweight: reads file, checks if fixup needed, writes back. No LLM calls.
 */

const fs = require('fs');
const path = require('path');
const cfg = require('./config.js');

const PROSPECTS_DIR = path.join(cfg.BRAIN_DIR, 'prospects');
const SESSIONS_DIR = path.join(cfg.BRAIN_DIR, 'sessions');

function readStdin() {
  try {
    if (process.stdin.isTTY) return null;
    return JSON.parse(fs.readFileSync(0, 'utf8'));
  } catch { return null; }
}

function getProspectNames() {
  // Build map of prospect names to filenames (without .md)
  const map = {};
  try {
    const files = fs.readdirSync(PROSPECTS_DIR).filter(f => f.endsWith('.md'));
    for (const f of files) {
      const base = f.replace('.md', '');
      // Parse "Name — Company" format
      const parts = base.split(' — ');
      if (parts.length >= 2) {
        const name = parts[0].trim();
        map[name] = base;
      }
    }
  } catch {}
  return map;
}

function getSessionFiles() {
  // Get list of session file basenames
  try {
    return fs.readdirSync(SESSIONS_DIR)
      .filter(f => f.endsWith('.md'))
      .map(f => f.replace('.md', ''));
  } catch { return []; }
}

function ensureProspectFrontmatter(filePath, content) {
  const basename = path.basename(filePath, '.md');
  const parts = basename.split(' — ');
  if (parts.length < 2) return content; // Can't parse name/company

  const name = parts[0].trim();
  const company = parts.slice(1).join(' — ').trim();

  // Already has frontmatter?
  if (content.startsWith('---\n')) {
    // Check if it has all required fields
    const fmEnd = content.indexOf('\n---\n', 4);
    if (fmEnd === -1) return content;
    const fm = content.substring(4, fmEnd);
    if (fm.includes('type:') && fm.includes('name:') && fm.includes('company:')) {
      return content; // Already complete
    }
    // Has frontmatter but missing fields — add them
    const lines = fm.split('\n');
    const fields = {};
    for (const line of lines) {
      const m = line.match(/^(\w+):\s*(.*)/);
      if (m) fields[m[1]] = m[2];
    }
    if (!fields.type) fields.type = 'prospect';
    if (!fields.name) fields.name = name;
    if (!fields.company) fields.company = company;
    if (!fields.stage) fields.stage = detectStage(content);

    const newFm = Object.entries(fields).map(([k, v]) => `${k}: ${v}`).join('\n');
    return `---\n${newFm}\n${content.substring(fmEnd)}`;
  }

  // No frontmatter — add it
  const stage = detectStage(content);
  const fm = [
    '---',
    `type: prospect`,
    `name: ${name}`,
    `company: ${company}`,
    `stage: ${stage}`,
    '---',
    '',
  ].join('\n');
  return fm + content;
}

function detectStage(content) {
  const lower = content.toLowerCase();
  if (lower.includes('closed-won') || lower.includes('closed won')) return 'closed-won';
  if (lower.includes('closed-lost') || lower.includes('closed lost')) return 'closed-lost';
  if (lower.includes('onboarding')) return 'onboarding';
  if (lower.includes('proposal')) return 'proposal-made';
  if (lower.includes('demo-done') || lower.includes('demo done') || lower.includes('post-demo')) return 'demo-done';
  if (lower.includes('demo-scheduled') || lower.includes('demo scheduled') || lower.includes('demo booked')) return 'demo-scheduled';
  if (lower.includes('no-show')) return 'no-show';
  if (lower.includes('replied') || lower.includes('reply')) return 'replied';
  return 'lead';
}

function addWikiLinksToSession(content, prospectMap) {
  let updated = content;
  for (const [name, fileBase] of Object.entries(prospectMap)) {
    // Skip very short names (Tom, Sam) — too many false matches
    if (name.length < 5) continue;
    // Skip if already wiki-linked
    const wikiPattern = new RegExp(`\\[\\[${fileBase.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}`, 'g');
    if (wikiPattern.test(updated)) continue;
    // Find unlinked mentions of the prospect name (not inside [[ ]])
    const namePattern = new RegExp(`(?<!\\[\\[)\\b(${name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})\\b(?!.*?\\]\\])`, 'g');
    // Only replace first occurrence
    let replaced = false;
    updated = updated.replace(namePattern, (match) => {
      if (replaced) return match;
      replaced = true;
      return `[[${fileBase}|${name}]]`;
    });
  }
  return updated;
}

function addSessionLinksToProspect(content, sessionFiles) {
  let updated = content;
  // Find session references like "Session 65", "S65", etc.
  const sessionPattern = /\b[Ss](?:ession\s+)?(\d{2,3})\b/g;
  let match;
  while ((match = sessionPattern.exec(content)) !== null) {
    const num = match[1];
    // Find matching session file
    const sessionFile = sessionFiles.find(f => f.includes(`S${num}`));
    if (!sessionFile) continue;
    // Check if already linked
    if (content.includes(`[[${sessionFile}`)) continue;
    // Replace first unlinked occurrence
    const literal = match[0];
    if (!updated.includes(`[[${sessionFile}|${literal}]]`)) {
      updated = updated.replace(literal, `[[${sessionFile}|${literal}]]`);
    }
  }
  return updated;
}

// ── Main ──────────────────────────────────────────────────────────

try {
  const toolData = readStdin();
  if (!toolData) process.exit(0);

  const toolName = toolData.tool_name || '';
  if (toolName !== 'Write' && toolName !== 'Edit') process.exit(0);

  const toolInput = toolData.tool_input || {};
  const filePath = (toolInput.file_path || '').replace(/\\/g, '/');

  const isProspect = filePath.includes('/prospects/') && filePath.endsWith('.md');
  const isSession = filePath.includes('/sessions/') && filePath.endsWith('.md') && !filePath.includes('loop-state');

  if (!isProspect && !isSession) process.exit(0);

  // Read current file content
  const normalizedPath = filePath.replace(/\//g, path.sep);
  if (!fs.existsSync(normalizedPath)) process.exit(0);
  let content = fs.readFileSync(normalizedPath, 'utf8');
  const original = content;

  if (isProspect) {
    content = ensureProspectFrontmatter(normalizedPath, content);
    const sessionFiles = getSessionFiles();
    content = addSessionLinksToProspect(content, sessionFiles);
  }

  if (isSession) {
    const prospectMap = getProspectNames();
    content = addWikiLinksToSession(content, prospectMap);
  }

  // Only write if changed
  if (content !== original) {
    fs.writeFileSync(normalizedPath, content, 'utf8');
  }
} catch (e) {
  // Never break the tool chain
}

// Timeout safety
setTimeout(() => process.exit(0), 3000);
