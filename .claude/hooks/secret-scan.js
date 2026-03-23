#!/usr/bin/env node
/**
 * secret-scan.js -- PostToolUse hook (matcher: Write|Edit)
 * Scans written/edited content for secrets (API keys, tokens, private keys).
 * Non-blocking -- warnings only via stderr.
 * Profile: standard + strict (skip minimal)
 */

const PROFILE = process.env.AIOS_HOOK_PROFILE || 'standard';
if (PROFILE === 'minimal') process.exit(0);

// Patterns from agent-manifests.json guardrails.sensitive_data_patterns + extras
const SECRET_PATTERNS = [
  { name: 'api_key (sk-...)', regex: /sk-[a-zA-Z0-9]{20,}/g },
  { name: 'aws_access_key', regex: /AKIA[A-Z0-9]{16}/g },
  { name: 'private_key', regex: /-----BEGIN[A-Z ]*PRIVATE KEY-----/g },
  { name: 'github_pat', regex: /ghp_[a-zA-Z0-9]{36}/g },
  { name: 'jwt_token', regex: /eyJ[a-zA-Z0-9_-]{20,}\.eyJ[a-zA-Z0-9_-]{20,}\.[a-zA-Z0-9_-]{20,}/g },
  { name: 'generic_secret (password=)', regex: /(?:password|api_key|token|secret)\s*[=:]\s*["']?[^\s"']{8,}/gi },
];

try {
  let input = '';
  if (!process.stdin.isTTY) {
    const fs = require('fs');
    input = fs.readFileSync(0, 'utf8');
  }
  if (!input) process.exit(0);

  let toolData = {};
  try { toolData = JSON.parse(input); } catch (e) { process.exit(0); }

  // Only activate for Write and Edit tools
  const toolName = toolData.tool_name || '';
  if (toolName !== 'Write' && toolName !== 'Edit') process.exit(0);

  // Extract content to scan
  const toolInput = toolData.tool_input || {};
  const textToScan = toolInput.content || toolInput.new_string || '';
  if (!textToScan) process.exit(0);

  // Scan for secrets
  const findings = [];
  for (const { name, regex } of SECRET_PATTERNS) {
    const matches = textToScan.match(regex);
    if (matches) {
      for (const m of matches) {
        const preview = m.length > 12 ? m.slice(0, 8) + '...' : m;
        findings.push({ name, preview });
      }
    }
  }

  if (findings.length > 0) {
    const filePath = toolInput.file_path || 'unknown';
    process.stderr.write(`[secret-scan] WARNING: ${findings.length} potential secret(s) detected in ${filePath}:\n`);
    for (const f of findings) {
      process.stderr.write(`  - ${f.name}: ${f.preview}\n`);
    }
  }
} catch (e) {
  // Silent failure -- hooks must not block
}
