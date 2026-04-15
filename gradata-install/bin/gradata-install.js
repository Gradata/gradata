#!/usr/bin/env node
/**
 * gradata-install — One-command installer for Gradata.
 *
 * Wraps: Python check -> pipx/pip install gradata -> gradata hooks install.
 * Does NOT bundle Python. Spawns the local python/pipx/pip binaries.
 *
 * Usage:
 *   npx gradata-install install [--ide=<name>]
 *   npx gradata-install --help
 *
 * Supported IDEs: claude-code (default), cursor, codex, gemini-cli, continue
 */

"use strict";

const { spawnSync } = require("node:child_process");
const os = require("node:os");
const process = require("node:process");

// ---- Constants ---------------------------------------------------------------

const SUPPORTED_IDES = [
  "claude-code",
  "cursor",
  "codex",
  "gemini-cli",
  "continue",
];
const DEFAULT_IDE = "claude-code";
const MIN_PYTHON = [3, 11];
const PACKAGE = "gradata";

// ---- Small helpers -----------------------------------------------------------

function log(msg) {
  process.stdout.write(msg + "\n");
}

function warn(msg) {
  process.stderr.write(msg + "\n");
}

function fail(msg, code = 1) {
  process.stderr.write("\n[gradata-install] ERROR: " + msg + "\n");
  process.exit(code);
}

function printHelp() {
  log(
    [
      "gradata-install — one-command Gradata installer",
      "",
      "Usage:",
      "  npx gradata-install install [--ide=<name>]",
      "  npx gradata-install --help",
      "",
      "Options:",
      "  --ide=<name>   IDE to wire up (default: claude-code)",
      "                 Supported: " + SUPPORTED_IDES.join(", "),
      "  -h, --help     Show this help and exit",
      "",
      "What it does:",
      "  1. Verifies Python >= " + MIN_PYTHON.join(".") + " is installed",
      "  2. Installs the `gradata` Python package (pipx preferred, pip --user fallback)",
      "  3. Runs `gradata hooks install` to wire up your IDE",
      "",
      "Prerequisites:",
      "  - Node.js >= 18 (you already have this if you ran npx)",
      "  - Python >= " + MIN_PYTHON.join(".") + "  (https://www.python.org/downloads/)",
      "  - pipx recommended  (https://pipx.pypa.io/)",
    ].join("\n")
  );
}

function parsePythonVersion(out) {
  // "Python 3.11.5" -> [3, 11, 5]
  const m = /Python\s+(\d+)\.(\d+)(?:\.(\d+))?/i.exec(out);
  if (!m) return null;
  return [parseInt(m[1], 10), parseInt(m[2], 10), parseInt(m[3] || "0", 10)];
}

function versionGte(v, min) {
  for (let i = 0; i < min.length; i++) {
    const a = v[i] || 0;
    const b = min[i];
    if (a > b) return true;
    if (a < b) return false;
  }
  return true;
}

function tryRun(cmd, args, opts = {}) {
  try {
    return spawnSync(cmd, args, {
      encoding: "utf8",
      shell: false,
      ...opts,
    });
  } catch (err) {
    return { error: err, status: -1, stdout: "", stderr: String(err) };
  }
}

function runInherit(cmd, args) {
  log("\n$ " + cmd + " " + args.join(" "));
  const r = spawnSync(cmd, args, { stdio: "inherit", shell: false });
  return r.status === null ? 1 : r.status;
}

// ---- Environment checks ------------------------------------------------------

function findPython() {
  // Returns { cmd, version } or null
  const candidates = process.platform === "win32"
    ? ["py", "python", "python3"]
    : ["python3", "python"];

  for (const cmd of candidates) {
    const args = cmd === "py" ? ["-3", "--version"] : ["--version"];
    const res = tryRun(cmd, args);
    if (res.status !== 0) continue;
    const out = (res.stdout || "") + (res.stderr || "");
    const v = parsePythonVersion(out);
    if (!v) continue;
    if (!versionGte(v, MIN_PYTHON)) continue;
    return {
      cmd,
      invocation: cmd === "py" ? [cmd, "-3"] : [cmd],
      version: v,
    };
  }
  return null;
}

function hasPipx() {
  const res = tryRun("pipx", ["--version"]);
  return res.status === 0;
}

function pythonInstallInstructions() {
  const platform = os.platform();
  const lines = [
    "Python >= " + MIN_PYTHON.join(".") + " is required but was not found.",
    "",
    "Install instructions:",
  ];
  if (platform === "darwin") {
    lines.push(
      "  macOS:     brew install python@3.12",
      "             or download from https://www.python.org/downloads/"
    );
  } else if (platform === "win32") {
    lines.push(
      "  Windows:   winget install Python.Python.3.12",
      "             or download from https://www.python.org/downloads/"
    );
  } else {
    lines.push(
      "  Debian/Ubuntu: sudo apt-get install python3 python3-pip python3-venv",
      "  Fedora/RHEL:   sudo dnf install python3 python3-pip",
      "  Arch:          sudo pacman -S python python-pip",
      "  Other:         https://www.python.org/downloads/"
    );
  }
  lines.push(
    "",
    "After installing, also install pipx (recommended):",
    "  python3 -m pip install --user pipx && python3 -m pipx ensurepath"
  );
  return lines.join("\n");
}

