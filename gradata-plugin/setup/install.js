#!/usr/bin/env node
const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');
const readline = require('readline');

const GRADATA_HOME = path.join(process.env.HOME || process.env.USERPROFILE || '~', '.gradata');
const PYTHON_CANDIDATES = process.platform === 'win32'
  ? ['python3', 'python', 'py -3']
  : ['python3', 'python', '/usr/local/bin/python3', '/usr/bin/python3'];

function tryPython(cmd) {
  try {
    const version = execSync(`${cmd} --version 2>&1`, { encoding: 'utf8', windowsHide: true, timeout: 5000 }).trim();
    const match = version.match(/Python (\d+)\.(\d+)/);
    if (!match) return null;
    const [, major, minor] = match.map(Number);
    if (major < 3 || (major === 3 && minor < 10)) return null;
    const absPath = execSync(`${cmd} -c "import sys; print(sys.executable)"`, {
      encoding: 'utf8', windowsHide: true, timeout: 5000,
    }).trim();
    return { cmd, absPath, version };
  } catch { return null; }
}

function hasGradata(pythonPath) {
  try {
    execSync(`"${pythonPath}" -c "import gradata"`, { encoding: 'utf8', windowsHide: true, timeout: 10000 });
    return true;
  } catch { return false; }
}

function writeConfig(pythonPath) {
  fs.mkdirSync(GRADATA_HOME, { recursive: true });
  const configPath = path.join(GRADATA_HOME, 'config.toml');
  fs.writeFileSync(configPath, `# Gradata configuration\npython_path = "${pythonPath.replace(/\\/g, '\\\\')}"\n`, 'utf8');
}

async function ask(question) {
  const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
  return new Promise(resolve => rl.question(question, ans => { rl.close(); resolve(ans); }));
}

async function main() {
  console.log('Gradata Plugin Setup\n');
  let python = null;
  for (const cmd of PYTHON_CANDIDATES) {
    python = tryPython(cmd);
    if (python) break;
  }
  if (!python) {
    console.log('Python 3.10+ not found.\n');
    if (process.platform === 'darwin') console.log('Install: brew install python3');
    else if (process.platform === 'win32') console.log('Install: Download from python.org/downloads (check "Add to PATH")');
    else console.log('Install: sudo apt install python3 python3-pip');
    process.exit(1);
  }
  console.log(`Python found: ${python.absPath} (${python.version})`);
  if (!hasGradata(python.absPath)) {
    console.log('Gradata SDK not found.\n');
    const answer = await ask(`Install? Run: "${python.absPath}" -m pip install gradata [Enter/n] `);
    if (answer.toLowerCase() === 'n') {
      console.log('Skipped. Run manually: pip install gradata');
    } else {
      try {
        console.log('Installing gradata...');
        execSync(`"${python.absPath}" -m pip install gradata`, { stdio: 'inherit', windowsHide: true, timeout: 120000 });
        console.log('Installed successfully.');
      } catch {
        console.log(`Failed. Try: "${python.absPath}" -m pip install gradata`);
        process.exit(1);
      }
    }
  } else {
    const ver = execSync(`"${python.absPath}" -c "import gradata; print(gradata.__version__)"`, {
      encoding: 'utf8', windowsHide: true,
    }).trim();
    console.log(`Gradata SDK: v${ver}`);
  }
  writeConfig(python.absPath);
  console.log(`\nConfig: ${path.join(GRADATA_HOME, 'config.toml')}`);
  console.log('Ready.\n');
}

main().catch(e => { console.error(e.message); process.exit(1); });
