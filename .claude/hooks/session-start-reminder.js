#!/usr/bin/env node
// Reminds Claude to run session-start if it hasn't been run yet
// Checks for a flag file that gets created after session-start runs

const fs = require('fs');
const path = require('path');
const os = require('os');

let input = '';
const timeout = setTimeout(() => process.exit(0), 3000);
process.stdin.setEncoding('utf8');
process.stdin.on('data', chunk => input += chunk);
process.stdin.on('end', () => {
  clearTimeout(timeout);
  try {
    const data = JSON.parse(input);
    const session = data.session_id || 'unknown';
    const flagFile = path.join(os.tmpdir(), `aios-session-started-${session}`);

    if (!fs.existsSync(flagFile)) {
      // First prompt of session — remind Claude
      process.stdout.write('IMPORTANT: You have NOT run session startup yet. Read and execute skills/session-start/SKILL.md NOW before doing anything else. This loads all context, CARL, skills, leads, calendar, and tools. Do NOT use the Skill tool — read the file directly with the Read tool and follow its instructions.');
      // Create flag so we don't remind again
      fs.writeFileSync(flagFile, Date.now().toString());
    }
    // If flag exists, output nothing (no reminder needed)
  } catch (e) {
    // Silent fail
  }
});
