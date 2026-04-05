#!/usr/bin/env node
/**
 * create-gradata — Scaffold a Gradata brain in 30 seconds.
 *
 * Usage:
 *   npx create-gradata ./my-brain
 *   npx create-gradata ./my-brain --domain Sales --name SalesBrain
 */

const { execSync, spawnSync } = require('child_process');
const fs = require('fs');
const path = require('path');
const readline = require('readline');

const args = process.argv.slice(2);
const flags = {};
let brainPath = null;

// Parse args
for (let i = 0; i < args.length; i++) {
  if (args[i].startsWith('--')) {
    const key = args[i].slice(2);
    flags[key] = args[i + 1] || '';
    i++;
  } else if (!brainPath) {
    brainPath = args[i];
  }
}

if (!brainPath) {
  console.log(`
  create-gradata — Scaffold a Gradata brain in 30 seconds.

  Usage:
    npx create-gradata ./my-brain
    npx create-gradata ./my-brain --domain Sales --name SalesBrain

  Options:
    --domain <domain>    Brain domain (default: General)
    --name <name>        Brain name (default: directory name)
    --company <company>  Company name (creates company.md)
    --no-interactive     Skip interactive prompts
  `);
  process.exit(0);
}

const absPath = path.resolve(brainPath);

// Check if Python + gradata are available
function checkPython() {
  for (const cmd of ['python3', 'python']) {
    try {
      const result = spawnSync(cmd, ['-c', 'import gradata; print(gradata.__version__)'], {
        encoding: 'utf8', timeout: 10000, stdio: ['pipe', 'pipe', 'pipe'],
      });
      if (result.status === 0) return { cmd, version: result.stdout.trim() };
    } catch (_) {}
  }
  return null;
}

async function main() {
  console.log('\n  create-gradata\n');

  // Step 1: Check Python
  let py = checkPython();
  if (!py) {
    console.log('  Gradata SDK not found. Installing...\n');
    try {
      execSync('pip install gradata', { stdio: 'inherit' });
      py = checkPython();
    } catch (_) {
      try {
        execSync('pip3 install gradata', { stdio: 'inherit' });
        py = checkPython();
      } catch (__) {}
    }
    if (!py) {
      console.error('  Error: Could not install gradata. Make sure Python 3.11+ and pip are available.');
      console.error('  Install manually: pip install gradata');
      process.exit(1);
    }
  }
  console.log(`  Found gradata v${py.version} (${py.cmd})\n`);

  // Step 2: Build the gradata init command
  const initArgs = ['-m', 'gradata.cli', 'init', absPath];
  if (flags.domain) initArgs.push('--domain', flags.domain);
  if (flags.name) initArgs.push('--name', flags.name);
  if (flags.company) initArgs.push('--company', flags.company);
  if (flags['no-interactive']) initArgs.push('--no-interactive');

  // Step 3: Run gradata init
  const result = spawnSync(py.cmd, initArgs, { stdio: 'inherit', encoding: 'utf8' });

  if (result.status !== 0) {
    console.error('\n  Brain creation failed. Check the output above.');
    process.exit(1);
  }

  // Step 4: Show next steps
  console.log(`
  Brain created at ${absPath}

  Next steps:

    1. Add to Claude Code settings.json:
       {
         "mcpServers": {
           "gradata": {
             "command": "${py.cmd}",
             "args": ["-m", "gradata.mcp_server"]
           }
         }
       }

    2. Start correcting. The brain learns from every edit.

    3. Check progress:
       gradata stats
       gradata manifest --json
  `);
}

main().catch(err => {
  console.error(err);
  process.exit(1);
});
