#!/usr/bin/env node
/**
 * PostToolUse hook: emit GATE_RESULT events when CARL gates are executed.
 *
 * Detects when Read is used on domain/gates/* files (gate loading) and emits
 * a GATE_RESULT event via events.py. This bridges the gap between CARL gate
 * enforcement (behavioral) and the event system (queryable).
 *
 * Input: JSON from stdin with { tool_name, tool_input, tool_output, session_id }
 * Silent on failure -- never break the tool chain.
 */

const fs = require("fs");

const cfg = require('./config.js');
const { execSafe } = cfg;
const PYTHON = cfg.PYTHON;

function readStdin() {
  try {
    return JSON.parse(fs.readFileSync(0, "utf8"));
  } catch {
    return null;
  }
}

/**
 * Extract gate name from a file path.
 * Returns null if the path is not a gate file.
 */
function extractGateName(filePath) {
  if (!filePath) return null;

  // Normalize to forward slashes
  const normalized = filePath.replace(/\\/g, "/");

  // Match domain/gates/<gate-name>
  const gateMatch = normalized.match(/domain\/gates\/([^/]+)/);
  if (gateMatch) {
    let name = gateMatch[1];
    name = name.replace(/\.(md|txt|yaml|json)$/i, "");
    name = name.replace(/[_\s]/g, "-").toLowerCase();
    return name;
  }

  // Match .carl paths containing "gate"
  const carlMatch = normalized.match(/\.carl\/.*gate/i);
  if (carlMatch) {
    const parts = normalized.split("/");
    const last = parts[parts.length - 1] || "unknown";
    return last.replace(/\.(md|txt|yaml|json)$/i, "").replace(/[_\s]/g, "-").toLowerCase();
  }

  return null;
}

function main() {
  const data = readStdin();
  if (!data || !data.tool_name) return;

  // Only fire on Read tool (gate files are loaded via Read)
  if (data.tool_name !== "Read") return;

  const filePath = (data.tool_input && (data.tool_input.file_path || data.tool_input.path)) || "";
  const gateName = extractGateName(filePath);
  if (!gateName) return;

  const safePath = filePath.replace(/\\/g, "/").replace(/'/g, "");

  // Use a Python one-liner to call emit_gate_result
  const pyCode = [
    "import sys",
    `sys.path.insert(0, '${cfg.SCRIPTS}')`,
    "from events import emit_gate_result",
    "emit_gate_result('" + gateName + "', 'PASS', ['" + safePath + "'], 'Gate loaded via Read')",
  ].join("; ");

  try {
    execSafe('"' + PYTHON + '" -c "' + pyCode + '"', { timeout: 5000, stdio: "ignore" });
  } catch {
    // Silent failure -- never break the tool chain
  }
}

main();
