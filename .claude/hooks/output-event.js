#!/usr/bin/env node
/**
 * output-event.js -- PostToolUse hook (matcher: Write|Edit)
 * Emits OUTPUT events when Claude produces prospect-facing deliverables.
 * Fixes GAP-1: checks 09 and 10 in wrap_up_validator.py need OUTPUT events.
 * Silent on failure -- never breaks the tool chain.
 */

const { execSync } = require("child_process");
const path = require("path");

const PYTHON = "C:/Users/olive/AppData/Local/Programs/Python/Python312/python.exe";
const EMIT_SCRIPT = "C:/Users/olive/SpritesWork/brain/scripts/emit_output.py";

const PROSPECT_PATHS = [
  "brain/prospects/",
  "domain/pipeline/",
  "docs/Demo Prep/",
  "brain/demos/",
  "brain/emails/",
];

const OUTPUT_PATTERNS = {
  email: [/email/i, /draft/i, /outreach/i, /follow.?up/i, /sequence/i],
  cheat_sheet: [/cheat/i, /prep/i, /battlecard/i, /objection/i, /talk.?track/i],
  research: [/research/i, /enrich/i, /intel/i, /profile/i, /discovery/i, /icp/i, /tech.?stack/i],
};

function readStdin() {
  try {
    return JSON.parse(require("fs").readFileSync(0, "utf8"));
  } catch {
    return null;
  }
}

function isProspectFacing(filePath) {
  if (!filePath) return false;
  const normalized = filePath.replace(/\\/g, "/");
  return PROSPECT_PATHS.some((p) => normalized.includes(p));
}

function classifyOutput(filePath) {
  if (!filePath) return null;
  const lower = filePath.toLowerCase();
  const fileName = path.basename(lower);
  for (const [outputType, patterns] of Object.entries(OUTPUT_PATTERNS)) {
    for (const regex of patterns) {
      if (regex.test(fileName) || regex.test(lower)) {
        return outputType;
      }
    }
  }
  if (lower.includes("email")) return "email";
  if (lower.includes("demo") || lower.includes("prep")) return "cheat_sheet";
  if (lower.includes("prospect")) return "research";
  return "research";
}

function shellEscape(str) {
  if (!str) return '""';
  return '"' + str.replace(/"/g, '\\"').replace(/\n/g, " ").substring(0, 200) + '"';
}

function extractSelfScore(text) {
  if (!text) return null;
  // Check first and last 2500 chars (scores appear at boundaries)
  const sample = text.length > 5000
    ? text.substring(0, 2500) + text.substring(text.length - 2500)
    : text;
  // Patterns: "self-score: 7/10", "Score: 8.5/10", "[7/10]", "quality: 8/10"
  const patterns = [
    /self[_-]?score\s*[:=]\s*(\d+(?:\.\d+)?)\s*(?:\/\s*10)?/i,
    /\bscore\s*[:=]\s*(\d+(?:\.\d+)?)\s*\/\s*10/i,
    /\[(\d+(?:\.\d+)?)\s*\/\s*10\]/,
    /quality\s*[:=]\s*(\d+(?:\.\d+)?)\s*\/\s*10/i,
  ];
  for (const re of patterns) {
    const m = sample.match(re);
    if (m) {
      const val = parseFloat(m[1]);
      if (val >= 0 && val <= 10) return val;
    }
  }
  return null;
}

function main() {
  const data = readStdin();
  if (!data) return;
  const toolName = data.tool_name || "";
  if (toolName !== "Write" && toolName !== "Edit") return;
  const toolInput = data.tool_input || {};
  const filePath = toolInput.file_path || toolInput.path || "";
  if (!isProspectFacing(filePath)) return;
  const outputType = classifyOutput(filePath);
  if (!outputType) return;
  const fileName = path.basename(filePath);

  // Extract self-score from written content
  const content = toolInput.content || toolInput.new_string || "";
  const resultText = (data.tool_result && typeof data.tool_result === "string") ? data.tool_result : "";
  const selfScore = extractSelfScore(content) || extractSelfScore(resultText);

  const cmdParts = [
    '"' + PYTHON + '"',
    '"' + EMIT_SCRIPT + '"',
    "--output-type", outputType,
    "--file", shellEscape(fileName),
  ];
  if (selfScore !== null) {
    cmdParts.push("--self-score", String(selfScore));
  }
  const cmd = cmdParts.join(" ");
  try {
    execSync(cmd, { timeout: 5000, stdio: "ignore" });
  } catch {
    // Silent failure -- never break the tool chain
  }

  // Track this file as "agent-written" so delta-auto-tag can detect Oliver's edits
  // and auto-emit HUMAN_JUDGMENT events for calibration
  try {
    const os = require("os");
    const manifestPath = path.join(os.tmpdir(), "agent-written-files.json");
    let manifest = {};
    if (require("fs").existsSync(manifestPath)) {
      try { manifest = JSON.parse(require("fs").readFileSync(manifestPath, "utf8")); } catch { manifest = {}; }
    }
    const normalizedPath = filePath.replace(/\\/g, "/");
    manifest[normalizedPath] = {
      agent: "unknown", // Will be enriched by spawn.py when available
      output_type: outputType,
      written_at: new Date().toISOString(),
      self_score: selfScore,
    };
    // Keep only last 50 entries to prevent bloat
    const keys = Object.keys(manifest);
    if (keys.length > 50) {
      for (const k of keys.slice(0, keys.length - 50)) delete manifest[k];
    }
    require("fs").writeFileSync(manifestPath, JSON.stringify(manifest, null, 2));
  } catch {
    // Silent -- manifest is best-effort
  }
}

main();
