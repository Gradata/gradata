#!/usr/bin/env node
const { callDaemon } = require('./lib/daemon-client.js');
(async () => {
  try {
    let input = '';
    if (!process.stdin.isTTY) {
      const fs = require('fs');
      input = fs.readFileSync(0, 'utf8');
    }
    let eventData = {};
    try { eventData = JSON.parse(input); } catch {}
    const sessionId = eventData.session_id || '';
    const result = await callDaemon('/end-session', {
      session_id: sessionId, session_type: 'full',
    }, 10000);
    if (result) {
      const c = result.corrections_captured || 0;
      const i = result.instructions_extracted || 0;
      const g = result.lessons_graduated || 0;
      process.stderr.write(`[gradata] Session end: ${c} corrections, ${i} instructions, ${g} graduated\n`);
      for (const cand of (result.cross_project_candidates || [])) {
        process.stderr.write(`[gradata] Rule '${cand.description}' graduated in ${cand.project_count} projects\n`);
      }
    }
  } catch (e) {
    process.stderr.write(`[gradata] session-stop error: ${e.message}\n`);
  }
})();
