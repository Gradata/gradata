#!/usr/bin/env node
// Gradata Statusline v7 — Dashboard you can read at a glance
// Line 1: Identity + runway
// Line 2: Gates | System | Brain | Quality | Last save
// Line 3: Pipeline attention items

const fs = require('fs');
const path = require('path');
const os = require('os');
const { execSafe } = require('./config.js');

const stdinTimeout = setTimeout(() => process.exit(0), 3000);
let input = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', chunk => input += chunk);
process.stdin.on('end', () => {
  clearTimeout(stdinTimeout);
  try {
    const data = JSON.parse(input);
    const model = (data.model && data.model.display_name) || data.model || 'Claude';
    const cfg = require('./config.js');
    const SPRITES_ROOT = cfg.WORKING_DIR;
    const dir = (data.workspace && data.workspace.current_dir) || data.cwd || process.env.SPRITES_ROOT || SPRITES_ROOT;
    const session = data.session_id || '';
    const remaining = data.context_window ? data.context_window.remaining_percentage : (data.remaining_context_percentage || null);

    const c = {
      reset: '\x1b[0m', dim: '\x1b[2m', bold: '\x1b[1m',
      green: '\x1b[32m', yellow: '\x1b[33m', orange: '\x1b[38;5;208m',
      red: '\x1b[31m', cyan: '\x1b[36m', white: '\x1b[37m',
    };

    function safeExec(cmd, timeout = 2000) {
      try { return execSafe(cmd, { timeout, stdio: ['pipe','pipe','pipe'] }).toString().trim(); } catch (e) { return ''; }
    }

    // -- Context Bar --
    let ctxDisplay = '';
    let usedPct = 0;
    if (remaining != null) {
      const BUFFER = 16.5;
      const usableRemaining = Math.max(0, ((remaining - BUFFER) / (100 - BUFFER)) * 100);
      usedPct = Math.max(0, Math.min(100, Math.round(100 - usableRemaining)));

      let burnInfo = '';
      if (session) {
        try {
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
          if (history.length >= 3) {
            const recent = history.slice(-6);
            const avgBurn = (recent[recent.length - 1].used_pct - recent[0].used_pct) / (recent.length - 1);
            if (avgBurn > 0) {
              const msgsLeft = Math.round((100 - usedPct) / avgBurn);
              burnInfo = ` ~${msgsLeft} left`;
            }
          }
          const bridgePath = path.join(os.tmpdir(), `claude-ctx-${session}.json`);
          fs.writeFileSync(bridgePath, JSON.stringify({
            session_id: session, remaining_percentage: remaining,
            used_pct: usedPct, timestamp: now
          }));
        } catch (e) {}
      }

      const total = 20;
      const filled = Math.round((usedPct / 100) * total);
      const bar = '\u2588'.repeat(filled) + '\u2591'.repeat(total - filled);
      let color = c.green;
      if (usedPct >= 80) color = c.red;
      else if (usedPct >= 65) color = c.orange;
      else if (usedPct >= 50) color = c.yellow;
      else if (usedPct >= 35) color = c.yellow;
      ctxDisplay = `${color}${bar} ${usedPct}%${burnInfo}${c.reset}`;
    }

    // -- Session Number (from git: last committed S## + 1) --
    let currentSession = 0;
    const gitSubject = safeExec(`git -C "${dir}" log -1 --format=%s`);
    const sMatch = gitSubject.match(/^S(\d+):/);
    if (sMatch) {
      currentSession = parseInt(sMatch[1]) + 1;
    } else if (fs.existsSync(cfg.LOOP_STATE)) {
      // Fallback to loop-state if git doesn't have S## prefix
      try {
        const m = fs.readFileSync(cfg.LOOP_STATE, 'utf8').substring(0, 200).match(/Session\s+(\d+)/);
        if (m) currentSession = parseInt(m[1]) + 1;
      } catch (e) {}
    }

    // -- Time --
    const timeStr = new Date().toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', hour12: true });

    // -- Git Age (brain repo — the "save file") --
    let gitAge = '?';
    const gitTs = safeExec(`git -C "${cfg.BRAIN_DIR}" log -1 --format=%ct`);
    if (gitTs) {
      const diffMins = Math.floor((Date.now() - parseInt(gitTs) * 1000) / 60000);
      if (diffMins < 60) gitAge = `${diffMins}m ago`;
      else if (diffMins < 1440) gitAge = `${Math.floor(diffMins / 60)}h ago`;
      else gitAge = `${Math.floor(diffMins / 1440)}d ago`;
    }

    // ══════════════════════════════════════════════════════════════════
    // SINGLE PYTHON CALL — all brain data in ~0.1s
    // ══════════════════════════════════════════════════════════════════
    let bd = {};
    if (fs.existsSync(cfg.SYSTEM_DB)) {
      const out = safeExec(`python "${path.join(cfg.SCRIPTS, 'brain_scores_cli.py')}"`);
      if (out) { try { bd = JSON.parse(out); } catch (e) {} }
    }

    // ── LINE 1: Identity + Context ──────────────────────────────────
    // Context grade: A (fresh, <35%), B (moderate, 35-50%), C (heavy, 50-65%), D (depleted, 65-80%), F (critical, 80%+)
    let ctxGrade = '', ctxGradeColor = c.green;
    if (typeof usedPct === 'number') {
      if (usedPct < 35) { ctxGrade = 'A'; ctxGradeColor = c.green; }
      else if (usedPct < 50) { ctxGrade = 'B'; ctxGradeColor = c.green; }
      else if (usedPct < 65) { ctxGrade = 'C'; ctxGradeColor = c.yellow; }
      else if (usedPct < 80) { ctxGrade = 'D'; ctxGradeColor = c.orange; }
      else { ctxGrade = 'F'; ctxGradeColor = c.red; }
    }
    const gradeDisplay = ctxGrade ? `${ctxGradeColor}${c.bold}${ctxGrade}${c.reset}` : '';

    const line1 = [
      `${c.bold}${c.cyan}Gradata${c.reset}`,
      currentSession > 0 ? `${c.bold}${c.white}S${currentSession}${c.reset}` : '',
      `${c.dim}${model}${c.reset}`,
      ctxDisplay,
      gradeDisplay,
      `${c.dim}${timeStr}${c.reset}`,
    ].filter(Boolean);

    // ── LINE 2: The 5 things that matter ────────────────────────────

    // GATES: Did last session close properly? Show pass/total
    // If gate data is stale (not from previous session), flag it
    const gP = bd.gate_passed || 0;
    const gT = bd.gate_total || 0;
    const gS = parseInt(bd.gate_session) || 0;
    const prevSession = currentSession - 1;
    let gatesDisplay;
    if (gT === 0) {
      gatesDisplay = `${c.red}Gates: no data${c.reset}`;
    } else if (gS >= prevSession) {
      // Fresh — from last session or current
      if (gP === gT) {
        gatesDisplay = `${c.green}Gates: ${gP}/${gT}${c.reset}`;
      } else {
        gatesDisplay = `${c.red}Gates: ${gP}/${gT}${c.reset}`;
      }
    } else {
      // Stale — wrap-up hasn't run for recent sessions
      const gap = prevSession - gS;
      gatesDisplay = `${c.orange}Gates: ${gP}/${gT} (S${gS}, ${gap} ago)${c.reset}`;
    }

    // SYSTEM: Simple — did the last wrap-up pass all checks?
    const gateRate = gT > 0 ? gP / gT : 0;
    const sysPct = Math.round(gateRate * 100);
    const isFresh = gS >= prevSession;
    let sysDisplay;
    if (!isFresh) {
      sysDisplay = `${c.orange}System: ${sysPct}% (stale)${c.reset}`;
    } else if (sysPct >= 100) {
      sysDisplay = `${c.green}System: ${sysPct}%${c.reset}`;
    } else if (sysPct >= 80) {
      sysDisplay = `${c.yellow}System: ${sysPct}%${c.reset}`;
    } else {
      sysDisplay = `${c.red}System: ${sysPct}%${c.reset}`;
    }

    // BRAIN: Is it growing? Show arrow based on pattern accumulation trend
    const pP = bd.patterns_proven || 0;
    const pE = bd.patterns_emerging || 0;
    const pT = bd.patterns_total || 0;
    const know = bd.knowledge_total || 0;
    // Brain is growing if proven patterns are accumulating
    let brainArrow, brainColor;
    if (pP >= 30) {
      brainArrow = '\u2197'; // ↗ trending up
      brainColor = c.green;
    } else if (pT >= 30) {
      brainArrow = '\u2192'; // → steady, collecting
      brainColor = c.yellow;
    } else if (pT > 0) {
      brainArrow = '\u2192'; // → just started
      brainColor = c.yellow;
    } else {
      brainArrow = '\u2012'; // - nothing yet
      brainColor = c.red;
    }
    const brainDisplay = `${brainColor}Brain: ${brainArrow} ${pP}P/${pE}E/${pT}total${c.reset}`;

    // QUALITY: Is AI output getting better? Arrow from correction trend
    const densTrend = bd.density_trend || 'unknown';
    let qualArrow, qualColor;
    if (densTrend === 'improving') {
      qualArrow = '\u2197'; // ↗
      qualColor = c.green;
    } else if (densTrend === 'stable') {
      qualArrow = '\u2192'; // →
      qualColor = c.yellow;
    } else if (densTrend === 'degrading') {
      qualArrow = '\u2198'; // ↘
      qualColor = c.red;
    } else {
      qualArrow = '\u2192';
      qualColor = c.dim;
    }
    const qualDisplay = `${qualColor}Quality: ${qualArrow}${c.reset}`;

    // SAVED: Two save files — brain (trained data) + code (the game itself)
    // Brain repo = your progress save. Code repo = the game build.
    let brainAge = '?', codeAge = '?';
    const brainTs = safeExec(`git -C "${cfg.BRAIN_DIR}" log -1 --format=%ct`);
    if (brainTs) {
      const m = Math.floor((Date.now() - parseInt(brainTs) * 1000) / 60000);
      brainAge = m < 60 ? `${m}m` : m < 1440 ? `${Math.floor(m / 60)}h` : `${Math.floor(m / 1440)}d`;
    }
    const codeTs = safeExec(`git -C "${SPRITES_ROOT}" log -1 --format=%ct`);
    if (codeTs) {
      const m = Math.floor((Date.now() - parseInt(codeTs) * 1000) / 60000);
      codeAge = m < 60 ? `${m}m` : m < 1440 ? `${Math.floor(m / 60)}h` : `${Math.floor(m / 1440)}d`;
    }
    const brainGitColor = brainAge.includes('d') && parseInt(brainAge) > 1 ? c.orange : c.green;
    const codeGitColor = codeAge.includes('d') && parseInt(codeAge) > 1 ? c.orange : c.green;
    const savedDisplay = `${brainGitColor}Brain:${brainAge}${c.reset} ${codeGitColor}Code:${codeAge}${c.reset}`;

    const line2 = [gatesDisplay, sysDisplay, brainDisplay, qualDisplay, savedDisplay];

    // ── LINE 3: What needs attention (LIVE from Pipedrive) ─────────
    // Cache Pipedrive data to tmpfile, refresh every 5 minutes
    const PIPEDRIVE_TOKEN = 'REDACTED_PIPEDRIVE_TOKEN';
    const PIPEDRIVE_CACHE = path.join(os.tmpdir(), 'gradata-pipedrive-cache.json');
    const CACHE_TTL_MS = 5 * 60 * 1000; // 5 minutes

    let overdueCount = 0, dueTodayCount = 0, activeDealsCount = 0;
    let pipelineVal = '--', replyRate = '?', replyRateNum = 0;

    function loadPipedriveCache() {
      try {
        if (fs.existsSync(PIPEDRIVE_CACHE)) {
          const cached = JSON.parse(fs.readFileSync(PIPEDRIVE_CACHE, 'utf8'));
          if (Date.now() - cached.ts < CACHE_TTL_MS) return cached;
        }
      } catch (e) {}
      return null;
    }

    function fetchPipedriveLive() {
      try {
        const https = require('https');
        const url = `https://api.pipedrive.com/v1/deals?status=open&limit=500&api_token=${PIPEDRIVE_TOKEN}`;
        const raw = execSafe(`node -e "const https=require('https');https.get('${url}',r=>{let d='';r.on('data',c=>d+=c);r.on('end',()=>process.stdout.write(d))})"`, { timeout: 4000 }).toString();
        const data = JSON.parse(raw);
        const deals = data.data || [];

        const now = new Date(); now.setHours(0,0,0,0);
        const tomorrow = new Date(now.getTime() + 86400000);
        let overdue = 0, dueToday = 0, activeCount = 0, totalValue = 0;

        // Oliver's label ID = 45. Only count deals tagged with Oliver.
        const OLIVER_LABEL = '45';
        for (const d of deals) {
          const labels = String(d.label || '').split(',').map(s => s.trim());
          if (!labels.includes(OLIVER_LABEL)) continue;

          const val = d.value || 0;
          totalValue += val;
          activeCount++;

          // Check next activity date for overdue/due today
          const nextAct = d.next_activity_date;
          if (nextAct) {
            const actDate = new Date(nextAct); actDate.setHours(0,0,0,0);
            if (actDate < now) overdue++;
            else if (actDate < tomorrow) dueToday++;
          } else {
            // No next activity = overdue (stale deal)
            overdue++;
          }
        }

        const result = { overdue, dueToday, activeCount, totalValue, ts: Date.now() };
        try { fs.writeFileSync(PIPEDRIVE_CACHE, JSON.stringify(result)); } catch (e) {}
        return result;
      } catch (e) {
        return null;
      }
    }

    const pdData = loadPipedriveCache() || fetchPipedriveLive();
    if (pdData) {
      overdueCount = pdData.overdue || 0;
      dueTodayCount = pdData.dueToday || 0;
      activeDealsCount = pdData.activeCount || 0;
      const pv = pdData.totalValue || 0;
      pipelineVal = pv >= 1000 ? '$' + (pv / 1000).toFixed(1) + 'K' : pv > 0 ? '$' + pv.toFixed(0) : '--';
    }

    // Reply rate — still from startup brief or brain scores (Instantly doesn't have a quick endpoint)
    const briefPath = path.join(dir, 'domain', 'pipeline', 'startup-brief.md');
    if (fs.existsSync(briefPath)) {
      try {
        const m = fs.readFileSync(briefPath, 'utf8').match(/Oliver.s Instantly reply rate:\*{0,2}\s*([\d.]+)%/);
        if (m) { replyRateNum = parseFloat(m[1]); replyRate = replyRateNum.toFixed(1) + '%'; }
      } catch (e) {}
    }
    if (replyRate === '?' && (bd.reply_rate || 0) > 0) {
      replyRateNum = bd.reply_rate; replyRate = replyRateNum.toFixed(1) + '%';
    }
    if (replyRateNum === 0 && (bd.reply_rate_cum || 0) > 0) {
      replyRateNum = bd.reply_rate_cum; replyRate = replyRateNum.toFixed(1) + '%';
    }
    const replyColor = replyRateNum >= 2 ? c.green : replyRateNum >= 1 ? c.yellow : c.red;

    // Build line 3
    const line3parts = [];
    if (overdueCount > 0) line3parts.push(`${c.red}${c.bold}${overdueCount} overdue${c.reset}`);
    if (dueTodayCount > 0) line3parts.push(`${c.yellow}${dueTodayCount} due today${c.reset}`);
    if (activeDealsCount > 0) line3parts.push(`${c.cyan}${activeDealsCount} deals${c.reset}`);
    if (line3parts.length === 0) line3parts.push(`${c.green}Pipeline clear${c.reset}`);
    line3parts.push(`${replyColor}${replyRate} reply${c.reset}`);
    line3parts.push(`${c.white}${pipelineVal} pipeline${c.reset}`);
    const tierName = currentSession >= 150 ? 'Proven' : currentSession >= 75 ? 'Growth' : currentSession >= 20 ? 'Seed' : 'Pre-Seed';
    line3parts.push(`${c.dim}${tierName}${c.reset}`);

    // ── OUTPUT ───────────────────────────────────────────────────────
    const sep = ` ${c.dim}\u2502${c.reset} `;
    process.stdout.write(line1.join(sep) + '\n' + line2.join(sep) + '\n' + line3parts.join(sep));

  } catch (e) {
    process.stdout.write('\x1b[36mGradata\x1b[0m');
  }
});
