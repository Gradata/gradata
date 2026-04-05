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
    const sessionId = eventData.session_id || `s_${Date.now()}`;
    const result = await callDaemon('/apply-rules', { prompt: '', session_id: sessionId }, 3000);
    if (!result) {
      process.stderr.write('[gradata] Daemon not available — corrections will not be captured this session\n');
      process.exit(0);
    }
    const rulesCount = (result.rules || []).length;
    if (result.injection_text) process.stdout.write(result.injection_text);
    process.stderr.write(`[gradata] Injecting ${rulesCount} rules\n`);
  } catch (e) {
    process.stderr.write(`[gradata] session-start error: ${e.message}\n`);
  }
})();
