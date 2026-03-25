#!/usr/bin/env node
/**
 * model-router.js -- Smart model routing for multi-LLM workflows
 * Determines which model should handle each task type.
 * Used by the orchestrator and workflow definitions.
 *
 * Usage:
 *   const { routeTask, MODEL } = require('./model-router.js');
 *   const best = routeTask('code-review', { fileCount: 3, linesChanged: 150 });
 *   // returns { model: 'codex', reason: 'Code review: Codex read-only sandbox' }
 */

// ── Model Definitions ──
const MODEL = {
  CLAUDE_OPUS: {
    id: 'claude-opus',
    name: 'Claude Opus 4.6',
    cmd: null, // primary orchestrator, no CLI
    costTier: 'high',
    strengths: ['architecture', 'complex-debug', 'multi-step-reasoning', 'long-context'],
  },
  CLAUDE_SONNET: {
    id: 'claude-sonnet',
    name: 'Claude Sonnet 4.6',
    cmd: null, // primary orchestrator
    costTier: 'medium',
    strengths: ['code-gen', 'email', 'copywriting', 'agentic-tasks', 'code-review'],
  },
  CODEX: {
    id: 'codex',
    name: 'OpenAI Codex CLI',
    cmd: 'codex exec --ephemeral --sandbox read-only',
    costTier: 'medium',
    strengths: ['code-review', 'verification', 'bug-detection', 'security-scan'],
  },
  GEMINI: {
    id: 'gemini',
    name: 'Gemini 2.5 Pro',
    cmd: 'gemini -p',
    costTier: 'free',
    strengths: ['research', 'long-context', 'doc-analysis', 'multimodal', 'synthesis'],
  },
  QWEN: {
    id: 'qwen',
    name: 'Qwen via Ollama',
    cmd: 'ollama run qwen2.5-coder:14b',
    costTier: 'free',
    strengths: ['lint', 'classification', 'batch', 'commit-msg', 'simple-review'],
  },
};

// ── Task Routing Rules ──
// Priority order: best match first. Falls back down the list.
const ROUTING_TABLE = {
  // Code workflows
  'code-gen':        [MODEL.CLAUDE_SONNET],
  'code-review':     [MODEL.CODEX, MODEL.CLAUDE_SONNET],
  'code-lint':       [MODEL.QWEN, MODEL.CODEX],
  'security-scan':   [MODEL.CODEX, MODEL.CLAUDE_SONNET],  // consensus: both
  'architecture':    [MODEL.CLAUDE_OPUS],
  'complex-debug':   [MODEL.CLAUDE_OPUS, MODEL.CLAUDE_SONNET],
  'commit-msg':      [MODEL.QWEN],

  // Research workflows
  'deep-research':   [MODEL.GEMINI, MODEL.CLAUDE_OPUS],
  'web-research':    [MODEL.GEMINI],
  'doc-analysis':    [MODEL.GEMINI],
  'competitor-scan': [MODEL.GEMINI, MODEL.CLAUDE_SONNET],

  // Sales workflows
  'email-draft':     [MODEL.CLAUDE_SONNET],
  'email-review':    [MODEL.GEMINI, MODEL.CLAUDE_SONNET],  // Gemini verifies tone/facts
  'demo-prep':       [MODEL.GEMINI, MODEL.CLAUDE_SONNET],  // Gemini researches, Claude builds
  'prospect-enrich': [MODEL.GEMINI, MODEL.QWEN],           // Gemini deep, Qwen batch
  'campaign-copy':   [MODEL.CLAUDE_SONNET],

  // Utility
  'classification':  [MODEL.QWEN],
  'batch-process':   [MODEL.QWEN],
  'summarize':       [MODEL.QWEN, MODEL.GEMINI],
};

/**
 * Route a task to the best model(s).
 * @param {string} taskType - Key from ROUTING_TABLE
 * @param {object} context - Optional context (fileCount, linesChanged, urgency)
 * @returns {{ primary: object, secondary: object|null, reason: string }}
 */
function routeTask(taskType, context = {}) {
  const models = ROUTING_TABLE[taskType];
  if (!models || models.length === 0) {
    return {
      primary: MODEL.CLAUDE_SONNET,
      secondary: null,
      reason: `Unknown task "${taskType}", defaulting to Claude Sonnet`,
    };
  }

  const primary = models[0];
  const secondary = models.length > 1 ? models[1] : null;

  // Cost-aware escalation: if context suggests high complexity, escalate
  if (context.complexity === 'high' && primary.costTier === 'free') {
    return {
      primary: models.length > 1 ? models[1] : MODEL.CLAUDE_SONNET,
      secondary: primary,
      reason: `High complexity: escalated from ${primary.name} to ${(models[1] || MODEL.CLAUDE_SONNET).name}`,
    };
  }

  return {
    primary,
    secondary,
    reason: `${taskType}: ${primary.name}${secondary ? ` (verified by ${secondary.name})` : ''}`,
  };
}

