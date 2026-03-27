#!/usr/bin/env node
/**
 * qwen-lint.js -- PostToolUse hook (matcher: Write|Edit)
 * Runs Qwen via Ollama locally for zero-cost lint checks.
 * Falls back silently if Ollama is not running.
 * Async: runs in background, surfaces issues via stderr.
 */

const http = require('http');
const path = require('path');
const fs = require('fs');

const PROFILE = process.env.GRADATA_HOOK_PROFILE || 'standard';
if (PROFILE === 'minimal') process.exit(0);

const OLLAMA_URL = process.env.OLLAMA_URL || 'http://localhost:11434';
const OLLAMA_MODEL = process.env.OLLAMA_MODEL || 'qwen2.5-coder:14b';

const CODE_EXTENSIONS = new Set([
  '.js', '.ts', '.jsx', '.tsx', '.py', '.sh',
  '.css', '.html', '.json', '.sql',
]);

const SKIP_PATHS = [
  'node_modules', '.git', 'brain/events.jsonl', 'system.db',
  'prospects/', 'sessions/', 'MEMORY.md',
];

function readStdin() {
  try {
    if (process.stdin.isTTY) return null;
    return JSON.parse(fs.readFileSync(0, 'utf8'));
  } catch { return null; }
}

function isCodeFile(filePath) {
  if (!filePath) return false;
  const ext = path.extname(filePath).toLowerCase();
  if (!CODE_EXTENSIONS.has(ext)) return false;
  const normalized = filePath.replace(/\\/g, '/');
  return !SKIP_PATHS.some(p => normalized.includes(p));
}

function queryOllama(prompt) {
  return new Promise((resolve, reject) => {
    const url = new URL('/api/generate', OLLAMA_URL);
    const payload = JSON.stringify({
      model: OLLAMA_MODEL,
      prompt,
      stream: false,
      options: { num_predict: 200, temperature: 0.1 },
    });

    const req = http.request(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      timeout: 15000,
    }, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try {
          const parsed = JSON.parse(data);
          resolve(parsed.response || '');
        } catch { resolve(''); }
      });
    });

    req.on('error', () => resolve('')); // silent fail if Ollama not running
    req.on('timeout', () => { req.destroy(); resolve(''); });
    req.write(payload);
    req.end();
  });
}

async function main() {
  const toolData = readStdin();
  if (!toolData) return;

  const toolName = toolData.tool_name || '';
  if (toolName !== 'Write' && toolName !== 'Edit') return;

  const toolInput = toolData.tool_input || {};
  const filePath = toolInput.file_path || '';
  if (!isCodeFile(filePath)) return;

  const content = toolInput.content || toolInput.new_string || '';
  if (!content || content.length < 30) return;

  const fileName = path.basename(filePath);
  const snippet = content.slice(0, 3000); // keep prompt small for local model

  const prompt = [
    `You are a code linter. Review this code for obvious bugs ONLY.`,
    `Skip style issues. Report max 3 issues. If clean, say "CLEAN".`,
    `File: ${fileName}`,
    ``,
    snippet,
  ].join('\n');

  const result = await queryOllama(prompt);
  if (result && !result.includes('CLEAN') && result.trim().length > 10) {
    const lines = result.trim().split('\n').slice(0, 5);
    process.stderr.write(`\n[qwen-lint] ${fileName}:\n`);
    for (const line of lines) {
      if (line.trim()) process.stderr.write(`  ${line.trim()}\n`);
    }
  }
}

main().catch(() => {}); // never throw
