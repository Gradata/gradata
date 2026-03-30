#!/usr/bin/env node
/**
 * behavior-triggers.js — PostToolUse hook
 * Detects behavioral patterns from tool usage and injects skill directives.
 *
 * Unlike skill-router.js (fires on what user SAYS), this fires on what HAPPENED:
 *   - Wrote Python code → suggest code review, TDD, security scan
 *   - Test failed (Bash) → suggest systematic-debugging or focused-fix
 *   - Git commit → suggest dependency-auditor, pr-review-expert
 *   - Created PR → suggest pr-review-expert
 *   - Build failed → suggest focused-fix
 *   - Wrote to brain/prospects/ → suggest verification
 *   - Multiple edits to same file → suggest refactoring
 *   - Wrote SDK code → suggest spec-driven-workflow if no spec exists
 *
 * Stateful: tracks tool calls in a temp file to detect multi-step patterns.
 * Silent on no match. <5ms typical latency.
 */
const fs = require('fs');
const path = require('path');
const os = require('os');

const STATE_FILE = path.join(os.tmpdir(), 'gradata-behavior-state.json');

// Read stdin (PostToolUse hook protocol)
let input = '';
try {
  input = fs.readFileSync(0, 'utf-8');
} catch (e) {
  process.exit(0);
}

let data = {};
try {
  data = JSON.parse(input);
} catch (e) {
  process.exit(0);
}

const toolName = data.tool_name || '';
const toolInput = data.tool_input || {};
const toolOutput = data.tool_output || '';
const toolOutputStr = typeof toolOutput === 'string' ? toolOutput : JSON.stringify(toolOutput);

// ── Load state ─────────────────────────────────────────────────
let state = { edits: {}, writes: [], bashResults: [], sessionTriggers: {} };
try {
  if (fs.existsSync(STATE_FILE)) {
    state = JSON.parse(fs.readFileSync(STATE_FILE, 'utf-8'));
    // Reset if stale (> 2 hours)
    if (state.ts && Date.now() - state.ts > 7200000) {
      state = { edits: {}, writes: [], bashResults: [], sessionTriggers: {} };
    }
  }
} catch (e) { /* fresh state */ }

// ── Track state ────────────────────────────────────────────────
const filePath = toolInput.file_path || toolInput.path || '';

if (toolName === 'Edit' || toolName === 'Write') {
  state.edits[filePath] = (state.edits[filePath] || 0) + 1;
  state.writes.push({ file: filePath, ts: Date.now() });
  // Keep last 50 writes only
  if (state.writes.length > 50) state.writes = state.writes.slice(-50);
}

if (toolName === 'Bash') {
  state.bashResults.push({
    cmd: (toolInput.command || '').substring(0, 200),
    output: toolOutputStr.substring(0, 500),
    ts: Date.now()
  });
  if (state.bashResults.length > 20) state.bashResults = state.bashResults.slice(-20);
}

// ── Trigger rules ──────────────────────────────────────────────
const triggers = [];

// Dedupe: don't fire the same trigger more than once per 10 minutes
function shouldFire(triggerName) {
  const last = state.sessionTriggers[triggerName] || 0;
  if (Date.now() - last < 600000) return false; // 10 min cooldown
  state.sessionTriggers[triggerName] = Date.now();
  return true;
}

// ── RULE 1: Wrote Python code in SDK → code review + test reminder
if ((toolName === 'Write' || toolName === 'Edit') && filePath.includes('sdk/src/')) {
  if (shouldFire('sdk-code-review')) {
    triggers.push('CODE WRITTEN in SDK — consider running code-reviewer-team and checking test coverage');
  }
}

// ── RULE 2: Test failure detected → debugging skill
if (toolName === 'Bash') {
  const out = toolOutputStr.toLowerCase();
  const cmd = (toolInput.command || '').toLowerCase();

  if ((cmd.includes('pytest') || cmd.includes('test')) &&
      (out.includes('failed') || out.includes('error') || out.includes('traceback'))) {
    if (shouldFire('test-failure')) {
      triggers.push('TEST FAILURE detected — load skills/dev/systematic-debugging/SKILL.md for root cause analysis. If multiple modules failing, use skills/dev/focused-fix/SKILL.md instead.');
    }
  }

  // ── RULE 3: Build failure
  if ((cmd.includes('build') || cmd.includes('pip install') || cmd.includes('uv ') || cmd.includes('npm ')) &&
      (out.includes('error') || out.includes('failed'))) {
    if (shouldFire('build-failure')) {
      triggers.push('BUILD FAILURE detected — diagnose before retrying. Check dependency versions and error output.');
    }
  }

  // ── RULE 4: Git commit → remind about PR review and changelog
  if (cmd.includes('git commit')) {
    if (shouldFire('post-commit')) {
      triggers.push('COMMIT made — if ready to merge, use skills/dev/pr-review-expert/SKILL.md for blast radius check. For release prep, use skills/dev/release-manager/SKILL.md.');
    }
  }

  // ── RULE 5: Git push → PR creation reminder
  if (cmd.includes('git push')) {
    if (shouldFire('post-push')) {
      triggers.push('PUSH detected — consider creating a PR with blast radius analysis (skills/dev/pr-review-expert/SKILL.md).');
    }
  }

  // ── RULE 6: gh pr create → adversarial review
  if (cmd.includes('gh pr create') || cmd.includes('gh pr ')) {
    if (shouldFire('pr-created')) {
      triggers.push('PR ACTIVITY — load skills/dev/adversarial-review/SKILL.md for pre-merge debate. Also run skills/dev/pr-review-expert/SKILL.md for structured review.');
    }
  }
}

