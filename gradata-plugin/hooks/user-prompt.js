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
    const message = eventData.message || eventData.content || '';
    const sessionId = eventData.session_id || '';
    if (!message || message.length < 5) process.exit(0);
    const [rulesResult, detectResult] = await Promise.all([
      callDaemon('/apply-rules', { prompt: message, session_id: sessionId }, 500),
      callDaemon('/detect', { user_message: message, session_id: sessionId }, 500),
    ]);
    if (rulesResult && rulesResult.injection_text) process.stdout.write(rulesResult.injection_text);
  } catch (e) { /* Never block the user's prompt */ }
})();
