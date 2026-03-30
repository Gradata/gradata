#!/usr/bin/env node
/**
 * tool-failure-emit.js — PostToolUse hook (matcher: mcp__*)
 * Emits TOOL_FAILURE events when MCP tool calls return errors.
 *
 * Detects: error fields, HTTP errors, timeouts, "Error:" prefixes,
 * exception traces, and known failure patterns.
 *
 * Updates mcp-health cache with failure/recovery tracking.
 * Silent on failure — never breaks the tool chain.
 */

const { execFileSync } = require("child_process");
const fs = require("fs");
const path = require("path");

const cfg = require('../config.js');
const PYTHON = cfg.PYTHON;
const BRAIN_PATH = cfg.BRAIN_DIR;
const HEALTH_CACHE = path.join(BRAIN_PATH, ".mcp-health.json");
const MAX_BACKOFF_MS = 600000; // 10 minutes

const ERROR_INDICATORS = [
  /\berror\b/i,
  /\bfailed\b/i,
  /\btimeout\b/i,
  /\bHTTP\s+[45]\d{2}\b/,
  /\bException\b/,
  /\bTraceback\b/,
  /\bECONNREFUSED\b/,
  /\bECONNRESET\b/,
  /\bENOTFOUND\b/,
  /\bunauthorized\b/i,
  /\bforbidden\b/i,
  /\brate.?limit/i,
  /\bserver\s+error\b/i,
  /\binternal\s+server\b/i,
  /\bservice\s+unavailable\b/i,
  /\bgateway\s+timeout\b/i,
  /\bbad\s+gateway\b/i,
];

// False positives — error-like words in normal output
const FALSE_POSITIVE_PATTERNS = [
  /error.?handling/i,
  /error.?message/i,
  /error.?code/i,
  /no\s+errors?\s+found/i,
  /without\s+error/i,
  /error.?free/i,
];

function readStdin() {
  try {
    return JSON.parse(fs.readFileSync(0, "utf8"));
  } catch {
    return null;
  }
}

function extractErrorSummary(output) {
  if (!output || typeof output !== "string") return null;

  // Check false positives first
  for (const fp of FALSE_POSITIVE_PATTERNS) {
    if (fp.test(output)) return null;
  }

  // Check for error indicators
  for (const pattern of ERROR_INDICATORS) {
    const match = output.match(pattern);
    if (match) {
      // Extract ~120 chars around the match for context
      const idx = match.index || 0;
      const start = Math.max(0, idx - 40);
      const end = Math.min(output.length, idx + 80);
      return output.substring(start, end).replace(/[\r\n]+/g, " ").trim();
    }
  }

  return null;
}

function extractServerPrefix(toolName) {
  if (!toolName) return "unknown";
  const parts = toolName.split("__");
  return parts.length >= 3 ? parts.slice(0, 3).join("__") : toolName;
}

function updateHealthCache(serverPrefix, isFailure) {
  let cache = {};
  try {
    if (fs.existsSync(HEALTH_CACHE)) {
      cache = JSON.parse(fs.readFileSync(HEALTH_CACHE, "utf8"));
    }
  } catch {
    cache = {};
  }

  const entry = cache[serverPrefix] || { status: "healthy", failures: 0, last_failure: null, backoff_ms: 0 };

  if (isFailure) {
    entry.failures += 1;
    entry.last_failure = new Date().toISOString();
    entry.status = "unhealthy";
    entry.backoff_ms = Math.min(MAX_BACKOFF_MS, 1000 * Math.pow(2, entry.failures));
  } else {
    // Recovery — reset on success
    if (entry.status === "retrying" || entry.status === "unhealthy") {
      entry.status = "healthy";
      entry.failures = 0;
      entry.backoff_ms = 0;
    }
  }

  cache[serverPrefix] = entry;
  try {
    fs.writeFileSync(HEALTH_CACHE, JSON.stringify(cache, null, 2));
  } catch {
    // Non-blocking
  }

  return entry;
}

function main() {
  const data = readStdin();
  if (!data || !data.tool_name) return;

  const toolName = data.tool_name || "";
  // Only process MCP tool calls
  if (!toolName.startsWith("mcp__")) return;

  // Check tool_output for error indicators
  const toolOutput = data.tool_output || "";
  const outputStr = typeof toolOutput === "string" ? toolOutput : JSON.stringify(toolOutput);

  // Also check if there's an explicit error field
  const hasErrorField = data.tool_output && typeof data.tool_output === "object" && (
    data.tool_output.error || data.tool_output.isError === true
  );

  const errorSummary = hasErrorField
    ? String(data.tool_output.error || "Tool returned isError=true")
    : extractErrorSummary(outputStr);

  const serverPrefix = extractServerPrefix(toolName);

  if (errorSummary) {
    // Update health cache
    const health = updateHealthCache(serverPrefix, true);

    // Emit TOOL_FAILURE event via events.py CLI
    const eventData = {
      tool_name: toolName,
      server: serverPrefix,
      error_summary: String(errorSummary).substring(0, 300),
      was_retried: health.failures > 1,
      consecutive_failures: health.failures,
    };
    const tags = ["tool:" + toolName, "server:" + serverPrefix];

    // Use events.py CLI interface — execFileSync avoids shell escaping issues on Windows
    try {
      execFileSync(PYTHON, [
        path.join(cfg.SCRIPTS, "events.py"),
        "emit", "TOOL_FAILURE", "hook:tool_failure_emit",
        JSON.stringify(eventData),
        JSON.stringify(tags),
      ], {
        timeout: 5000,
        stdio: "ignore",
        cwd: cfg.SCRIPTS,
      });
    } catch {
      // Silent — never break the tool chain
    }
  } else {
    // Success — update health cache for recovery tracking
    updateHealthCache(serverPrefix, false);
  }
}

main();
