#!/usr/bin/env node
/**
 * secret-scan.js -- PostToolUse hook (matcher: Write|Edit)
 * Scans written/edited content for secrets (API keys, tokens, private keys).
 * Non-blocking -- warnings only via stderr.
 * Profile: standard + strict (skip minimal)
 */

const PROFILE = process.env.GRADATA_HOOK_PROFILE || 'standard';
if (PROFILE === 'minimal') process.exit(0);

// Patterns from agent-manifests.json guardrails.sensitive_data_patterns + extras
const SECRET_PATTERNS = [
  // Cloud / AI providers
  { name: 'openai_key (sk-...)', regex: /sk-[a-zA-Z0-9]{20,}/g },
  { name: 'aws_access_key', regex: /AKIA[A-Z0-9]{16}/g },
  { name: 'private_key', regex: /-----BEGIN[A-Z ]*PRIVATE KEY-----/g },
  { name: 'github_pat', regex: /ghp_[a-zA-Z0-9]{36}/g },
  { name: 'jwt_token', regex: /eyJ[a-zA-Z0-9_-]{20,}\.eyJ[a-zA-Z0-9_-]{20,}\.[a-zA-Z0-9_-]{20,}/g },
  // Slack
  { name: 'slack_token', regex: /xox[bpsa]-[a-zA-Z0-9-]{10,}/g },
  // Stripe
  { name: 'stripe_key', regex: /[sr]k_live_[a-zA-Z0-9]{20,}/g },
  { name: 'stripe_publishable', regex: /pk_live_[a-zA-Z0-9]{20,}/g },
  // SendGrid
  { name: 'sendgrid_key', regex: /SG\.[a-zA-Z0-9_-]{22,}\.[a-zA-Z0-9_-]{22,}/g },
  // Twilio
  { name: 'twilio_sid', regex: /AC[a-f0-9]{32}/g },
  // Database connection strings with embedded passwords
  { name: 'db_connection_string', regex: /(?:postgres|mysql|mongodb|redis):\/\/[^:]+:[^@]+@[^\s"']+/gi },
  // Sales tools (Oliver's stack)
  { name: 'pipedrive_api_key', regex: /(?:pipedrive)[_-]?(?:api)?[_-]?(?:key|token)\s*[=:]\s*["']?[a-f0-9]{40}/gi },
  { name: 'zerobounce_key', regex: /(?:zerobounce|zb)[_-]?(?:api)?[_-]?key\s*[=:]\s*["']?[^\s"']{8,}/gi },
  { name: 'instantly_key', regex: /(?:instantly)[_-]?(?:api)?[_-]?key\s*[=:]\s*["']?[^\s"']{8,}/gi },
  { name: 'apollo_key', regex: /(?:apollo)[_-]?(?:api)?[_-]?key\s*[=:]\s*["']?[^\s"']{8,}/gi },
  { name: 'prospeo_key', regex: /(?:prospeo)[_-]?(?:api)?[_-]?key\s*[=:]\s*["']?[^\s"']{8,}/gi },
  // Generic catch-all (last resort)
  { name: 'generic_secret', regex: /(?:password|api_key|token|secret|apikey|api_secret)\s*[=:]\s*["']?[^\s"']{8,}/gi },
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
    const msg = `SECRET DETECTED: ${findings.length} potential secret(s) in ${filePath}: ${findings.map(f => f.name).join(', ')}. Move secrets to .env or brain config.`;
    process.stderr.write(`[secret-scan] ${msg}\n`);

    // In PreToolUse context, BLOCK the write. In PostToolUse, just warn.
    // PreToolUse passes tool_name in the input; PostToolUse passes tool_output.
    const isPreTool = !toolData.tool_output && !toolData.output;
    if (isPreTool) {
      process.stdout.write(JSON.stringify({
        decision: 'block',
        reason: msg,
      }));
    }
  }
} catch (e) {
  // Silent failure -- hooks must not block
}
