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
  const cmd = [
    '"' + PYTHON + '"',
    '"' + EMIT_SCRIPT + '"',
    "--output-type", outputType,
    "--file", shellEscape(fileName),
  ].join(" ");
  try {
    execSync(cmd, { timeout: 5000, stdio: "ignore" });
  } catch {
    // Silent failure -- never break the tool chain
  }
}

main();