/**
 * Get the workflow pipeline for a high-level activity.
 * Returns ordered steps with model assignments.
 */
function getWorkflowPipeline(activity) {
  const pipelines = {
    'demo-prep': [
      { step: 1, task: 'crm-pull',        model: MODEL.CLAUDE_SONNET,  desc: 'Pull Apollo contact + Pipedrive deal + brain/prospects/ note' },
      { step: 2, task: 'deep-research',   model: MODEL.GEMINI,         desc: 'Gemini enriches WITH Apollo/Pipedrive data as context (company, news, stack)' },
      { step: 3, task: 'doc-analysis',     model: MODEL.CLAUDE_SONNET,  desc: 'NotebookLM pulls case studies + objection handling for persona' },
      { step: 4, task: 'synthesis',        model: MODEL.CLAUDE_SONNET,  desc: 'SYNTHESIZE: merge Apollo + Gemini + NotebookLM + brain into prioritized brief' },
      { step: 5, task: 'email-draft',      model: MODEL.CLAUDE_SONNET,  desc: 'Build cheat sheet from synthesis brief (not raw sources)' },
      { step: 6, task: 'email-review',     model: MODEL.GEMINI,         desc: 'Gemini verifies final output against raw sources for hallucinations' },
    ],
    'prospecting': [
      { step: 1, task: 'crm-pull',        model: MODEL.CLAUDE_SONNET,  desc: 'Pull Apollo company data + existing brain/prospects/ notes' },
      { step: 2, task: 'deep-research',   model: MODEL.GEMINI,         desc: 'Gemini enriches with ICP fit signals, tech stack, hiring data' },
      { step: 3, task: 'prospect-enrich',  model: MODEL.QWEN,           desc: 'Batch classify/tier leads via Qwen (free, local)' },
      { step: 4, task: 'synthesis',        model: MODEL.CLAUDE_SONNET,  desc: 'SYNTHESIZE: merge Apollo + Gemini into tiered lead brief' },
      { step: 5, task: 'campaign-copy',    model: MODEL.CLAUDE_SONNET,  desc: 'Draft campaign sequence from synthesis (best copy)' },
      { step: 6, task: 'email-review',     model: MODEL.CODEX,          desc: 'Codex reviews sequence for consistency/errors' },
    ],
    'email-outreach': [
      { step: 1, task: 'crm-pull',        model: MODEL.CLAUDE_SONNET,  desc: 'Pull Apollo + Pipedrive + brain/prospects/ + PATTERNS.md' },
      { step: 2, task: 'deep-research',   model: MODEL.GEMINI,         desc: 'Gemini researches prospect WITH contact data as context' },
      { step: 3, task: 'synthesis',        model: MODEL.CLAUDE_SONNET,  desc: 'SYNTHESIZE: merge all sources into personalization brief' },
      { step: 4, task: 'email-draft',      model: MODEL.CLAUDE_SONNET,  desc: 'Draft email from synthesis brief (best tone control)' },
      { step: 5, task: 'email-review',     model: MODEL.GEMINI,         desc: 'Gemini fact-checks claims and personalization' },
    ],
    'code-build': [
      { step: 1, task: 'code-gen',         model: MODEL.CLAUDE_SONNET,  desc: 'Claude generates code (primary)' },
      { step: 2, task: 'code-review',      model: MODEL.CODEX,          desc: 'Codex reviews in read-only sandbox (auto via hook)' },
      { step: 3, task: 'code-lint',        model: MODEL.QWEN,           desc: 'Qwen local lint check (auto via hook, free)' },
      { step: 4, task: 'security-scan',    model: MODEL.CODEX,          desc: 'Codex security scan on final output' },
    ],
    'research': [
      { step: 1, task: 'deep-research',   model: MODEL.GEMINI,         desc: 'Gemini primary research (1M context, free tier)' },
      { step: 2, task: 'web-research',     model: MODEL.GEMINI,         desc: 'Gemini synthesizes multiple sources' },
      { step: 3, task: 'doc-analysis',     model: MODEL.CLAUDE_SONNET,  desc: 'Claude analyzes and structures findings' },
    ],
    'post-demo': [
      { step: 1, task: 'crm-pull',        model: MODEL.CLAUDE_SONNET,  desc: 'Pull Pipedrive deal + brain/prospects/ + Fireflies transcript' },
      { step: 2, task: 'doc-analysis',     model: MODEL.GEMINI,         desc: 'Gemini analyzes full transcript (1M context) WITH deal context' },
      { step: 3, task: 'synthesis',        model: MODEL.CLAUDE_SONNET,  desc: 'SYNTHESIZE: merge transcript analysis + deal data into structured brief' },
      { step: 4, task: 'email-draft',      model: MODEL.CLAUDE_SONNET,  desc: 'Claude writes prospect note update + follow-up from synthesis' },
      { step: 5, task: 'email-review',     model: MODEL.GEMINI,         desc: 'Gemini verifies note accuracy against raw transcript' },
    ],
    'crm-entry': [
      { step: 1, task: 'crm-pull',        model: MODEL.CLAUDE_SONNET,  desc: 'Pull Apollo + any existing brain/prospects/ data' },
      { step: 2, task: 'deep-research',   model: MODEL.GEMINI,         desc: 'Gemini verifies company details WITH Apollo data as input' },
      { step: 3, task: 'synthesis',        model: MODEL.CLAUDE_SONNET,  desc: 'SYNTHESIZE: merge Apollo + Gemini verification into clean note' },
      { step: 4, task: 'email-draft',      model: MODEL.CLAUDE_SONNET,  desc: 'Claude writes/updates brain/prospects/ note from synthesis' },
    ],
    'pre-call': [
      { step: 1, task: 'crm-pull',        model: MODEL.CLAUDE_SONNET,  desc: 'Pull Pipedrive deal + brain/prospects/ + PATTERNS.md history' },
      { step: 2, task: 'deep-research',   model: MODEL.GEMINI,         desc: 'Gemini checks for updates since last contact WITH deal context' },
      { step: 3, task: 'synthesis',        model: MODEL.CLAUDE_SONNET,  desc: 'SYNTHESIZE: merge existing notes + Gemini refresh into call brief' },
      { step: 4, task: 'email-draft',      model: MODEL.CLAUDE_SONNET,  desc: 'Claude builds call prep from synthesis' },
    ],
    'campaign-build': [
      { step: 1, task: 'crm-pull',        model: MODEL.CLAUDE_SONNET,  desc: 'Pull existing Instantly campaigns for style + lead data' },
      { step: 2, task: 'deep-research',   model: MODEL.GEMINI,         desc: 'Gemini researches poster, topic, commenter intent WITH campaign context' },
      { step: 3, task: 'synthesis',        model: MODEL.CLAUDE_SONNET,  desc: 'SYNTHESIZE: merge campaign style + Gemini research into sequence brief' },
      { step: 4, task: 'campaign-copy',    model: MODEL.CLAUDE_SONNET,  desc: 'Claude drafts the sequence from synthesis (best copy/tone)' },
      { step: 5, task: 'email-review',     model: MODEL.CODEX,          desc: 'Codex reviews for consistency and personalization errors' },
    ],
  };

  return pipelines[activity] || null;
}

// CLI mode: node model-router.js <task-type>
if (require.main === module) {
  const task = process.argv[2];
  if (!task) {
    console.log('Available task types:', Object.keys(ROUTING_TABLE).join(', '));
    console.log('\nWorkflow pipelines:', Object.keys({
      'demo-prep': 1, 'prospecting': 1, 'email-outreach': 1, 'code-build': 1, 'research': 1,
    }).join(', '));
    console.log('\nUsage: node model-router.js <task-type|workflow-name>');
    process.exit(0);
  }

  // Try as workflow first, then as task
  const pipeline = getWorkflowPipeline(task);
  if (pipeline) {
    console.log(`\nWorkflow: ${task}`);
    console.log('='.repeat(60));
    for (const step of pipeline) {
      console.log(`  Step ${step.step}: [${step.model.name}] ${step.desc}`);
    }
  } else {
    const route = routeTask(task);
    console.log(`Task: ${task}`);
    console.log(`  Primary: ${route.primary.name}`);
    if (route.secondary) console.log(`  Secondary: ${route.secondary.name}`);
    console.log(`  Reason: ${route.reason}`);
  }
}

module.exports = { routeTask, getWorkflowPipeline, MODEL, ROUTING_TABLE };
