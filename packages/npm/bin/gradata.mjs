#!/usr/bin/env node
/**
 * @gradata/cli — Node wrapper.
 *
 * Two modes:
 *   1. `gradata correct --draft X --final Y` — emits a correction event
 *      directly to a local daemon over HTTP (no Python required).
 *   2. Any other subcommand — shells out to `python -m gradata <args>`.
 *      Surfaces a helpful message if Python/SDK is not installed.
 */

import { spawnSync } from "node:child_process";
import process from "node:process";

// Dynamic import so `gradata --version` works even before `npm run build`.
async function loadClient() {
  try {
    const mod = await import("../dist/client.js");
    return mod.GradataClient ?? mod.default;
  } catch (err) {
    return null;
  }
}

const PKG_VERSION = "0.1.0";

function printHelp() {
  process.stdout.write(
    [
      "gradata — procedural memory for AI agents (JS wrapper)",
      "",
      "Usage:",
      "  gradata correct --draft <text> --final <text> [--type <email|code|...>]",
      "  gradata <any-python-subcommand> [args...]   # forwards to python -m gradata",
      "  gradata --version",
      "  gradata --help",
      "",
      "Environment:",
      "  GRADATA_DAEMON_URL  Daemon endpoint (default http://127.0.0.1:8765)",
      "  GRADATA_PYTHON      Python binary (default: python)",
      "",
    ].join("\n"),
  );
}

function parseFlags(argv) {
  const out = {};
  for (let i = 0; i < argv.length; i += 1) {
    const a = argv[i];
    if (a.startsWith("--")) {
      const key = a.slice(2);
      const next = argv[i + 1];
      if (next === undefined || next.startsWith("--")) {
        out[key] = true;
      } else {
        out[key] = next;
        i += 1;
      }
    }
  }
  return out;
}

async function runCorrect(argv) {
  const flags = parseFlags(argv);
  const draft = flags.draft;
  const final = flags.final;
  if (typeof draft !== "string" || typeof final !== "string") {
    process.stderr.write(
      "error: `gradata correct` requires --draft <text> and --final <text>\n",
    );
    process.exit(2);
  }
  const Client = await loadClient();
  if (!Client) {
    process.stderr.write(
      [
        "error: @gradata/cli is not built. Run `npm run build` in packages/npm,",
        "or install the published package via `npm i @gradata/cli`.",
        "",
      ].join("\n"),
    );
    process.exit(1);
  }
  const endpoint =
    process.env.GRADATA_DAEMON_URL ?? "http://127.0.0.1:8765";
  const client = new Client({ endpoint });
  try {
    const resp = await client.correct({
      draft,
      final,
      outputType: typeof flags.type === "string" ? flags.type : undefined,
      taskType: typeof flags.task === "string" ? flags.task : undefined,
    });
    process.stdout.write(JSON.stringify(resp) + "\n");
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    process.stderr.write(
      [
        `error: could not reach Gradata daemon at ${endpoint}`,
        `       ${msg}`,
        "       Start the daemon: `python -m gradata.daemon --brain-dir ./brain`",
        "       Or run via Docker: `docker run -p 8765:8765 gradata/daemon`",
        "",
      ].join("\n"),
    );
    process.exit(1);
  }
}

function shellToPython(argv) {
  const py = process.env.GRADATA_PYTHON ?? "python";
  const result = spawnSync(py, ["-m", "gradata", ...argv], {
    stdio: "inherit",
  });
  if (result.error) {
    const err = result.error;
    if (err.code === "ENOENT") {
      process.stderr.write(
        [
          "error: Python not found. Install Python 3.11+ and `pip install gradata`,",
          "       or set GRADATA_PYTHON to a python binary.",
          "",
        ].join("\n"),
      );
      process.exit(1);
    }
    process.stderr.write(`error: ${err.message}\n`);
    process.exit(1);
  }
  process.exit(result.status ?? 0);
}

async function main() {
  const argv = process.argv.slice(2);
  if (argv.length === 0 || argv[0] === "--help" || argv[0] === "-h") {
    printHelp();
    process.exit(0);
  }
  if (argv[0] === "--version" || argv[0] === "-V") {
    process.stdout.write(PKG_VERSION + "\n");
    process.exit(0);
  }
  if (argv[0] === "correct") {
    await runCorrect(argv.slice(1));
    return;
  }
  shellToPython(argv);
}

main().catch((err) => {
  process.stderr.write(
    `fatal: ${err instanceof Error ? err.message : String(err)}\n`,
  );
  process.exit(1);
});
