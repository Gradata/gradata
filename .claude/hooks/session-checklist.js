#!/usr/bin/env node
/**
 * session-checklist.js — Stop hook
 * Automatically generates the session checklist at session end.
 * Writes gaps to brain/session-gaps.md so next session's startup surfaces them.
 * Silent on failure — never blocks session close.
 */

const { execSync } = require('child_process');
const fs = require('fs');
const cfg = require('./config.js');

try {
  const input = fs.readFileSync(0, 'utf8');
  // Stop hooks get session data on stdin — we just need to fire

  // Run session_checklist.py and write output to brain/session-gaps.md
  const script = `${cfg.SCRIPTS}/session_checklist.py`;
  if (!fs.existsSync(script)) process.exit(0);

  const result = execSync(
    `"${cfg.PYTHON}" "${script}" --json`,
    { encoding: 'utf8', timeout: 10000, stdio: ['pipe', 'pipe', 'pipe'] }
  );

  if (!result || result.trim().length < 10) process.exit(0);

  const items = JSON.parse(result);

  // Count items by urgency
  let todayCount = 0;
  let totalCount = 0;
  for (const cat of Object.values(items)) {
    for (const item of cat) {
      totalCount++;
      if (item.urgency === 'TODAY') todayCount++;
    }
  }

  // Write summary to brain/ for next session startup to read
  const gapsPath = `${cfg.BRAIN_DIR}/session-gaps.md`;
  const lines = [
    `# Session Gaps — auto-generated at session close`,
    `# ${totalCount} items pending | ${todayCount} due today`,
    `# Read by startup Phase 0 to surface what needs attention`,
    '',
  ];

  // Only write TODAY items (startup doesn't need the full list)
  for (const [cat, catItems] of Object.entries(items)) {
    const today = catItems.filter(i => i.urgency === 'TODAY');
    if (today.length === 0) continue;
    lines.push(`## ${cat.toUpperCase()}`);
    for (const item of today) {
      lines.push(`- ${item.item}`);
    }
    lines.push('');
  }

  fs.writeFileSync(gapsPath, lines.join('\n'), 'utf8');

} catch (e) {
  // Silent — never block session close
}
