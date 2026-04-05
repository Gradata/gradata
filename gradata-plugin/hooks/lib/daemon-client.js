// gradata-plugin/hooks/lib/daemon-client.js
/**
 * Connect-or-spawn protocol for Gradata daemon.
 * Every hook calls ensureDaemon() then callDaemon(endpoint, body).
 */
const fs = require('fs');
const path = require('path');
const { execSync, spawn } = require('child_process');
const crypto = require('crypto');

const COMPATIBLE_SDK = /^0\.\d+\.\d+/; // 0.x.x
const GRADATA_HOME = path.join(process.env.HOME || process.env.USERPROFILE || '~', '.gradata');

/** Resolve brain directory from git remote or CWD. */
function resolveBrainDir() {
  let key = '';
  try {
    key = execSync('git remote get-url origin 2>/dev/null', {
      encoding: 'utf8', windowsHide: true, timeout: 2000,
    }).trim().replace(/\.git$/, '').toLowerCase();
  } catch {}
  if (!key) {
    try {
      key = execSync('git rev-parse --show-toplevel 2>/dev/null', {
        encoding: 'utf8', windowsHide: true, timeout: 2000,
      }).trim();
    } catch {}
  }
  if (!key) key = process.cwd();
  const hash = crypto.createHash('sha256').update(key).digest('hex').slice(0, 12);
  return path.join(GRADATA_HOME, 'projects', hash);
}

/** Read PID file for a brain directory. Returns parsed JSON or null. */
function readPidFile(brainDir) {
  const pidPath = path.join(brainDir, 'daemon.pid');
  try {
    return JSON.parse(fs.readFileSync(pidPath, 'utf8'));
  } catch { return null; }
}

/** Check if a process is alive. */
function isAlive(pid) {
  try { process.kill(pid, 0); return true; } catch { return false; }
}

/** Read Python path from config.toml. */
function getPythonPath() {
  try {
    const configPath = path.join(GRADATA_HOME, 'config.toml');
    const content = fs.readFileSync(configPath, 'utf8');
    const match = content.match(/python_path\s*=\s*"([^"]+)"/);
    return match ? match[1] : 'python3';
  } catch { return 'python3'; }
}

/** Spawn the daemon for a brain directory. */
function spawnDaemon(brainDir) {
  const python = getPythonPath();
  const isWin = process.platform === 'win32';
  // On Windows, use pythonw.exe for no CMD flash
  const cmd = isWin ? python.replace(/python(3)?\.exe$/i, 'pythonw$1.exe') : python;

  fs.mkdirSync(brainDir, { recursive: true });

  const child = spawn(cmd, ['-m', 'gradata.daemon', '--brain-dir', brainDir], {
    stdio: 'ignore',
    detached: true,
    windowsHide: true,
  });
  child.unref();
}

/** HTTP fetch to daemon. Returns parsed JSON or null. */
async function fetchDaemon(port, endpoint, body, timeoutMs) {
  const url = `http://127.0.0.1:${port}${endpoint}`;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const opts = body != null
      ? { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body), signal: controller.signal }
      : { signal: controller.signal };
    const resp = await fetch(url, opts);
    return await resp.json();
  } catch { return null; }
  finally { clearTimeout(timer); }
}

/** Sleep helper. */
function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

/** Ensure daemon is running. Returns port number or null. */
async function ensureDaemon(brainDir) {
  brainDir = brainDir || resolveBrainDir();
  const pid = readPidFile(brainDir);

  // Try existing daemon
  if (pid) {
    const health = await fetchDaemon(pid.port, '/health', null, 500);
    if (health && health.status === 'ok') {
      if (pid.sdk_version && !COMPATIBLE_SDK.test(pid.sdk_version)) {
        process.stderr.write(`[gradata] SDK version ${pid.sdk_version} incompatible\n`);
        return null;
      }
      return pid.port;
    }
    // Daemon not responding — clean up stale PID
    if (pid.pid && !isAlive(pid.pid)) {
      try { fs.unlinkSync(path.join(brainDir, 'daemon.pid')); } catch {}
    }
  }

  // Spawn new daemon
  spawnDaemon(brainDir);

  // Poll for startup (up to 3s)
  for (let i = 0; i < 10; i++) {
    await sleep(300);
    const newPid = readPidFile(brainDir);
    if (newPid) {
      const health = await fetchDaemon(newPid.port, '/health', null, 500);
      if (health && health.status === 'ok') return newPid.port;
    }
  }
  return null; // Daemon didn't start in time
}

/**
 * Call a daemon endpoint. Returns response JSON or null.
 * @param {string} endpoint - e.g. "/apply-rules"
 * @param {object|null} body - request body (null for GET)
 * @param {number} timeoutMs - request timeout (default 2000)
 */
async function callDaemon(endpoint, body, timeoutMs = 2000) {
  const brainDir = resolveBrainDir();
  const port = await ensureDaemon(brainDir);
  if (!port) return null;
  return fetchDaemon(port, endpoint, body, timeoutMs);
}

module.exports = { resolveBrainDir, ensureDaemon, callDaemon, fetchDaemon, getPythonPath, GRADATA_HOME };
