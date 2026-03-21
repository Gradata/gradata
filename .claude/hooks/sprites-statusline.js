#!/usr/bin/env node
// Sprites.ai Sales Statusline v2
// Clean, readable, no broken unicode

const fs = require('fs');
const path = require('path');
const os = require('os');

const stdinTimeout = setTimeout(() => process.exit(0), 3000);
let input = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', chunk => input += chunk);
process.stdin.on('end', () => {
  clearTimeout(stdinTimeout);
  try {
    const data = JSON.parse(input);
    const model = (data.model && data.model.display_name) || data.model || 'Claude';
    // Hardcode project root as fallback — Claude Code may not pass cwd to statusline hooks
    const SPRITES_ROOT = 'C:/Users/olive/OneDrive/Desktop/Sprites Work';
    const dir = (data.workspace && data.workspace.current_dir) || data.cwd || process.env.SPRITES_ROOT || SPRITES_ROOT;
    const session = data.session_id || '';
    const remaining = data.context_window ? data.context_window.remaining_percentage : (data.remaining_context_percentage || null);

    // ── Helpers ──
    const c = {
      reset: '\x1b[0m',
      dim: '\x1b[2m',
      bold: '\x1b[1m',
      green: '\x1b[32m',
      yellow: '\x1b[33m',
      orange: '\x1b[38;5;208m',
      red: '\x1b[31m',
      cyan: '\x1b[36m',
      magenta: '\x1b[35m',
      blue: '\x1b[34m',
      white: '\x1b[37m',
      blink: '\x1b[5m',
    };

    // ── Context Bar (using simple ASCII) ──
    let ctxDisplay = '';
    let usedPct = 0;
    if (remaining != null) {
      const BUFFER = 16.5;
      const usableRemaining = Math.max(0, ((remaining - BUFFER) / (100 - BUFFER)) * 100);
      usedPct = Math.max(0, Math.min(100, Math.round(100 - usableRemaining)));

      // Bridge file
      if (session) {
        try {
          const bridgePath = path.join(os.tmpdir(), `claude-ctx-${session}.json`);
          fs.writeFileSync(bridgePath, JSON.stringify({
            session_id: session, remaining_percentage: remaining,
            used_pct: usedPct, timestamp: Math.floor(Date.now() / 1000)
          }));
        } catch (e) {}
      }

      // Simple bar: [====------] 42%
      const total = 20;
      const filled = Math.round((usedPct / 100) * total);
      const empty = total - filled;
      const bar = '='.repeat(filled) + '-'.repeat(empty);

      let color = c.green;
      if (usedPct >= 80) color = c.red;
      else if (usedPct >= 65) color = c.orange;
      else if (usedPct >= 50) color = c.yellow;

      ctxDisplay = `${color}[${bar}] ${usedPct}%${c.reset}`;
    }

    // ── Current Task ──
    let task = '';
    const homeDir = os.homedir();
    const claudeDir = process.env.CLAUDE_CONFIG_DIR || path.join(homeDir, '.claude');
    const todosDir = path.join(claudeDir, 'todos');
    if (session && fs.existsSync(todosDir)) {
      try {
        const files = fs.readdirSync(todosDir)
          .filter(f => f.startsWith(session) && f.includes('-agent-') && f.endsWith('.json'))
          .map(f => ({ name: f, mtime: fs.statSync(path.join(todosDir, f)).mtime }))
          .sort((a, b) => b.mtime - a.mtime);
        if (files.length > 0) {
          const todos = JSON.parse(fs.readFileSync(path.join(todosDir, files[0].name), 'utf8'));
          const inProgress = todos.find(t => t.status === 'in_progress');
          if (inProgress) task = inProgress.activeForm || '';
        }
      } catch (e) {}
    }

    // ── Agent Count (running background tasks) ──
    let agentCount = 0;
    if (session && fs.existsSync(todosDir)) {
      try {
        const allFiles = fs.readdirSync(todosDir)
          .filter(f => f.endsWith('.json'));
        // Count unique active agent sessions
        const agentSessions = new Set();
        for (const f of allFiles) {
          try {
            const todos = JSON.parse(fs.readFileSync(path.join(todosDir, f), 'utf8'));
            const active = todos.filter(t => t.status === 'in_progress');
            if (active.length > 0) agentSessions.add(f);
          } catch (e) {}
        }
        agentCount = agentSessions.size;
      } catch (e) {}
    }

    // ── Lessons Count ──
    let lessonsCount = 0;
    const lessonsPath = path.join(dir, '.claude', 'lessons.md');
    if (fs.existsSync(lessonsPath)) {
      try {
        const content = fs.readFileSync(lessonsPath, 'utf8');
        lessonsCount = (content.match(/^\[/gm) || []).length;
      } catch (e) {}
    }

    // ── Prospect Count ──
    let prospectCount = 0;
    const brainPath = 'C:/Users/olive/SpritesWork/brain/prospects';
    if (fs.existsSync(brainPath)) {
      try {
        prospectCount = fs.readdirSync(brainPath).filter(f => f.endsWith('.md')).length;
      } catch (e) {}
    }

    // ── Skills Count ──
    let skillCount = 0;
    const skillsPath = path.join(dir, 'skills');
    if (fs.existsSync(skillsPath)) {
      try {
        skillCount = fs.readdirSync(skillsPath).filter(f => {
          return fs.statSync(path.join(skillsPath, f)).isDirectory();
        }).length;
      } catch (e) {}
    }

    // ── MCP Count ──
    let mcpTotal = 0;
    try {
      const homeConfig = path.join(homeDir, '.claude.json');
      if (fs.existsSync(homeConfig)) {
        const config = JSON.parse(fs.readFileSync(homeConfig, 'utf8'));
        const globalCount = Object.keys(config.mcpServers || {}).length;
        // Sum MCPs from all matching project entries (exact match on dir)
        let localCount = 0;
        const dirNorm = dir.replace(/\\/g, '/');
        for (const [key, val] of Object.entries(config.projects || {})) {
          const keyNorm = key.replace(/\\/g, '/');
          if (keyNorm === dirNorm) {
            localCount += Object.keys(val.mcpServers || {}).length;
          }
        }
        mcpTotal = globalCount + localCount;
      }
    } catch (e) {}

    // ── API Keys ──
    let apiKeys = [];
    const envPath = path.join(dir, '.env');
    if (fs.existsSync(envPath)) {
      try {
        const env = fs.readFileSync(envPath, 'utf8');
        if (env.match(/PROSPEO_API_KEY=.+/)) apiKeys.push('P');
        if (env.match(/ZEROBOUNCE_API_KEY=.+/)) apiKeys.push('ZB');
        if (env.match(/LEADMAGIC_API_KEY=.+/)) apiKeys.push('LM');
      } catch (e) {}
    }
    const apiDisplay = apiKeys.length > 0 ? `${c.green}${apiKeys.join(' ')}${c.reset}` : `${c.red}NO KEYS${c.reset}`;

    // ── CARL Domains ──
    let carlCount = 0;
    const carlPath = path.join(dir, '.carl');
    if (fs.existsSync(carlPath)) {
      try {
        carlCount = fs.readdirSync(carlPath).filter(f => {
          return fs.statSync(path.join(carlPath, f)).isFile();
        }).length;
      } catch (e) {}
    }

    // ── Time ──
    const now = new Date();
    const timeStr = now.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', hour12: true });

    // ── Build Output ──
    // Line 1: Branding | Model | Context
    const line1parts = [
      `${c.bold}${c.cyan}Sprites.ai${c.reset}`,
      `${c.dim}${model}${c.reset}`,
      ctxDisplay,
      `${c.dim}${timeStr}${c.reset}`
    ];

    // Line 2: Task or Stats
    const statParts = [
      `${c.magenta}SK:${skillCount}${c.reset}`,
      `${c.blue}CARL:${carlCount}${c.reset}`,
      `${c.cyan}MCP:${mcpTotal}${c.reset}`,
      `${c.yellow}Prospects:${prospectCount}${c.reset}`,
      `${c.green}Lessons:${lessonsCount}${c.reset}`,
      `${c.dim}Keys:${c.reset}${apiDisplay}`,
    ];

    if (agentCount > 0) {
      statParts.unshift(`${c.orange}Agents:${agentCount}${c.reset}`);
    }

    let output = line1parts.join(` ${c.dim}|${c.reset} `);
    output += `\n`;

    if (task) {
      output += `${c.bold}> ${task}${c.reset} ${c.dim}|${c.reset} `;
    }
    output += statParts.join(` ${c.dim}|${c.reset} `);

    process.stdout.write(output);

  } catch (e) {
    process.stdout.write('\x1b[36mSprites.ai\x1b[0m');
  }
});
