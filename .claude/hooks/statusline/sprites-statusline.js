#!/usr/bin/env node
// Gradata Statusline v9 — Zero subprocess spawns
// Line 1: Identity + context window + time
// Line 2: Jobs | Overdue | Deals | Reply rate | Learning | Saved
//
// v9: Replaced all Python, curl, and git CLI spawns with native Node.
// Uses better-sqlite3 for DB, node:https for Pipedrive, .git/ reads for timestamps.

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
    const cfg = require('../config.js');
    const dir = (data.workspace && data.workspace.current_dir) || data.cwd || cfg.WORKING_DIR;
    const session = data.session_id || '';
    const remaining = data.context_window ? data.context_window.remaining_percentage : (data.remaining_context_percentage || null);

    // Native modules — zero spawns
    const nativeDb = require('../native-db.js');
    const nativeGit = require('../native-git.js');
    const nativeHttp = require('../native-http.js');

    const c = {
      reset: '\x1b[0m', dim: '\x1b[2m', bold: '\x1b[1m',
      green: '\x1b[32m', yellow: '\x1b[33m', orange: '\x1b[38;5;208m',
      red: '\x1b[31m', cyan: '\x1b[36m', white: '\x1b[37m',
    };

    // ── Context Window ──────────────────────────────────────────────
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
            try { history = JSON.parse(fs.readFileSync(historyPath, 'utf8')); } catch { history = []; }
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
        } catch {}
      }

      let color = c.green;
      if (usedPct >= 80) color = c.red;
      else if (usedPct >= 65) color = c.orange;
      else if (usedPct >= 50) color = c.yellow;

      let bracket = 'FRESH', bracketColor = c.green;
      if (usedPct >= 80) { bracket = 'CRITICAL'; bracketColor = c.red; }
      else if (usedPct >= 65) { bracket = 'DEPLETED'; bracketColor = c.orange; }
      else if (usedPct >= 35) { bracket = 'MODERATE'; bracketColor = c.yellow; }

      ctxDisplay = `${color}ctx: ${usedPct}%${burnInfo}${c.reset} ${bracketColor}${c.bold}${bracket}${c.reset}`;
    }

    // ── Session Number (Anthropic session logs) ─────────────────────
    // Count .jsonl files across all ~/.claude/projects/ dirs — each file
    // is one real Claude Code session, regardless of project or worktree.
    let currentSession = 0;
    try {
      const projectsDir = path.join(os.homedir(), '.claude', 'projects');
      if (fs.existsSync(projectsDir)) {
        let count = 0;
        for (const entry of fs.readdirSync(projectsDir)) {
          const entryPath = path.join(projectsDir, entry);
          try {
            if (fs.statSync(entryPath).isDirectory()) {
              for (const f of fs.readdirSync(entryPath)) {
                if (f.endsWith('.jsonl')) count++;
              }
            }
          } catch {}
        }
        currentSession = count;
      }
    } catch {}

    // ── Time ────────────────────────────────────────────────────────
    const timeStr = new Date().toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', hour12: true });

    // ══════════════════════════════════════════════════════════════════
    // LINE 1: Identity + Context
    // ══════════════════════════════════════════════════════════════════
    const line1 = [
      `${c.bold}${c.cyan}Gradata${c.reset}`,
      currentSession > 0 ? `${c.bold}${c.white}S${currentSession}${c.reset}` : '',
      `${c.dim}${model}${c.reset}`,
      ctxDisplay,
      `${c.dim}${timeStr}${c.reset}`,
    ].filter(Boolean);

    // ══════════════════════════════════════════════════════════════════
    // LINE 2: The 6 things that matter (all zero-spawn)
    // ══════════════════════════════════════════════════════════════════

    // 1. JOBS QUEUED — native SQLite via better-sqlite3 (was: Python spawn)
    let jobsDisplay = '';
    try {
      const jd = nativeDb.getJobQueue(cfg.SYSTEM_DB);
      if (jd.pending > 0) {
        let age = '';
        if (jd.oldest) {
          const diffMs = Date.now() - new Date(jd.oldest).getTime();
          const hrs = Math.floor(diffMs / 3600000);
          age = hrs < 24 ? `${hrs}h` : `${Math.floor(hrs / 24)}d`;
        }
        jobsDisplay = `${c.yellow}${c.bold}${jd.pending} jobs${age ? ` (${age})` : ''}${c.reset}`;
      }
    } catch {}

    // 2. OVERDUE DEALS — file-based cache + async refresh (was: curl spawn)
    const PIPEDRIVE_CACHE = path.join(os.tmpdir(), 'gradata-pipedrive-cache.json');
    const CACHE_TTL_MS = 5 * 60 * 1000;
    const MORNING_BRIEF = path.join(cfg.BRAIN_DIR, 'morning-brief.md');
    const BRIEF_MAX_AGE_MS = 24 * 60 * 60 * 1000;

    let overdueCount = 0, activeDealsCount = 0, pipelineVal = '--';
    let overdueSource = '';
    let _startupBriefCache = ''; // cached for reuse in reply-rate section

    try {
      const startupBriefPath = path.join(dir, 'domain', 'pipeline', 'startup-brief.md');
      const briefSources = [MORNING_BRIEF, startupBriefPath];
      for (const bp of briefSources) {
        if (overdueSource) break;
        if (!fs.existsSync(bp)) continue;
        const briefAge = Date.now() - fs.statSync(bp).mtimeMs;
        if (briefAge > BRIEF_MAX_AGE_MS) continue;
        const briefText = fs.readFileSync(bp, 'utf8');
        if (bp === startupBriefPath) _startupBriefCache = briefText;
        const qcMatch = briefText.match(/Overdue Deals \((\d+) need action/);
        if (qcMatch) { overdueCount = parseInt(qcMatch[1]); overdueSource = 'qc'; break; }
        const sbMatch = briefText.match(/(\d+) truly overdue/);
        if (sbMatch) { overdueCount = parseInt(sbMatch[1]); overdueSource = 'sb'; break; }
      }
    } catch {}

    // Pipedrive: read processed cache, trigger async refresh if stale (zero spawns)
    let pdData = null;
    try {
      if (fs.existsSync(PIPEDRIVE_CACHE)) {
        const cached = JSON.parse(fs.readFileSync(PIPEDRIVE_CACHE, 'utf8'));
        if (Date.now() - cached.ts < CACHE_TTL_MS) {
          pdData = cached;
        } else {
          pdData = cached; // use stale data this render
          nativeHttp.refreshPipedriveDeals(
            process.env.PIPEDRIVE_TOKEN,
            PIPEDRIVE_CACHE + '.raw',
            5000
          );
        }
      }
    } catch {}

    // Process raw Pipedrive response if available (from previous async fetch)
    if (!pdData) {
      try {
        const rawPath = PIPEDRIVE_CACHE + '.raw';
        if (fs.existsSync(rawPath)) {
          const raw = JSON.parse(fs.readFileSync(rawPath, 'utf8'));
          const deals = raw.data || [];
          const now = new Date(); now.setHours(0,0,0,0);
          let overdue = 0, activeCount = 0, totalValue = 0;
          const OLIVER_LABEL = '45';
          for (const d of deals) {
            const labels = String(d.label || '').split(',').map(s => s.trim());
            if (!labels.includes(OLIVER_LABEL)) continue;
            totalValue += (d.value || 0);
            activeCount++;
            const nextAct = d.next_activity_date;
            if (nextAct) {
              const actDate = new Date(nextAct); actDate.setHours(0,0,0,0);
              if (actDate < now) overdue++;
            }
          }
          pdData = { overdue, activeCount, totalValue, ts: Date.now() };
          fs.writeFileSync(PIPEDRIVE_CACHE, JSON.stringify(pdData));
          try { fs.unlinkSync(rawPath); } catch {}
        }
      } catch {}
    }

    if (pdData) {
      if (!overdueSource) overdueCount = pdData.overdue || 0;
      activeDealsCount = pdData.activeCount || 0;
      const pv = pdData.totalValue || 0;
      pipelineVal = pv >= 1000 ? '$' + (pv / 1000).toFixed(1) + 'K' : pv > 0 ? '$' + pv.toFixed(0) : '--';
    }

    let overdueDisplay = '';
    if (overdueCount > 0) {
      overdueDisplay = `${c.red}${c.bold}${overdueCount} overdue${c.reset}`;
    }

    // 3. DEALS + PIPELINE VALUE
    const dealsDisplay = activeDealsCount > 0
      ? `${c.cyan}${activeDealsCount} deals ${pipelineVal}${c.reset}`
      : '';

    // 4. REPLY RATE — reuse cached startup-brief from overdue section (one read, not two)
    let replyRate = '', replyRateNum = 0;
    if (!_startupBriefCache) {
      // Wasn't read in overdue loop (e.g. morning-brief matched first) — read now
      try {
        const sbp = path.join(dir, 'domain', 'pipeline', 'startup-brief.md');
        if (fs.existsSync(sbp)) _startupBriefCache = fs.readFileSync(sbp, 'utf8');
      } catch {}
    }
    if (_startupBriefCache) {
      const m = _startupBriefCache.match(/Oliver.s Instantly reply rate:\*{0,2}\s*([\d.]+)%/);
      if (m) { replyRateNum = parseFloat(m[1]); }
    }
    if (replyRateNum === 0) {
      try {
        const bd = nativeDb.getBrainScores(cfg.SYSTEM_DB);
        if ((bd.reply_rate || 0) > 0) replyRateNum = bd.reply_rate;
        else if ((bd.reply_rate_cum || 0) > 0) replyRateNum = bd.reply_rate_cum;
      } catch {}
    }
    if (replyRateNum > 0) {
      const rColor = replyRateNum >= 2 ? c.green : replyRateNum >= 1 ? c.yellow : c.dim;
      replyRate = `${rColor}${replyRateNum.toFixed(1)}% reply${c.reset}`;
    }

    // 5. LEARNING — parse lessons.md directly in Node (was: Python spawn)
    let learningDisplay = '';
    try {
      if (fs.existsSync(cfg.LESSONS_FILE)) {
        const text = fs.readFileSync(cfg.LESSONS_FILE, 'utf8');
        const lines = text.split('\n');
        let rules = 0, learning = 0;
        for (const line of lines) {
          const match = line.match(/^\[[\d-]+\]\s+\[(RULE|PATTERN|INSTINCT):([\d.]+)\]/);
          if (match) {
            if (match[1] === 'RULE') rules++;
            else learning++;
          }
        }
        const rColor = rules > 0 ? c.green : c.dim;
        const lColor = learning > 0 ? c.yellow : c.dim;
        learningDisplay = `${rColor}${rules} rules${c.reset} ${lColor}${learning} learning${c.reset}`;
      }
    } catch {}

    // 6. BRAIN SAVE AGE — read .git/ directly (was: git CLI spawn)
    let savedDisplay = '';
    const brainTs = nativeGit.lastCommitTime(cfg.BRAIN_DIR);
    if (brainTs) {
      const diffMins = Math.floor((Date.now() - brainTs * 1000) / 60000);
      let age, ageColor;
      if (diffMins < 60) { age = `${diffMins}m`; ageColor = c.green; }
      else if (diffMins < 1440) { age = `${Math.floor(diffMins / 60)}h`; ageColor = diffMins > 360 ? c.orange : c.green; }
      else { age = `${Math.floor(diffMins / 1440)}d`; ageColor = c.red; }
      savedDisplay = `${ageColor}saved ${age}${c.reset}`;
    }

    // ── BUILD LINE 2 ────────────────────────────────────────────────
    const line2 = [
      jobsDisplay, overdueDisplay, dealsDisplay, replyRate, learningDisplay, savedDisplay
    ].filter(Boolean);

    if (line2.length === 0) line2.push(`${c.green}All clear${c.reset}`);

    // ── OUTPUT ───────────────────────────────────────────────────────
    const sep = ` ${c.dim}\u2502${c.reset} `;
    process.stdout.write(line1.join(sep) + '\n' + line2.join(sep));

  } catch (e) {
    process.stdout.write('\x1b[36mGradata\x1b[0m');
  }
});