// ---- Argument parsing --------------------------------------------------------

function parseArgs(argv) {
  const out = { command: null, ide: DEFAULT_IDE, help: false };
  const args = argv.slice(2);
  for (let i = 0; i < args.length; i++) {
    const a = args[i];
    if (a === "-h" || a === "--help") {
      out.help = true;
    } else if (a === "install" && out.command === null) {
      out.command = "install";
    } else if (a.startsWith("--ide=")) {
      out.ide = a.slice("--ide=".length);
    } else if (a === "--ide") {
      out.ide = args[i + 1];
      i++;
    } else if (a.startsWith("-")) {
      warn("Unknown option: " + a);
      out.help = true;
    } else if (!out.command) {
      out.command = a;
    }
  }
  return out;
}

// ---- Main flow ---------------------------------------------------------------

function installFlow(ide) {
  if (!SUPPORTED_IDES.includes(ide)) {
    fail(
      "Unsupported IDE: " +
        ide +
        "\nSupported: " +
        SUPPORTED_IDES.join(", ")
    );
  }

  log("[gradata-install] Target IDE: " + ide);

  // 1. Python check
  const py = findPython();
  if (!py) {
    fail(pythonInstallInstructions());
  }
  log(
    "[gradata-install] Found Python " +
      py.version.join(".") +
      " via `" +
      py.invocation.join(" ") +
      "`"
  );

  // 2. Install gradata package
  let installCmd, installArgs;
  if (hasPipx()) {
    log("[gradata-install] pipx detected — using pipx.");
    installCmd = "pipx";
    installArgs = ["install", PACKAGE];
  } else {
    log(
      "[gradata-install] pipx not found — falling back to `pip install --user`."
    );
    log("[gradata-install] (Tip: install pipx for cleaner isolation.)");
    installCmd = py.invocation[0];
    installArgs = py.invocation
      .slice(1)
      .concat(["-m", "pip", "install", "--user", "--upgrade", PACKAGE]);
  }

  let status = runInherit(installCmd, installArgs);
  if (status !== 0) {
    // If pipx install failed because already installed, retry with upgrade.
    if (installCmd === "pipx") {
      log(
        "[gradata-install] pipx install failed — trying `pipx upgrade " +
          PACKAGE +
          "`."
      );
      status = runInherit("pipx", ["upgrade", PACKAGE]);
    }
    if (status !== 0) {
      fail(
        "Failed to install `" +
          PACKAGE +
          "` (exit code " +
          status +
          ").\n" +
          "Check the output above and try running the command manually."
      );
    }
  }

  // 3. Run hook installer
  // The gradata CLI exposes `gradata hooks install` (see src/gradata/cli.py).
  // We pass the IDE via --ide for forward-compat; current CLI ignores unknown
  // flags or targets claude-code by default. We only pass --ide when non-default.
  const hookArgs = ["hooks", "install"];
  if (ide !== DEFAULT_IDE) {
    hookArgs.push("--ide", ide);
  }

  status = runInherit("gradata", hookArgs);
  if (status !== 0) {
    // Fall back to `python -m gradata` if `gradata` isn't on PATH yet
    // (common with pip --user on fresh installs).
    log(
      "[gradata-install] `gradata` not on PATH — retrying via `python -m gradata`."
    );
    status = runInherit(
      py.invocation[0],
      py.invocation.slice(1).concat(["-m", "gradata"]).concat(hookArgs)
    );
  }
  if (status !== 0) {
    fail(
      "Hook installation failed (exit code " +
        status +
        ").\n" +
        "You can retry manually with: gradata hooks install"
    );
  }

  // 4. Success message
  log("");
  log("[gradata-install] Gradata installed and wired up for " + ide + ".");
  log("");
  log("Next steps:");
  if (ide === "claude-code") {
    log("  1. Restart Claude Code so it picks up the hook.");
  } else {
    log("  1. Restart " + ide + " so it picks up the hook.");
  }
  log("  2. Verify with:  gradata status");
  log("  3. Docs:          https://github.com/Gradata/gradata");
  log("");
}

// ---- Entrypoint --------------------------------------------------------------

function main() {
  // Clean Ctrl+C handling — suppress node's default stacktrace.
  process.on("SIGINT", () => {
    warn("\n[gradata-install] Cancelled by user.");
    process.exit(130);
  });

  const args = parseArgs(process.argv);

  if (args.help || !args.command) {
    printHelp();
    process.exit(args.help ? 0 : 1);
  }

  if (args.command !== "install") {
    warn("Unknown command: " + args.command);
    printHelp();
    process.exit(1);
  }

  installFlow(args.ide);
}

main();
