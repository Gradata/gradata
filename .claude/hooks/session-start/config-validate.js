#!/usr/bin/env node
/**
 * config-validate.js — SessionStart hook
 * =======================================
 * Validates settings.json and agent-manifests.json on session start.
 * Checks: valid JSON, hook file existence, no duplicate hooks.
 * Outputs warnings to stderr. Never blocks (always exits 0).
 */

const fs = require("fs");
const path = require("path");

const cfg = require('../config.js');
const WORKING_DIR = cfg.WORKING_DIR;
const SETTINGS_PATH = path.join(WORKING_DIR, ".claude/settings.json");
const MANIFEST_PATH = path.join(WORKING_DIR, ".claude/agent-manifests.json");

const warnings = [];

function warn(msg) {
  warnings.push(msg);
}

function validateJSON(filePath, label) {
  if (!fs.existsSync(filePath)) {
    warn(`${label}: file not found at ${filePath}`);
    return null;
  }
  try {
    const raw = fs.readFileSync(filePath, "utf-8");
    return JSON.parse(raw);
  } catch (e) {
    warn(`${label}: invalid JSON — ${e.message}`);
    return null;
  }
}

function extractHookCommands(settings) {
  const commands = [];
  const hooks = settings.hooks || {};

  for (const [event, entries] of Object.entries(hooks)) {
    if (!Array.isArray(entries)) continue;
    for (const entry of entries) {
      const hookList = entry.hooks || [];
      for (const hook of hookList) {
        if (hook.type === "command" && hook.command) {
          commands.push({ event, command: hook.command });
        }
      }
    }
  }
  return commands;
}

function resolveCommandFile(command) {
  // Extract the file path from the command string
  // Handles: node path/file.js, python "path/file.py", python path/file.py
  const patterns = [
    /^(?:node|python)\s+"([^"]+)"/,
    /^(?:node|python)\s+(\S+)/,
  ];

  for (const pattern of patterns) {
    const match = command.match(pattern);
    if (match) return match[1];
  }
  return null;
}

function checkHookFilesExist(hookCommands) {
  for (const { event, command } of hookCommands) {
    const filePath = resolveCommandFile(command);
    if (!filePath) continue;

    // Resolve relative paths against working dir
    const resolved = path.isAbsolute(filePath)
      ? filePath
      : path.join(WORKING_DIR, filePath);

    if (!fs.existsSync(resolved)) {
      warn(
        `Hook file missing: ${filePath} (event: ${event}, command: ${command})`
      );
    }
  }
}

function checkDuplicateHooks(hookCommands) {
  const seen = new Map();
  for (const { event, command } of hookCommands) {
    const key = `${event}::${command}`;
    if (seen.has(key)) {
      warn(`Duplicate hook: "${command}" registered twice in ${event}`);
    }
    seen.set(key, true);
  }
}

function validateManifestStructure(manifest) {
  // Check required top-level keys
  if (!manifest.agents || typeof manifest.agents !== "object") {
    warn("agent-manifests.json: missing or invalid 'agents' object");
    return;
  }

  // Validate each agent has required fields
  const requiredFields = [
    "description",
    "trust_level",
    "tools_allowed",
    "write_paths",
  ];
  for (const [name, agent] of Object.entries(manifest.agents)) {
    for (const field of requiredFields) {
      if (!(field in agent)) {
        warn(`agent-manifests.json: agent '${name}' missing field '${field}'`);
      }
    }
  }

  // Validate orchestration
  if (!manifest.orchestration) {
    warn("agent-manifests.json: missing 'orchestration' config");
  }

  // Validate guardrails
  if (!manifest.guardrails) {
    warn("agent-manifests.json: missing 'guardrails' config");
  }
}

// ── Main ──────────────────────────────────────────────────────────

function main() {
  // 1. Validate settings.json
  const settings = validateJSON(SETTINGS_PATH, "settings.json");

  if (settings) {
    // 2. Check hook files exist
    const hookCommands = extractHookCommands(settings);
    checkHookFilesExist(hookCommands);

    // 3. Check for duplicate hooks
    checkDuplicateHooks(hookCommands);
  }

  // 4. Validate agent-manifests.json
  const manifest = validateJSON(MANIFEST_PATH, "agent-manifests.json");
  if (manifest) {
    validateManifestStructure(manifest);
  }

  // Output warnings to stderr (never block)
  if (warnings.length > 0) {
    process.stderr.write(
      `[config-validate] ${warnings.length} warning(s):\n`
    );
    for (const w of warnings) {
      process.stderr.write(`  - ${w}\n`);
    }
  }

  // Always exit 0 — warnings only, never block
  process.exit(0);
}

main();
