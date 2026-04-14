#!/usr/bin/env node
/**
 * Gradata bundled rule-to-hook dispatcher.
 *
 * Reads _manifest.json from its own directory and evaluates every rule
 * against a single PreToolUse / PostToolUse payload in one node invocation.
 *
 * This replaces spawning one node process per installed rule (~50-150ms
 * startup each). At 6 rules that saved ~300-900ms per tool call.
 *
 * Manifest entry shape:
 *   {
 *     "slug": "never-use-em-dashes",
 *     "template": "regex_replace" | "fstring_block" | "root_file_save"
 *                 | "destructive_block" | "secret_scan" | "file_size_check"
 *                 | "auto_test",
 *     "template_arg": "<pattern literal or line limit>",
 *     "source_hash": "abc123def456",
 *     "rule_text": "Never use em dashes"
 *   }
 *
 * Exits:
 *   0 — no rule blocked
 *   2 — at least one rule blocked (first match wins); block reason emitted
 *       as JSON on stdout in the same shape individual hooks used:
 *       {"decision": "block", "reason": "..."}
 *
 * Never throws on malformed payload or manifest — errors log to stderr and
 * exit 0 (fail-open, same policy as individual hooks).
 */
'use strict';

const fs = require('fs');
const path = require('path');

if (process.env.GRADATA_BYPASS === '1') process.exit(0);

let input;
try {
  if (process.stdin.isTTY) process.exit(0);
  const raw = fs.readFileSync(0, 'utf8');
  if (!raw.trim()) process.exit(0);
  input = JSON.parse(raw);
} catch (e) {
  process.exit(0);
}

const manifestPath = path.join(__dirname, '_manifest.json');
let manifest;
try {
  manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
} catch (e) {
  // No manifest or malformed — nothing to do.
  process.exit(0);
}

if (!Array.isArray(manifest) || manifest.length === 0) process.exit(0);

const toolInput = input.tool_input || {};
const toolName = input.tool_name || '';

function contentForTemplate(tmpl) {
  if (tmpl === 'destructive_block' || tmpl === 'fstring_block') {
    return toolInput.command || toolInput.content || toolInput.new_string || '';
  }
  if (tmpl === 'root_file_save') {
    return toolInput.file_path || '';
  }
  if (tmpl === 'auto_test') {
    return toolInput.file_path || '';
  }
  // regex_replace, secret_scan, file_size_check
  return toolInput.content || toolInput.new_string || toolInput.command || '';
}

function blockMessage(entry, extra) {
  const base = `\u26d4 BLOCKED by graduated rule: ${entry.rule_text || entry.slug}`;
  const tail = extra ? `\n${extra}` : '';
  const suffix = `\n\nSet GRADATA_BYPASS=1 to override.`;
  return `${base}${tail}${suffix} [rule=${entry.slug}]`;
}

function emitBlock(entry, msg) {
  process.stdout.write(JSON.stringify({ decision: 'block', reason: msg }));
  process.stderr.write(`gradata-dispatcher: blocked by rule ${entry.slug}\n`);
}

function runEntry(entry) {
  const tmpl = entry.template;
  const content = contentForTemplate(tmpl);

  try {
    if (tmpl === 'file_size_check') {
      const limit = parseInt(entry.template_arg || entry.line_limit || '500', 10);
      if (!Number.isFinite(limit)) return false;
      const lineCount = String(content).split('\n').length;
      if (lineCount > limit) {
        emitBlock(entry, blockMessage(entry, `file has ${lineCount} lines (limit ${limit}).`));
        return true;
      }
      return false;
    }

    if (tmpl === 'auto_test') {
      // auto_test is PostToolUse and runs pytest. We don't run child
      // processes inside the bundled dispatcher — the PostToolUse
      // runner falls back to the legacy per-file path for auto_test.
      return false;
    }

    // regex-family templates
    if (!entry.template_arg) return false;
    let pattern;
    try { pattern = new RegExp(entry.template_arg); }
    catch { return false; }

    if (pattern.test(String(content))) {
      emitBlock(entry, blockMessage(entry));
      return true;
    }
    return false;
  } catch (e) {
    return false;
  }
}

for (const entry of manifest) {
  if (!entry || typeof entry !== 'object') continue;
  if (!entry.template || !entry.slug) continue;
  const blocked = runEntry(entry);
  if (blocked) process.exit(2);
}

process.exit(0);
