#!/usr/bin/env node
// Scrapes Claude.ai usage limits via Chrome DevTools Protocol
// Requires Chrome running with --remote-debugging-port=9222
// Writes to ~/.claude/plan-usage.json for the statusline to read
// Usage: node .claude/scripts/update-plan-usage.js

const http = require('http');
const https = require('https');
const fs = require('fs');
const path = require('path');
const os = require('os');
const WebSocket = require('ws') || null;

const OUTPUT = path.join(os.homedir(), '.claude', 'plan-usage.json');
const CDP_PORT = 9222;

function httpGet(url) {
  return new Promise((resolve, reject) => {
    const mod = url.startsWith('https') ? https : http;
    mod.get(url, res => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => resolve(data));
    }).on('error', reject);
  });
}

function cdpSend(ws, method, params = {}) {
  return new Promise((resolve, reject) => {
    const id = Math.floor(Math.random() * 100000);
    const timeout = setTimeout(() => reject(new Error(`CDP timeout: ${method}`)), 15000);
    const handler = (msg) => {
      const data = JSON.parse(msg);
      if (data.id === id) {
        clearTimeout(timeout);
        ws.removeListener('message', handler);
        if (data.error) reject(new Error(data.error.message));
        else resolve(data.result);
      }
    };
    ws.on('message', handler);
    ws.send(JSON.stringify({ id, method, params }));
  });
}

(async () => {
  try {
    // Get list of tabs from Chrome
    const tabsJson = await httpGet(`http://localhost:${CDP_PORT}/json`);
    const tabs = JSON.parse(tabsJson);

    // Find an existing page tab (not devtools, not extension)
    let target = tabs.find(t => t.type === 'page' && t.url.startsWith('http'));
    if (!target) target = tabs.find(t => t.type === 'page');
    if (!target) {
      // Create a new tab
      const newTab = await httpGet(`http://localhost:${CDP_PORT}/json/new?about:blank`);
      target = JSON.parse(newTab);
    }

    console.log(`Connecting to tab: ${target.title || target.url}`);

    // Connect via WebSocket
    const ws = new (require('ws'))(target.webSocketDebuggerUrl);
    await new Promise((resolve, reject) => {
      ws.on('open', resolve);
      ws.on('error', reject);
    });

    // Navigate to usage page
    console.log('Navigating to usage page...');
    await cdpSend(ws, 'Page.navigate', { url: 'https://claude.ai/settings/usage' });

    // Wait for page to fully render (SPA — poll for "% used" text)
    let text = '';
    for (let attempt = 0; attempt < 15; attempt++) {
      await new Promise(r => setTimeout(r, 2000));
      const result = await cdpSend(ws, 'Runtime.evaluate', {
        expression: `document.body.innerText`,
        returnByValue: true
      });
      text = result.result.value || '';
      if (text.includes('% used')) {
        console.log(`Page loaded after ${(attempt + 1) * 2}s`);
        break;
      }
      if (attempt === 14) console.log('Timed out waiting for page content');
    }

    console.log('Page text length:', text.length);

    // Parse usage data
    const usage = { session: null, weekly_all: null, weekly_sonnet: null, updated: new Date().toISOString() };
    const lines = text.split('\n').map(l => l.trim()).filter(Boolean);

    for (let i = 0; i < lines.length; i++) {
      const pctMatch = lines[i].match(/^(\d+)%\s*used$/i);
      if (pctMatch) {
        const pct = parseInt(pctMatch[1]);
        // Look backwards for context
        const context = lines.slice(Math.max(0, i - 6), i).join(' ').toLowerCase();

        if (context.includes('current session')) {
          const resetMatch = context.match(/resets\s+in\s+(.+)/i);
          usage.session = { used_pct: pct, resets_in: resetMatch ? resetMatch[1].trim() : 'unknown' };
          console.log(`  Session: ${pct}% used`);
        } else if (context.includes('sonnet')) {
          const resetMatch = context.match(/resets\s+(\w+\s+\d+:\d+\s*(?:am|pm))/i);
          usage.weekly_sonnet = { used_pct: pct, resets: resetMatch ? resetMatch[1].trim() : 'unknown' };
          console.log(`  Sonnet: ${pct}% used`);
        } else if (context.includes('all models') || context.includes('weekly')) {
          const resetMatch = context.match(/resets\s+(\w+\s+\d+:\d+\s*(?:am|pm))/i);
          usage.weekly_all = { used_pct: pct, resets: resetMatch ? resetMatch[1].trim() : 'unknown' };
          console.log(`  Weekly: ${pct}% used`);
        }
      }
    }

    // Navigate back so the tab isn't stuck on settings
    await cdpSend(ws, 'Page.navigate', { url: 'https://claude.ai' });

    if (usage.session || usage.weekly_all) {
      fs.writeFileSync(OUTPUT, JSON.stringify(usage, null, 2));
      console.log(`\nWritten to ${OUTPUT}`);
      console.log(JSON.stringify(usage, null, 2));
    } else {
      console.log('\nCould not parse usage. Raw text (first 1000 chars):');
      console.log(text.substring(0, 1000));
      // Write debug file
      fs.writeFileSync(OUTPUT + '.debug.txt', text);
    }

    ws.close();
    process.exit(0);
  } catch (err) {
    console.error('Error:', err.message);
    if (err.message.includes('ws')) {
      console.error('\nTip: npm install ws');
    }
    process.exit(1);
  }
})();
