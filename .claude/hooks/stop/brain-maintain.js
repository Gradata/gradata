#!/usr/bin/env node
/**
 * brain-maintain.js — Stop hook
 * Auto-runs brain maintenance at session end:
 *   1. Rebuild FTS5 index (keyword search stays fresh)
 *   2. Run overnight review if last run > 12 hours ago
 *
 * Silent on failure — never blocks session end.
 */
const fs = require('fs');
const path = require('path');
const os = require('os');

const cfg = require('../config.js');
const { execSafe } = cfg;
const PYTHON = cfg.PYTHON;
const BRAIN = cfg.BRAIN_DIR;
const SCRIPTS = cfg.SCRIPTS;

// 0. Auto-accept: agent-written files that Oliver never edited = accepted without changes
try {
  const manifestPath = path.join(os.tmpdir(), 'agent-written-files.json');
  if (fs.existsSync(manifestPath)) {
    const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
    const remaining = Object.entries(manifest);
    if (remaining.length > 0) {
      for (const [filePath, entry] of remaining) {
        const agentName = entry.agent || 'unknown';
        const taskId = `auto_${agentName}_${entry.written_at || 'unknown'}`;
        // Log as accepted, not edited (Oliver saw it and didn't change it)
        execSafe(
          `"${PYTHON}" -c "import sys; sys.path.insert(0, r'${SCRIPTS}'); from spawn import log_human_judgment; log_human_judgment('${taskId.replace(/'/g, '')}', '${agentName.replace(/'/g, '')}', accepted=True, edited=False)"`,
          { timeout: 3000, stdio: 'ignore' }
        );
      }
      // Clear manifest
      fs.writeFileSync(manifestPath, '{}');
    }
  }
} catch (e) {
  // Silent
}

// 1. Ensure daily_metrics row exists (carries forward Instantly/Gmail data if no fresh pull)
try {
  execSafe(
    `"${PYTHON}" "${path.join(SCRIPTS, 'snapshot.py')}" save-minimal`,
    { timeout: 10000, stdio: 'ignore' }
  );
} catch (e) {
  // Silent
}

// 2. Rebuild FTS5 index (fast — just re-indexes brain markdown files)
try {
  execSafe(
    `"${PYTHON}" -c "import sys; sys.path.insert(0, r'${SCRIPTS}'); from query import fts_rebuild; n = fts_rebuild(); print(f'FTS5: {n} chunks')"`,
    { timeout: 8000, stdio: 'ignore' }
  );
} catch (e) {
  // Silent
}

// 3. [REMOVED] ChromaDB embedding — killed per S42 research decision (sqlite-vec replacement).
//    FTS5 (step 2) handles keyword search. Semantic search via sqlite-vec is future work.
//    Saves ~45s per session.

// 3. Update PATTERNS.md from tagged events (closes the learning loop)
try {
  execSafe(
    `"${PYTHON}" "${path.join(SCRIPTS, 'patterns_updater.py')}"`,
    { timeout: 10000, stdio: 'ignore' }
  );
} catch (e) {
  // Silent
}

// 4. Extract facts from any prospect files modified this session
try {
  execSafe(
    `"${PYTHON}" "${path.join(SCRIPTS, 'fact_extractor.py')}" extract`,
    { timeout: 8000, stdio: 'ignore' }
  );
} catch (e) {
  // Silent
}

// 5. Generate brain.manifest.json
try {
  execSafe(
    `"${PYTHON}" "${path.join(SCRIPTS, 'brain_manifest.py')}"`,
    { timeout: 10000, stdio: 'ignore' }
  );
} catch (e) {
  // Silent
}

// 6. Calibrate deal health
try {
  execSafe(
    `"${PYTHON}" "${path.join(SCRIPTS, 'deal_calibration.py')}"`,
    { timeout: 8000, stdio: 'ignore' }
  );
} catch (e) {
  // Silent
}

// 7. Dream consolidation (cooldown-gated: 24h + 5 sessions)
try {
  execSafe(
    `"${PYTHON}" "${path.join(SCRIPTS, 'dream.py')}" run`,
    { timeout: 15000, stdio: 'ignore' }
  );
} catch (e) {
  // Silent — dream is best-effort maintenance
}

// 8. Regen morning brief if stale (> 12h old)
try {
  const briefPath = path.join(BRAIN, 'morning-brief.md');
  let shouldRun = true;

  if (fs.existsSync(briefPath)) {
    const stat = fs.statSync(briefPath);
    const ageHours = (Date.now() - stat.mtimeMs) / (1000 * 60 * 60);
    shouldRun = ageHours > 12;
  }

  if (shouldRun) {
    execSafe(
      `"${PYTHON}" "${path.join(SCRIPTS, 'scheduled', 'overnight_review.py')}"`,
      { timeout: 10000, stdio: 'ignore' }
    );
  }
} catch (e) {
  // Silent
}

// 9. Auto-commit brain repo (prevents stale/backdated data next session)
try {
  const brainStatus = execSafe(`git -C "${BRAIN}" status --porcelain`, { encoding: 'utf8', timeout: 5000 }).trim();
  if (brainStatus) {
    execSafe(`git -C "${BRAIN}" add -A`, { timeout: 5000, stdio: 'ignore' });
    execSafe(`git -C "${BRAIN}" commit -m "Auto-save session end"`, { timeout: 10000, stdio: 'ignore' });
  }
} catch (e) {
  // Silent — git commit is best-effort
}