// ── RULE 7: Wrote to brain/prospects/ → verify accuracy
if ((toolName === 'Write' || toolName === 'Edit') && filePath.includes('brain/prospects/')) {
  if (shouldFire('prospect-update')) {
    triggers.push('PROSPECT NOTE updated — verify contact info, next_touch date, and tags are accurate. Load skills/core/verification-before-completion/SKILL.md.');
  }
}

// ── RULE 8: Multiple edits to same file (3+) → suggest refactoring
if (toolName === 'Edit' && state.edits[filePath] >= 4) {
  if (shouldFire('multi-edit-' + path.basename(filePath))) {
    triggers.push(`FILE CHURN: ${path.basename(filePath)} edited ${state.edits[filePath]} times this session — consider stepping back to refactor holistically rather than incremental patches.`);
  }
}

// ── RULE 9: Wrote hook code → security review
if ((toolName === 'Write' || toolName === 'Edit') && filePath.includes('.claude/hooks/')) {
  if (shouldFire('hook-security')) {
    triggers.push('HOOK MODIFIED — run skills/dev/skill-security-auditor/SKILL.md to verify no config tampering or injection risks.');
  }
}

// ── RULE 10: Wrote CARL rules or CLAUDE.md → self-audit
if ((toolName === 'Write' || toolName === 'Edit') &&
    (filePath.includes('.carl/') || filePath.includes('CLAUDE.md'))) {
  if (shouldFire('carl-modified')) {
    triggers.push('SYSTEM RULES MODIFIED — run skills/core/rule-validator/SKILL.md to check for conflicts. Also verify CLAUDE.md line count stays under 150.');
  }
}

// ── RULE 11: Wrote email draft → adversarial review before sending
if ((toolName === 'Write' || toolName === 'Edit') &&
    (filePath.includes('email') || filePath.includes('draft') || filePath.includes('Demo Prep'))) {
  if (shouldFire('email-draft')) {
    triggers.push('PROSPECT-FACING CONTENT written — load skills/dev/adversarial-review/SKILL.md for CRITIC/DEFENDER debate before sending.');
  }
}

// ── RULE 12: Wrote to pyproject.toml or package.json → dependency check
if ((toolName === 'Write' || toolName === 'Edit') &&
    (filePath.includes('pyproject.toml') || filePath.includes('package.json') || filePath.includes('requirements'))) {
  if (shouldFire('dep-change')) {
    triggers.push('DEPENDENCY FILE changed — run skills/dev/dependency-auditor/SKILL.md to check for license conflicts and vulnerabilities.');
  }
}

// ── RULE 13: Wrote new skill → skill tester
if ((toolName === 'Write' || toolName === 'Edit') && filePath.includes('skills/') && filePath.includes('SKILL.md')) {
  if (shouldFire('skill-written')) {
    triggers.push('SKILL MODIFIED — run skills/dev/skill-tester/SKILL.md to validate structure, and update skill-router.js if new intent patterns needed.');
  }
}

// ── RULE 14: PLAN-FIRST GATE — Any fix/change to core files OR spawning implementation agents
// Oliver corrected 3x in S74: never jump to implementation without planning.
// Applies to: (a) direct edits to core files, (b) spawning agents to fix/build core logic
const CORE_LEARNING_PATHS = [
  'wrap_up.py', 'ablation_test.py', 'ablation_lifecycle.py', 'learning_dashboard.py',
  'capture_learning.py', 'rule_verifier.py', 'meta_rules.py', 'diff_engine.py',
  'self_improvement.py', 'quality_gates.py', 'rule_engine.py',
];
const PLAN_FIRST_MSG =
  'PLAN-FIRST GATE: MANDATORY workflow for ANY suggested fix Oliver approves: ' +
  '(1) Spawn a Plan agent to design the fix approach. ' +
  '(2) Spawn an Adversary agent to attack the plan and find holes. ' +
  '(3) Fix the plan based on adversary findings. ' +
  '(4) ONLY THEN spawn implementation agents or edit code directly. ' +
  'This applies to ALL fixes, not just core files. Oliver corrected this 3x in S74.';

// Gate on direct edits to core files
if ((toolName === 'Write' || toolName === 'Edit') &&
    CORE_LEARNING_PATHS.some(p => filePath.includes(p))) {
  if (shouldFire('plan-first-gate')) {
    triggers.push(PLAN_FIRST_MSG);
  }
}

// Gate on spawning implementation agents (Agent tool) that touch core logic
if (toolName === 'Agent') {
  const agentPrompt = ((data.tool_input || {}).prompt || '').toLowerCase();
  const agentDesc = ((data.tool_input || {}).description || '').toLowerCase();
  const isFix = /\b(fix|implement|build|create|write|refactor|patch|update|change)\b/.test(agentDesc);
  const touchesCore = CORE_LEARNING_PATHS.some(p => agentPrompt.includes(p.replace('.py', '')));
  if (isFix && touchesCore) {
    if (shouldFire('plan-first-agent')) {
      triggers.push(PLAN_FIRST_MSG);
    }
  }
}

// ── Save state ─────────────────────────────────────────────────
state.ts = Date.now();
try {
  fs.writeFileSync(STATE_FILE, JSON.stringify(state));
} catch (e) { /* silent */ }

// ── Output ─────────────────────────────────────────────────────
if (triggers.length > 0) {
  process.stdout.write(JSON.stringify({
    result: triggers.join('\n')
  }));
}
