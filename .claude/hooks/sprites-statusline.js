#!/usr/bin/env node
// AIOS Statusline v5 -- Domain-aware + System Health + Context Rot + Plan Usage + Delta Metrics
// Reads domain name from domain/DOMAIN.md if present

const fs = require('fs');
const path = require('path');
const os = require('os');
const { execSync } = require('child_process');

const stdinTimeout = setTimeout(() => process.exit(0), 3000);
let input = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', chunk => input += chunk);
process.stdin.on('end', () => {
  clearTimeout(stdinTimeout);
  try {
    const data = JSON.parse(input);
    const model = (data.model && data.model.display_name) || data.model || 'Claude';
    const SPRITES_ROOT = 'C:/Users/olive/OneDrive/Desktop/Sprites Work';
    const dir = (data.workspace && data.workspace.current_dir) || data.cwd || process.env.SPRITES_ROOT || SPRITES_ROOT;
    const session = data.session_id || '';
    const remaining = data.context_window ? data.context_window.remaining_percentage : (data.remaining_context_percentage || null);

    // -- Helpers --
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

    function safeExec(cmd, timeout = 2000) {
      try { return execSync(cmd, { timeout, stdio: ['pipe','pipe','pipe'] }).toString().trim(); } catch (e) { return ''; }
    }

    // -- Domain Detection (AIOS + Talent) --
    let domainTalent = '';
    const domainPath = path.join(dir, 'domain', 'DOMAIN.md');
    if (fs.existsSync(domainPath)) {
      try {
        const domainContent = fs.readFileSync(domainPath, 'utf8');
        // Look for role/talent field first (e.g., "Role: Sales" or "Talent: Sales")
        const roleMatch = domainContent.match(/(?:role|talent|profession|domain):\s*(.+)/i);
        if (roleMatch) {
          domainTalent = roleMatch[1].trim().split(/[,\n]/)[0].trim();
        } else {
          // Fallback: extract from title (e.g., "Sprites.ai Sales Domain" -> "Sales")
          const titleMatch = domainContent.match(/^#\s+(.+)/m);
          if (titleMatch) {
            const title = titleMatch[1];
            // Try to find a profession word in the title
            const professionMatch = title.match(/\b(Sales|Engineering|Marketing|Design|Support|Operations|Finance|HR|Legal|Product)\b/i);
            domainTalent = professionMatch ? professionMatch[1] : title.split(' ').slice(-2, -1)[0] || '';
          }
        }
      } catch (e) {}
    }

    const homeDir = os.homedir();

    // -- Context Bar + Burn Rate + Context Rot --
    let ctxDisplay = '';
    let usedPct = 0;
    let compactionCount = 0;
    let contextHealth = 'A';
    let contextHealthColor = c.green;
    if (remaining != null) {
      const BUFFER = 16.5;
      const usableRemaining = Math.max(0, ((remaining - BUFFER) / (100 - BUFFER)) * 100);
      usedPct = Math.max(0, Math.min(100, Math.round(100 - usableRemaining)));

      // Burn rate + compaction tracking
      let burnRate = '';
      let burnAccel = 0;
      if (session) {
        try {
          const bridgePath = path.join(os.tmpdir(), `claude-ctx-${session}.json`);
          const historyPath = path.join(os.tmpdir(), `claude-ctx-hist-${session}.json`);

          let history = [];
          if (fs.existsSync(historyPath)) {
            try { history = JSON.parse(fs.readFileSync(historyPath, 'utf8')); } catch (e) { history = []; }
          }

          const now = Math.floor(Date.now() / 1000);
          if (history.length === 0 || history[history.length - 1].used_pct !== usedPct) {
            history.push({ used_pct: usedPct, timestamp: now });
            fs.writeFileSync(historyPath, JSON.stringify(history));
          }

          // Detect compactions: used_pct drops >10% between consecutive snapshots
          for (let i = 1; i < history.length; i++) {
            if (history[i].used_pct < history[i-1].used_pct - 10) compactionCount++;
          }

          // Burn rate over last 5 snapshots
          if (history.length >= 3) {
            const recent = history.slice(-6);
            const totalDelta = recent[recent.length - 1].used_pct - recent[0].used_pct;
            const interactions = recent.length - 1;
            const avgBurn = (totalDelta / interactions).toFixed(1);
            if (parseFloat(avgBurn) > 0) {
              const msgsLeft = Math.round((100 - usedPct) / parseFloat(avgBurn));
              burnRate = ` ~${avgBurn}%/msg ~${msgsLeft}left`;
            }

            // Burn acceleration: compare recent burn to earlier burn
            if (history.length >= 6) {
              const older = history.slice(-10, -5);
              const newer = history.slice(-5);
              if (older.length >= 2 && newer.length >= 2) {
                const oldRate = (older[older.length-1].used_pct - older[0].used_pct) / (older.length - 1);
                const newRate = (newer[newer.length-1].used_pct - newer[0].used_pct) / (newer.length - 1);
                burnAccel = newRate - oldRate;
              }
            }
          }

          fs.writeFileSync(bridgePath, JSON.stringify({
            session_id: session, remaining_percentage: remaining,
            used_pct: usedPct, timestamp: Math.floor(Date.now() / 1000)
          }));
        } catch (e) {}
      }

      // Context health score (composite: fill + compactions + burn acceleration)
      let healthScore = 100;
      healthScore -= usedPct * 0.8;                          // fill level penalty
      healthScore -= compactionCount * 15;                    // each compaction = major penalty
      healthScore -= Math.max(0, burnAccel) * 5;             // accelerating burn = struggling
      healthScore = Math.max(0, Math.min(100, healthScore));

      if (healthScore >= 80) { contextHealth = 'A'; contextHealthColor = c.green; }
      else if (healthScore >= 60) { contextHealth = 'B'; contextHealthColor = c.green; }
      else if (healthScore >= 40) { contextHealth = 'C'; contextHealthColor = c.yellow; }
      else if (healthScore >= 20) { contextHealth = 'D'; contextHealthColor = c.orange; }
      else { contextHealth = 'F'; contextHealthColor = c.red; }

      // Context bar with research-backed thresholds
      const total = 20;
      const filled = Math.round((usedPct / 100) * total);
      const empty = total - filled;
      const bar = '='.repeat(filled) + '-'.repeat(empty);

      let color = c.green;
      if (usedPct >= 80) color = c.red;       // active quality failure zone
      else if (usedPct >= 65) color = c.orange; // compact NOW
      else if (usedPct >= 50) color = c.yellow; // compact recommended
      else if (usedPct >= 35) color = c.yellow; // early degradation

      let compactLabel = '';
      if (compactionCount > 0) compactLabel = ` C:${compactionCount}`;

      ctxDisplay = `${color}[${bar}] ${usedPct}%${burnRate}${compactLabel}${c.reset}`;
    }

    // -- Current Task --
    let task = '';
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

    // -- Agent Count (running background tasks) --
    let agentCount = 0;
    if (session && fs.existsSync(todosDir)) {
      try {
        const allFiles = fs.readdirSync(todosDir)
          .filter(f => f.endsWith('.json'));
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

    // -- Lessons Count (active + graduated) --
    let lessonsCount = 0;
    let graduatedCount = 0;
    const lessonsCap = 30;
    const lessonsPath = path.join(dir, '.claude', 'lessons.md');
    if (fs.existsSync(lessonsPath)) {
      try {
        const content = fs.readFileSync(lessonsPath, 'utf8');
        lessonsCount = (content.match(/^\[/gm) || []).length;
        // Count graduated from the index table (lines starting with | # |)
        const gradMatches = content.match(/^\|\s*\d+\s*\|/gm);
        graduatedCount = gradMatches ? gradMatches.length : 0;
      } catch (e) {}
    }

    // -- Edit Rates (split by track) --
    let salesEditRate = '';
    let sysEditRate = '';
    const metricsPath = 'C:/Users/olive/SpritesWork/brain/metrics';
    if (fs.existsSync(metricsPath)) {
      try {
        const files = fs.readdirSync(metricsPath).filter(f => f.endsWith('.md')).sort().slice(-10);
        let salesOut = 0, salesRev = 0, sysOut = 0, sysRev = 0;
        for (const f of files) {
          const content = fs.readFileSync(path.join(metricsPath, f), 'utf8');
          const produced = content.match(/outputs_produced:\s*(\d+)/);
          const revised = content.match(/outputs_revised:\s*(\d+)/);
          const p = produced ? parseInt(produced[1]) : 0;
          const r = revised ? parseInt(revised[1]) : 0;
          if (content.match(/type:\s*architecture/i)) {
            sysOut += p; sysRev += r;
          } else {
            salesOut += p; salesRev += r;
          }
        }
        if (salesOut > 0) salesEditRate = `${Math.round((salesRev / salesOut) * 100)}%`;
        if (sysOut > 0) sysEditRate = `${Math.round((sysRev / sysOut) * 100)}%`;
      } catch (e) {}
    }

    // -- Brain Version --
    let brainVersion = '?';
    const versionPath = 'C:/Users/olive/SpritesWork/brain/VERSION.md';
    if (fs.existsSync(versionPath)) {
      try {
        const content = fs.readFileSync(versionPath, 'utf8');
        const match = content.match(/Current Version:\s*(v[\d.]+)/i);
        if (match) brainVersion = match[1];
      } catch (e) {}
    }

    // -- Last Git Commit Age (brain repo) --
    let gitAge = '?';
    const gitTs = safeExec('git -C "C:/Users/olive/SpritesWork/brain" log -1 --format=%ct');
    if (gitTs) {
      const diffMs = Date.now() - parseInt(gitTs) * 1000;
      const diffMins = Math.floor(diffMs / 60000);
      if (diffMins < 60) gitAge = `${diffMins}m`;
      else if (diffMins < 1440) gitAge = `${Math.floor(diffMins / 60)}h`;
      else gitAge = `${Math.floor(diffMins / 1440)}d`;
    }

    // -- Hook Health --
    let hooksOk = 0;
    let hooksTotal = 0;
    const hooksDir = path.join(dir, '.claude', 'hooks');
    if (fs.existsSync(hooksDir)) {
      try {
        const hookFiles = fs.readdirSync(hooksDir).filter(f => f.endsWith('.js'));
        hooksTotal = hookFiles.length;
        for (const hf of hookFiles) {
          const stat = fs.statSync(path.join(hooksDir, hf));
          if (stat.size > 0) hooksOk++;
        }
      } catch (e) {}
    }

    // -- Brain DB Health (entity count from system.db) --
    let dbEntities = 0;
    let dbOk = false;
    const dbPath = 'C:/Users/olive/SpritesWork/brain/system.db';
    if (fs.existsSync(dbPath)) {
      dbOk = true;
      const out = safeExec(`python -c "import sqlite3; c=sqlite3.connect('C:/Users/olive/SpritesWork/brain/system.db'); print(c.execute('SELECT COUNT(*) FROM entities').fetchone()[0])"`);
      if (out) dbEntities = parseInt(out) || 0;
    }

    // -- Gate Pass Rate (from session_metrics) --
    let gateRate = '?';
    let gateSession = 0;
    let gateRateNum = 0;
    if (dbOk) {
      const out = safeExec(`python -c "import sqlite3; c=sqlite3.connect('C:/Users/olive/SpritesWork/brain/system.db'); r=c.execute('SELECT session, gate_pass_rate FROM session_metrics ORDER BY session DESC LIMIT 1').fetchone(); print(f'{r[0]}|{r[1]}') if r else print('0|0')"`);
      if (out) {
        const [sess, rate] = out.split('|');
        gateSession = parseInt(sess) || 0;
        gateRateNum = parseFloat(rate) || 0;
        gateRate = gateRateNum > 0 ? Math.round(gateRateNum * 100) + '%' : '?';
      }
    }

    // -- Brain Scores (System/Quality/Growth from session_metrics + events) --
    let brainSystem = '?', brainQuality = '?', brainGrowth = '?', brainArch = '?';
    let brainSysNum = 0, brainQualNum = 0, brainGrowthNum = 0, brainArchNum = 0;
    let brierScore = '';
    let brierDisplay = '';
    let trendLabel = 'STABLE';
    let trendArrow = '\u2192';
    if (dbOk) {
      const out = safeExec(`python "C:/Users/olive/SpritesWork/brain/scripts/brain_scores_cli.py"`);
      if (out) {
        const parts = out.split('|');
        brainSysNum = parseFloat(parts[0]) || 0;
        brainQualNum = parseFloat(parts[1]) || 0;
        brainGrowthNum = parseFloat(parts[2]) || 100;
        brainArchNum = parseFloat(parts[3]) || 0;
        brainSystem = Math.round(brainSysNum) + '%';
        brainQuality = Math.round(brainQualNum) + '%';
        brainGrowth = Math.round(brainGrowthNum) + '%';
        brainArch = Math.round(brainArchNum) + '%';
        // Brier calibration score (index 4)
        if (parts[4] && parts[4] !== '') {
          const bVal = parseFloat(parts[4]);
          if (!isNaN(bVal)) {
            brierScore = bVal.toFixed(2);
            if (bVal < 0.10) brierDisplay = `${c.green}Cal:${brierScore}${c.reset}`;
            else if (bVal < 0.20) brierDisplay = `${c.yellow}Cal:${brierScore}${c.reset}`;
            else brierDisplay = `${c.red}Cal:${brierScore}${c.reset}`;
          }
        }
        // Trend (index 5)
        if (parts[5]) {
          trendLabel = parts[5].trim();
          if (trendLabel === 'IMPROVING') trendArrow = '\u2191';
          else if (trendLabel === 'DEGRADING') trendArrow = '\u2193';
          else trendArrow = '\u2192';
        }
      }
    }
    // Color: red = bad (needs attention), yellow = baseline (ok), green = progressing (good)
    const brainSysColor = brainSysNum >= 90 ? c.green : brainSysNum >= 70 ? c.yellow : c.red;
    const brainQualColor = brainQualNum >= 70 ? c.green : brainQualNum >= 50 ? c.yellow : c.red;
    const brainGrowthColor = brainGrowthNum > 110 ? c.green : brainGrowthNum >= 95 ? c.yellow : c.red;
    const brainArchColor = brainArchNum >= 90 ? c.green : brainArchNum >= 70 ? c.yellow : c.red;

    // -- Employment Week (Oliver started Feb 4, 2026 -- Sunday-based weeks) --
    // Week 1 starts the Sunday on or before Feb 4 (Feb 1, 2026)
    // New week begins every Sunday
    const startDate = new Date(2026, 1, 1); // Feb 1, 2026 (Sunday before Feb 4 start)
    startDate.setHours(0,0,0,0);
    const nowForWeek = new Date();
    nowForWeek.setHours(0,0,0,0);
    const employmentWeek = Math.max(1, Math.floor((nowForWeek - startDate) / (7 * 24 * 60 * 60 * 1000)) + 1);

    // -- Prospect Pipeline (live from brain/prospects/) --
    let overdueCount = 0;
    let dueTodayCount = 0;
    let activeDealsCount = 0;
    let totalActive = 0;
    const brainPath = 'C:/Users/olive/SpritesWork/brain/prospects';
    if (fs.existsSync(brainPath)) {
      try {
        const now = new Date();
        now.setHours(0,0,0,0);
        const tomorrow = new Date(now.getTime() + 24 * 60 * 60 * 1000);
        const files = fs.readdirSync(brainPath).filter(f => f.endsWith('.md') && !f.startsWith('_'));
        for (const f of files) {
          try {
            const content = fs.readFileSync(path.join(brainPath, f), 'utf8');
            const stageMatch = content.match(/stage:\s*(.+)/i);
            const stage = stageMatch ? stageMatch[1].trim() : '';
            if (stage === 'closed-won' || stage === 'closed-lost') continue;
            totalActive++;
            if (stage.includes('proposal')) activeDealsCount++;
            const match = content.match(/next_touch:\s*(.+)/i);
            if (!match) continue;
            const raw = match[1].trim();
            let touchDate = new Date(raw);
            if (isNaN(touchDate.getTime())) {
              const parts = raw.match(/^(\d{1,2})\/(\d{1,2})$/);
              if (parts) {
                touchDate = new Date(now.getFullYear(), parseInt(parts[1]) - 1, parseInt(parts[2]));
              }
            }
            if (isNaN(touchDate.getTime())) continue;
            touchDate.setHours(0,0,0,0);
            if (touchDate < now) overdueCount++;
            else if (touchDate < tomorrow) dueTodayCount++;
          } catch (e) {}
        }
      } catch (e) {}
    }

    // -- Skills Count (deduplicated across all 3 locations) --
    let skillCount = 0;
    const skillSet = new Set();
    const skillDirs = [
      path.join(dir, 'skills'),
      path.join(dir, '.claude', 'skills'),
      path.join(dir, 'domain', 'skills')
    ];
    for (const sp of skillDirs) {
      if (fs.existsSync(sp)) {
        try {
          fs.readdirSync(sp).filter(f => {
            return fs.statSync(path.join(sp, f)).isDirectory();
          }).forEach(f => skillSet.add(f));
        } catch (e) {}
      }
    }
    skillCount = skillSet.size;

    // -- MCP Count (local: .claude.json + .mcp.json) --
    let mcpTotal = 0;
    try {
      // Count from ~/.claude.json (global + project-scoped)
      const homeConfig = path.join(homeDir, '.claude.json');
      if (fs.existsSync(homeConfig)) {
        const config = JSON.parse(fs.readFileSync(homeConfig, 'utf8'));
        mcpTotal += Object.keys(config.mcpServers || {}).length;
        const dirNorm = dir.replace(/\\/g, '/');
        for (const [key, val] of Object.entries(config.projects || {})) {
          if (key.replace(/\\/g, '/') === dirNorm) {
            mcpTotal += Object.keys(val.mcpServers || {}).length;
          }
        }
      }
      // Count from project .mcp.json
      const mcpJson = path.join(dir, '.mcp.json');
      if (fs.existsSync(mcpJson)) {
        const mcp = JSON.parse(fs.readFileSync(mcpJson, 'utf8'));
        mcpTotal += Object.keys(mcp.mcpServers || {}).length;
      }
    } catch (e) {}

    // -- CARL Domains (AIOS + domain) --
    let carlCount = 0;
    const carlPaths = [path.join(dir, '.carl'), path.join(dir, 'domain', 'carl')];
    for (const cp of carlPaths) {
      if (fs.existsSync(cp)) {
        try {
          carlCount += fs.readdirSync(cp).filter(f => {
            return fs.statSync(path.join(cp, f)).isFile();
          }).length;
        } catch (e) {}
      }
    }

    // -- Time --
    const now2 = new Date();
    const timeStr = now2.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', hour12: true });

    // -- Delta Metrics (Line 4) --
    // Reply rate -- try Oliver-only from startup-brief first, fall back to system.db
    let replyRate = '?';
    let replyRateNum = 0;
    const briefPath = path.join(dir, 'domain', 'pipeline', 'startup-brief.md');
    if (fs.existsSync(briefPath)) {
      try {
        const briefContent = fs.readFileSync(briefPath, 'utf8');
        const rrMatch = briefContent.match(/Oliver.s Instantly reply rate:\*{0,2}\s*([\d.]+)%/);
        if (rrMatch) {
          replyRateNum = parseFloat(rrMatch[1]);
          replyRate = replyRateNum.toFixed(1) + '%';
        }
      } catch (e) {}
    }
    if (replyRate === '?' && dbOk) {
      const out = safeExec(`python -c "import sqlite3; c=sqlite3.connect('C:/Users/olive/SpritesWork/brain/system.db'); r=c.execute('SELECT instantly_reply_rate FROM daily_metrics ORDER BY date DESC LIMIT 1').fetchone(); print(r[0]) if r and r[0] is not None else print('')"`);
      if (out && out !== '') {
        replyRateNum = parseFloat(out);
        replyRate = replyRateNum.toFixed(1) + '%';
      }
    }

    // Pipeline value from system.db
    let pipelineVal = '?';
    if (dbOk) {
      const out = safeExec(`python -c "import sqlite3; c=sqlite3.connect('C:/Users/olive/SpritesWork/brain/system.db'); r=c.execute('SELECT pipeline_value FROM daily_metrics ORDER BY date DESC LIMIT 1').fetchone(); print(r[0]) if r and r[0] is not None else print('')"`);
      if (out && out !== '') {
        const val = parseFloat(out);
        if (val >= 1000) {
          pipelineVal = '$' + (val / 1000).toFixed(1) + 'K';
        } else {
          pipelineVal = '$' + val.toFixed(0);
        }
      }
    }

    // Deals won/lost from system.db
    let dealsWon = 0;
    let dealsLost = 0;
    let dealsDisplay = '?';
    if (dbOk) {
      const out = safeExec(`python -c "import sqlite3; c=sqlite3.connect('C:/Users/olive/SpritesWork/brain/system.db'); r=c.execute('SELECT deals_closed_won, deals_closed_lost FROM daily_metrics ORDER BY date DESC LIMIT 1').fetchone(); print(f'{r[0]}|{r[1]}') if r and r[0] is not None else print('')"`);
      if (out && out !== '') {
        const parts = out.split('|');
        dealsWon = parseInt(parts[0]) || 0;
        dealsLost = parseInt(parts[1]) || 0;
        dealsDisplay = `+${dealsWon}/-${dealsLost}`;
      }
    }

    // Outcomes count from prospect files
    let outcomesCount = 0;
    const outcomesOut = safeExec(`python -c "import os,re; files=[f for f in os.listdir('C:/Users/olive/SpritesWork/brain/prospects') if f.endswith('.md')]; c=sum(1 for f in files if re.search(r'outcome:\\s*(?!pending)\\S+', open(os.path.join('C:/Users/olive/SpritesWork/brain/prospects',f),encoding='utf-8').read(),re.I)); print(c)"`, 3000);
    if (outcomesOut && outcomesOut !== '') {
      outcomesCount = parseInt(outcomesOut) || 0;
    }

    // -- Current Session Number (from loop-state.md) --
    let currentSession = 0;
    const loopStatePath = 'C:/Users/olive/SpritesWork/brain/loop-state.md';
    if (fs.existsSync(loopStatePath)) {
      try {
        const lsContent = fs.readFileSync(loopStatePath, 'utf8').substring(0, 200);
        const sessMatch = lsContent.match(/Session\s+(\d+)/);
        if (sessMatch) currentSession = parseInt(sessMatch[1]);
      } catch (e) {}
    }

    // Tier thresholds: Seed=20, Growth=75, Proven=150
    let tierName = 'Seed';
    if (currentSession >= 150) tierName = 'Proven';
    else if (currentSession >= 75) tierName = 'Growth';
    else if (currentSession >= 20) tierName = 'Seed';
    else tierName = 'Pre-Seed';
    const tierTarget = 150;
    const tierDisplay = `${tierName}(${currentSession}/${tierTarget})`;

    // Delta line colors
    // Reply: red < 1% (below industry), yellow 1-2% (baseline), green > 2% (beating industry)
    const replyColor = replyRateNum >= 2 ? c.green : replyRateNum >= 1 ? c.yellow : c.red;
    const dealsColor = dealsWon > 0 && dealsLost > 0 ? c.yellow : dealsWon > 0 ? c.green : dealsLost > 0 ? c.red : c.white;
    // Outcomes: red < 10 (thin data), yellow 10-30 (building), green > 30 (statistical base)
    const outcomesColor = outcomesCount >= 30 ? c.green : outcomesCount >= 10 ? c.yellow : c.red;

    // -- Build Output (3 lines, professional layout) --

    const gitColor = gitAge.endsWith('d') && parseInt(gitAge) > 1 ? c.yellow : c.green;
    const gateColor = gateRateNum >= 0.95 ? c.green : gateRateNum >= 0.80 ? c.yellow : c.red;
    const gateLag = currentSession - gateSession;
    const gateDisplay = gateLag >= 3
      ? `${c.orange}Gate:${gateRate}(${gateLag}ago)${c.reset}`
      : `${gateColor}Gate:${gateRate}${c.reset}`;
    const trendColor = trendLabel === 'IMPROVING' ? c.green : trendLabel === 'DEGRADING' ? c.red : c.yellow;

    // Line 1: Identity + Context
    const line1parts = [
      `${c.bold}${c.cyan}AIOS${c.reset}`,
      domainTalent ? `${c.white}Talent: ${domainTalent}${c.reset}` : '',
      currentSession > 0 ? `${c.bold}${c.white}S${currentSession}${c.reset}` : '',
      `${c.dim}${model}${c.reset}`,
      ctxDisplay,
      `${contextHealthColor}[${contextHealth}]${c.reset}`,
      `${c.dim}${timeStr}${c.reset}`,
    ].filter(Boolean);

    // Line 2: Brain Report Card (the scores that matter)
    const brainParts = [
      gateDisplay,
      `${brainSysColor}System:${brainSystem}${c.reset}`,
      `${brainQualColor}AI Quality:${brainQuality}${c.reset}`,
      `${brainGrowthColor}Growth:${brainGrowth}${c.reset}`,
      `${brainArchColor}Arch:${brainArch}${c.reset}`,
      brierDisplay ? brierDisplay : '',
      `${trendColor}${trendArrow}${c.reset}`,
      `${gitColor}Git:${gitAge}${c.reset}`,
      `${c.cyan}Brain:${brainVersion}${c.reset}`,
    ].filter(Boolean);

    // Line 3: Pipeline + Business Metrics
    let pipeDisplay = '';
    if (overdueCount > 0) pipeDisplay += `${c.red}${c.bold}Overdue:${overdueCount}${c.reset} `;
    if (dueTodayCount > 0) pipeDisplay += `${c.yellow}Today:${dueTodayCount}${c.reset} `;
    if (activeDealsCount > 0) pipeDisplay += `${c.cyan}Deals:${activeDealsCount}${c.reset} `;
    if (!pipeDisplay) pipeDisplay = `${c.green}Pipeline: clear${c.reset} `;

    const bizParts = [
      pipeDisplay.trim(),
      `${replyColor}Reply:${replyRate}${c.reset}`,
      `${c.white}Value:${pipelineVal}${c.reset}`,
      `${dealsColor}Won/Lost:${dealsDisplay}${c.reset}`,
      `${outcomesColor}Outcomes:${outcomesCount}${c.reset}`,
      `${c.cyan}Tier:${tierDisplay}${c.reset}`,
    ];

    let output = line1parts.join(` ${c.dim}|${c.reset} `);
    output += `\n`;
    output += brainParts.join(` ${c.dim}|${c.reset} `);
    output += `\n`;
    output += bizParts.join(` ${c.dim}|${c.reset} `);

    process.stdout.write(output);

  } catch (e) {
    process.stdout.write('\x1b[36mAIOS\x1b[0m');
  }
});
