#!/usr/bin/env node
/**
 * brain-maintain.js — Stop hook
 * Auto-runs brain maintenance at session end:
 *   1. Rebuild FTS5 index (keyword search stays fresh)
 *   2. Run overnight review if last run > 12 hours ago
 *
 * Silent on failure — never blocks session end.
 */
const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');
const os = require('os');

const PYTHON = 'C:/Users/olive/AppData/Local/Programs/Python/Python312/python.exe';
const BRAIN = 'C:/Users/olive/SpritesWork/brain';
const SCRIPTS = path.join(BRAIN, 'scripts');

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
        execSync(
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
  execSync(
    `"${PYTHON}" "${path.join(SCRIPTS, 'snapshot.py')}" save-minimal`,
    { timeout: 10000, stdio: 'ignore' }
  );
} catch (e) {
  // Silent
}

// 2. Rebuild FTS5 index (fast — just re-indexes brain markdown files)
try {
  execSync(
    `"${PYTHON}" -c "import sys; sys.path.insert(0, r'${SCRIPTS}'); from query import fts_rebuild; n = fts_rebuild(); print(f'FTS5: {n} chunks')"`,
    { timeout: 15000, stdio: 'ignore' }
  );
} catch (e) {
  // Silent
}

// 3. Delta embed changed files into ChromaDB (keeps semantic search current)
try {
  execSync(
    `"${PYTHON}" "${path.join(SCRIPTS, 'embed.py')}"`,
    { timeout: 45000, stdio: 'ignore' }
  );
} catch (e) {
  // Silent — embedding is best-effort, FTS5 already rebuilt above
}

// 4. Update PATTERNS.md from tagged events (closes the learning loop)
try {
  execSync(
    `"${PYTHON}" "${path.join(SCRIPTS, 'patterns_updater.py')}"`,
    { timeout: 10000, stdio: 'ignore' }
  );
} catch (e) {
  // Silent
}

// 5. Extract facts from any prospect files modified this session
try {
  execSync(
    `"${PYTHON}" "${path.join(SCRIPTS, 'fact_extractor.py')}" extract`,
    { timeout: 15000, stdio: 'ignore' }
  );
} catch (e) {
  // Silent
}

// 5. Generate brain.manifest.json (keeps manifest fresh for SDK/marketplace)
try {
  execSync(
    `"${PYTHON}" "${path.join(SCRIPTS, 'brain_manifest.py')}"`,
    { timeout: 10000, stdio: 'ignore' }
  );
} catch (e) {
  // Silent
}

// 6. Calibrate deal health scores
try {
  execSync(
    `"${PYTHON}" "${path.join(SCRIPTS, 'deal_calibration.py')}"`,
    { timeout: 15000, stdio: 'ignore' }
  );
} catch (e) {
  // Silent
}

// 7. Run overnight review if morning-brief is stale (> 12 hours old)
try {
  const briefPath = path.join(BRAIN, 'morning-brief.md');
  let shouldRun = true;

  if (fs.existsSync(briefPath)) {
    const stat = fs.statSync(briefPath);
    const ageHours = (Date.now() - stat.mtimeMs) / (1000 * 60 * 60);
    shouldRun = ageHours > 12;
  }

  if (shouldRun) {
    execSync(
      `"${PYTHON}" "${path.join(SCRIPTS, 'scheduled', 'overnight_review.py')}"`,
      { timeout: 20000, stdio: 'ignore' }
    );
  }
} catch (e) {
  // Silent
}
