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
    const toolName = eventData.tool_name || '';
    if (!['Edit', 'Write', 'MultiEdit'].includes(toolName)) process.exit(0);
    const toolInput = eventData.tool_input || {};
    const oldStr = toolInput.old_string || '';
    const newStr = toolInput.new_string || toolInput.content || '';
    const filePath = toolInput.file_path || '';
    const sessionId = eventData.session_id || '';
    if (!oldStr && !newStr) process.exit(0);
    if (oldStr === newStr) process.exit(0);
    await callDaemon('/correct', {
      old_string: oldStr, new_string: newStr,
      file_path: filePath, session_id: sessionId,
    }, 1000);
  } catch (e) { /* Best-effort — never block editing */ }
})();
