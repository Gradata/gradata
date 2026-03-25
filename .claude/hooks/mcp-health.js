#!/usr/bin/env node
/**
 * mcp-health.js — PreToolUse hook (matcher: mcp__*)
 * Checks persistent health cache before MCP tool calls.
 * Exponential backoff on previously failed MCP servers.
 * Profile: standard, strict
 */
const fs = require('fs');
const path = require('path');

const PROFILE = process.env.AIOS_HOOK_PROFILE || 'standard';
if (PROFILE === 'minimal') process.exit(0);

const cfg = require('./config.js');
const BRAIN_PATH = cfg.BRAIN_DIR;
const HEALTH_CACHE = path.join(BRAIN_PATH, '.mcp-health.json');
const MAX_BACKOFF_MS = 600000; // 10 minutes

try {
  let input = '';
  if (!process.stdin.isTTY) {
    input = fs.readFileSync(0, 'utf8');
  }

  let toolData = {};
  try { toolData = JSON.parse(input); } catch (e) { /* no data */ }

  const toolName = toolData.tool_name || '';
  // Extract MCP server prefix (e.g., "mcp__claude_ai_Gmail" from "mcp__claude_ai_Gmail__gmail_search_messages")
  const parts = toolName.split('__');
  const serverPrefix = parts.length >= 3 ? parts.slice(0, 3).join('__') : toolName;

  // Load health cache
  let cache = {};
  if (fs.existsSync(HEALTH_CACHE)) {
    try { cache = JSON.parse(fs.readFileSync(HEALTH_CACHE, 'utf8')); } catch (e) { cache = {}; }
  }

  const serverHealth = cache[serverPrefix] || { status: 'healthy', failures: 0, last_failure: null, backoff_ms: 0 };

  if (serverHealth.status === 'unhealthy' && serverHealth.last_failure) {
    const elapsed = Date.now() - new Date(serverHealth.last_failure).getTime();
    if (elapsed < serverHealth.backoff_ms) {
      const waitSec = Math.round((serverHealth.backoff_ms - elapsed) / 1000);
      process.stderr.write(`[mcp-health] ${serverPrefix} is unhealthy. Backoff: ${waitSec}s remaining. ${serverHealth.failures} consecutive failures.\n`);
    } else {
      // Backoff expired, allow retry
      serverHealth.status = 'retrying';
      cache[serverPrefix] = serverHealth;
      fs.writeFileSync(HEALTH_CACHE, JSON.stringify(cache, null, 2));
    }
  }

} catch (e) {
  // Silent failure — never block MCP calls
}
