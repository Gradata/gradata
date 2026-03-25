#!/usr/bin/env node
/**
 * gemini-research.js -- Utility for deep research via Gemini CLI
 * NOT a hook -- called by the orchestrator when research depth is needed.
 * Uses Gemini's 1M context window + free tier for research synthesis.
 *
 * Usage (from other hooks or scripts):
 *   const { geminiResearch } = require('./gemini-research.js');
 *   const result = await geminiResearch("Research topic here", { model: 'gemini-2.5-pro' });
 *
 * Or from CLI:
 *   node gemini-research.js "Research topic here"
 */

const { execSync } = require('child_process');

const DEFAULT_MODEL = 'gemini-2.5-pro';
const TIMEOUT = 120000; // 2 minutes

/**
 * Run a research query through Gemini CLI in headless mode.
 * @param {string} query - The research prompt
 * @param {object} opts - Options: model, timeout, includeFiles
 * @returns {string} Gemini's response text
 */
function geminiResearch(query, opts = {}) {
  const model = opts.model || DEFAULT_MODEL;
  const timeout = opts.timeout || TIMEOUT;

  try {
    // Build command -- -p for headless, --output-format text for clean output
    const cmd = `gemini -p "${query.replace(/"/g, '\\"')}" -m ${model}`;

    const result = execSync(cmd, {
      encoding: 'utf8',
      timeout,
      stdio: ['pipe', 'pipe', 'pipe'],
      maxBuffer: 1024 * 1024 * 5, // 5MB buffer for long responses
    });

    return result.trim();
  } catch (e) {
    return `[gemini-research] Error: ${e.message}`;
  }
}

/**
 * Research with file context -- feeds files into Gemini's 1M context
 * @param {string} query - The research prompt
 * @param {string[]} filePaths - Array of file paths to include as context
 * @returns {string} Gemini's response
 */
function geminiResearchWithFiles(query, filePaths = [], opts = {}) {
  const model = opts.model || DEFAULT_MODEL;
  const timeout = opts.timeout || TIMEOUT;
  const fs = require('fs');

  // Build context from files
  let fileContext = '';
  for (const fp of filePaths) {
    try {
      const content = fs.readFileSync(fp, 'utf8');
      const name = require('path').basename(fp);
      fileContext += `\n--- ${name} ---\n${content}\n`;
    } catch { /* skip unreadable files */ }
  }

  const fullPrompt = fileContext
    ? `${query}\n\nContext files:\n${fileContext}`
    : query;

  return geminiResearch(fullPrompt, { model, timeout });
}

// CLI mode: node gemini-research.js "query"
if (require.main === module) {
  const query = process.argv.slice(2).join(' ');
  if (!query) {
    console.error('Usage: node gemini-research.js "Your research query"');
    process.exit(1);
  }
  const result = geminiResearch(query);
  console.log(result);
}

module.exports = { geminiResearch, geminiResearchWithFiles };
