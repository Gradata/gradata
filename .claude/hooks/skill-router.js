#!/usr/bin/env node
/**
 * skill-router.js — UserPromptSubmit hook
 * Pattern-matches user intent against installed skills and injects
 * "SKILL MATCH" directives so the AI loads the right skill BEFORE responding.
 *
 * Two-tier matching:
 *   1. Keyword match (fast, covers explicit triggers)
 *   2. Semantic intent match (catches indirect references)
 *
 * Silent on no match. Never blocks. <3ms latency.
 */

let input = '';
try {
  input = require('fs').readFileSync(0, 'utf-8');
} catch (e) {
  process.exit(0);
}

let message = '';
try {
  const parsed = JSON.parse(input);
  message = (parsed.message || parsed.prompt || parsed.content || '').toLowerCase();
} catch (e) {
  message = input.trim().toLowerCase();
}

if (!message || message.length < 5 || message.startsWith('/')) {
  process.exit(0);
}

// ── Skill routing table ──────────────────────────────────────────
// Each entry: { skill, path, keywords (exact match), intents (semantic patterns) }
// Keywords = fast substring check. Intents = regex for broader coverage.
const SKILLS = [
  // ── Engineering workflow ──
  {
    skill: 'agent-workflow-designer',
    path: 'skills/agent-workflow-designer/SKILL.md',
    keywords: ['agent workflow', 'multi-agent', 'orchestration pattern', 'agent architecture', 'design agents'],
    intents: [
      /how should (the |these |I )?agents? (work|coordinate|hand.?off)/i,
      /which (agent |orchestration )?pattern/i,
      /sequential.*(parallel|router|orchestrator)/i,
      /design.*(agent|workflow|pipeline)/i,
      /agent.*(design|scaffold|architect)/i,
    ],
  },
  {
    skill: 'spec-driven-workflow',
    path: 'skills/spec-driven-workflow/SKILL.md',
    keywords: ['write a spec', 'spec first', 'specification', 'requirements doc', 'acceptance criteria', 'functional req'],
    intents: [
      /write.*(spec|specification|requirements)/i,
      /spec.*(before|first|driven)/i,
      /(acceptance|functional).*(criteria|requirements)/i,
      /RFC.?2119/i,
      /given.?when.?then/i,
    ],
  },
  {
    skill: 'focused-fix',
    path: 'skills/focused-fix/SKILL.md',
    keywords: ['focused fix', 'module broken', 'whole feature', 'deep fix', 'feature repair'],
    intents: [
      /(whole|entire|full) (\w+ )?(module|feature|system).*(broken|failing|busted)/i,
      /nothing.*(work|function)s? (in|for|with)/i,
      /everything.*(broken|failing)/i,
      /deep.*(fix|repair|debug)/i,
      /trace.*(depend|upstream|downstream)/i,
    ],
  },
  {
    skill: 'pr-review-expert',
    path: 'skills/pr-review-expert/SKILL.md',
    keywords: ['pr review', 'pull request review', 'review this pr', 'blast radius', 'review the pr'],
    intents: [
      /review.*(pr|pull request|merge request)/i,
      /(pr|pull request).*(review|check|audit)/i,
      /blast.?radius/i,
      /breaking.?change/i,
      /what.*(break|impact|affect).*merg/i,
    ],
  },
  {
    skill: 'code-reviewer-team',
    path: 'skills/code-reviewer-team/SKILL.md',
    keywords: ['code quality', 'quality scan', 'code review', 'solid violations', 'complexity score', 'code audit'],
    intents: [
      /code.*(quality|review|audit|scan)/i,
      /(cyclomatic|cognitive).?complexity/i,
      /SOLID.*(violation|principle)/i,
      /god.?class/i,
      /secret.*(detect|scan|leak)/i,
      /scan.*(code|codebase|repo)/i,
    ],
  },
  {
    skill: 'self-improving-agent',
    path: 'skills/self-improving-agent/SKILL.md',
    keywords: ['memory review', 'prune memory', 'promote memory', 'memory health', 'curate memory', 'clean memory'],
    intents: [
      /(review|prune|clean|curate|audit).*(memory|memories|MEMORY)/i,
      /memory.*(stale|bloat|health|prune|promote)/i,
      /graduate.*(memory|pattern|lesson)/i,
      /too many memor/i,
    ],
  },
  {
    skill: 'mcp-server-builder',
    path: 'skills/mcp-server-builder/SKILL.md',
    keywords: ['mcp server', 'build mcp', 'create mcp', 'mcp tool', 'openapi to mcp'],
    intents: [
      /(build|create|scaffold|generate).*(mcp|tool server)/i,
      /mcp.*(server|builder|scaffold|tool)/i,
      /openapi.*(mcp|convert|tool)/i,
      /expose.*as.*(mcp|tool)/i,
    ],
  },
  {
    skill: 'dependency-auditor',
    path: 'skills/dependency-auditor/SKILL.md',
    keywords: ['dependency audit', 'license check', 'cve scan', 'vulnerability scan', 'outdated dep', 'license compliance'],
    intents: [
      /(audit|check|scan).*(dep|package|librar)/i,
      /(dep|package|librar).*(audit|check|scan|outdated|vulnerable)/i,
      /license.*(compliance|check|audit|GPL|AGPL)/i,
      /(CVE|vulnerability|vuln).*(scan|check|audit)/i,
      /unused.*(dep|package)/i,
    ],
  },
  {
    skill: 'release-manager',
    path: 'skills/release-manager/SKILL.md',
    keywords: ['release', 'changelog', 'semver', 'version bump', 'cut a release', 'release branch', 'rollback plan'],
    intents: [
      /(cut|prepare|plan|create).*(release|version)/i,
      /(release|version).*(bump|cut|plan|prepare|branch)/i,
      /changelog/i,
      /sem(antic)?.?ver/i,
      /rollback.?(plan|strategy)/i,
      /hotfix.*(branch|release|deploy)/i,
    ],
  },
  {
    skill: 'tech-debt-tracker',
    path: 'skills/tech-debt-tracker/SKILL.md',
    keywords: ['tech debt', 'technical debt', 'debt scan', 'debt tracker', 'debt dashboard'],
    intents: [
      /tech(nical)?.?debt/i,
      /debt.*(scan|track|priorit|dashboard)/i,
      /cost.?of.?delay/i,
      /(code|architecture).*(rot|decay|smell)/i,
      /what.*(needs|should).*(refactor|clean)/i,
    ],
  },
  {
    skill: 'competitive-teardown',
    path: 'skills/competitive-teardown/SKILL.md',
    keywords: ['competitive teardown', 'competitor analysis', 'competitive analysis', 'teardown', 'versus', 'compare against'],
    intents: [
      /(competitive|competitor).*(teardown|analysis|research|compare)/i,
      /tear.?down.*(compet|product|app)/i,
      /how (does|do).*(compare|stack up|differ)/i,
      /(vs|versus|compared to).*(competitor|rival|alternative)/i,
      /what.*(better|worse|different).*(than|from)/i,
    ],
  },
  {
    skill: 'experiment-designer',
    path: 'skills/experiment-designer/SKILL.md',
    keywords: ['experiment design', 'hypothesis', 'a/b test design', 'sample size', 'experiment plan', 'test design'],
    intents: [
      /(design|plan|set up).*(experiment|test|trial)/i,
      /hypothesis/i,
      /sample.?size/i,
      /(minimum|min).?detectable.?effect/i,
      /statistical.*(significance|power)/i,
      /if.?then.?because/i,
      /ICE.?scor/i,
    ],
  },
  {
    skill: 'product-discovery',
    path: 'skills/product-discovery/SKILL.md',
    keywords: ['product discovery', 'opportunity solution tree', 'assumption map', 'discovery sprint', 'user research'],
    intents: [
      /product.?discovery/i,
      /opportunity.?solution.?tree/i,
      /assumption.?(map|test|valid)/i,
      /discovery.?sprint/i,
      /(desirability|viability|feasibility).*(test|valid|assum)/i,
      /should (we|I) build/i,
      /validate.*(idea|concept|product|feature)/i,
    ],
  },
  // ── Prompt engineering (installed earlier) ──
  {
    skill: 'prompt-master',
    path: 'skills/prompt-master/SKILL.md',
    keywords: ['write a prompt', 'prompt for', 'optimize prompt', 'cursor prompt', 'midjourney prompt', 'image prompt', 'agent prompt'],
    intents: [
      /(write|create|make|build|craft|generate).*(prompt)/i,
      /prompt.*(for|optimize|fix|improve|adapt)/i,
      /(cursor|midjourney|dall.?e|stable diffusion|copilot|chatgpt|gpt|gemini|v0|bolt|devin).*(prompt)/i,
    ],
  },

  // ── Engineering (batch 2) ──────────────────────────────────────
  {
    skill: 'agenthub',
    path: 'skills/agenthub/SKILL.md',
    keywords: ['agenthub', 'multi-agent competition', 'worktree isolation', 'competitive agents', 'agent arena'],
    intents: [
      /compet.*(agent|solution|approach)/i,
      /multiple agents?.*(compet|race|compare)/i,
      /worktree.*(isol|agent|parallel)/i,
      /agent.*(hub|arena|tournament)/i,
    ],
  },
  {
    skill: 'api-design-reviewer',
    path: 'skills/api-design-reviewer/SKILL.md',
    keywords: ['api design review', 'api review', 'review api', 'api standards', 'rest api design'],
    intents: [
      /review.*(api|endpoint|route)/i,
      /api.*(design|review|standard|convention)/i,
      /(rest|graphql|grpc).*(design|review|best practice)/i,
      /endpoint.*(naming|design|convention)/i,
    ],
  },
  {
    skill: 'ci-cd-pipeline-builder',
    path: 'skills/ci-cd-pipeline-builder/SKILL.md',
    keywords: ['ci/cd', 'ci cd', 'pipeline builder', 'github actions', 'deployment pipeline'],
    intents: [
      /(build|create|design|set up).*(ci|cd|pipeline|deploy)/i,
      /(ci|cd|pipeline).*(build|create|design|set up)/i,
      /github.?actions?.*(workflow|pipeline)/i,
      /continuous.*(integration|delivery|deployment)/i,
    ],
  },
  {
    skill: 'codebase-onboarding',
    path: 'skills/codebase-onboarding/SKILL.md',
    keywords: ['codebase onboarding', 'onboarding docs', 'codebase guide', 'developer onboarding', 'code walkthrough'],
    intents: [
      /(generate|create|write).*(onboarding|walkthrough)/i,
      /onboard.*(new|developer|engineer|contributor)/i,
      /codebase.*(tour|guide|overview|onboard)/i,
      /how does this (codebase|repo|project) work/i,
    ],
  },
  {
    skill: 'migration-architect',
    path: 'skills/migration-architect/SKILL.md',
    keywords: ['migration plan', 'database migration', 'system migration', 'migration architect', 'migrate from'],
    intents: [
      /(plan|design|architect).*(migration|migrate)/i,
      /migrat.*(database|system|platform|service|schema)/i,
      /(database|system|platform).*(migrat|move|transition)/i,
      /switch.*(from|to).*(database|platform|provider)/i,
    ],
  },
  {
    skill: 'observability-designer',
    path: 'skills/observability-designer/SKILL.md',
    keywords: ['observability', 'monitoring design', 'alerting design', 'dashboard design', 'logging strategy'],
    intents: [
      /(design|plan|set up).*(monitoring|alerting|observability|dashboard)/i,
      /observability.*(design|stack|strategy|plan)/i,
      /(SLO|SLI|SLA|error budget)/i,
      /what should (we|I) (monitor|alert|track|measure)/i,
    ],
  },
  {
    skill: 'skill-security-auditor',
    path: 'skills/skill-security-auditor/SKILL.md',
    keywords: ['skill security audit', 'audit skill security', 'skill permissions', 'skill safety', 'skill audit'],
    intents: [
      /audit.*(skill|hook).*(security|permission|safety)/i,
      /skill.*(security|safe|permiss|audit)/i,
      /(security|safety).*(audit|check).*(skill|hook)/i,
    ],
  },
  {
    skill: 'skill-tester',
    path: 'skills/skill-tester/SKILL.md',
    keywords: ['test skill', 'skill test', 'skill quality', 'validate skill', 'skill validation'],
    intents: [
      /test.*(skill|hook)/i,
      /skill.*(test|quality|valid|check)/i,
      /(quality|valid).*(check|test).*(skill)/i,
    ],
  },
  {
    skill: 'playwright-pro',
    path: 'skills/playwright-pro/SKILL.md',
    keywords: ['playwright test', 'playwright pro', 'e2e test', 'end to end test', 'browser automation'],
    intents: [
      /playwright.*(test|automat|script|advanced)/i,
      /(e2e|end.to.end|browser).*(test|automat)/i,
      /automate.*(browser|ui|web|page)/i,
      /test.*(browser|ui|web page|e2e)/i,
    ],
  },
  {
    skill: 'security-pen-testing',
    path: 'skills/security-pen-testing/SKILL.md',
    keywords: ['pen test', 'penetration test', 'security test', 'vulnerability assessment', 'pentest'],
    intents: [
      /pen(etration)?.?test/i,
      /(security|vuln).*(test|assess|audit|scan)/i,
      /OWASP.*(test|scan|check)/i,
      /find.*(vulnerabil|exploit|weakness)/i,
    ],
  },
  {
    skill: 'senior-architect',
    path: 'skills/senior-architect/SKILL.md',
    keywords: ['architecture decision', 'adr', 'system design', 'architecture review', 'technical architecture'],
    intents: [
      /architect.*(decision|review|design|pattern)/i,
      /(system|software|technical).*(design|architecture)/i,
      /ADR/i,
      /how should (we|I) (architect|structure|design) (the|this)/i,
    ],
  },
  {
    skill: 'tdd-guide',
    path: 'skills/tdd-guide/SKILL.md',
    keywords: ['tdd', 'test driven', 'red green refactor', 'test first', 'write tests first'],
    intents: [
      /test.?driven.?(dev|design)/i,
      /red.?green.?refactor/i,
      /write.*(test|spec).*(first|before)/i,
      /TDD/i,
    ],
  },

  // ── Sales / Marketing (batch 2) ───────────────────────────────
  {
    skill: 'content-creator',
    path: 'skills/content-creator/SKILL.md',
    keywords: ['create content', 'content creation', 'write content', 'blog post', 'article draft'],
    intents: [
      /(create|write|draft|generate).*(content|blog|article|post)/i,
      /content.*(create|creat|write|draft)/i,
      /(blog|article|post).*(write|draft|create)/i,
    ],
  },
  {
    skill: 'content-humanizer',
    path: 'skills/content-humanizer/SKILL.md',
    keywords: ['humanize content', 'remove ai patterns', 'sound human', 'ai detection', 'content humanizer'],
    intents: [
      /humaniz.*(content|text|writing|copy)/i,
      /(sound|read|feel).*(human|natural|authentic)/i,
      /(remove|strip|fix).*(ai|robot|generic).*(pattern|tone|voice)/i,
      /ai.?(detect|written|generat).*(fix|remove|avoid)/i,
    ],
  },
  {
    skill: 'campaign-analytics',
    path: 'skills/campaign-analytics/SKILL.md',
    keywords: ['campaign analytics', 'campaign performance', 'campaign metrics', 'campaign report', 'campaign results'],
    intents: [
      /campaign.*(analyt|perform|metric|report|result|data)/i,
      /analyz.*(campaign|outreach|email blast)/i,
      /how (did|is|are).*(campaign|outreach).*(perform|do|go)/i,
    ],
  },
  {
    skill: 'brand-guidelines',
    path: 'skills/brand-guidelines/SKILL.md',
    keywords: ['brand guidelines', 'brand consistency', 'brand voice', 'brand style', 'brand guide'],
    intents: [
      /brand.*(guideline|consisten|voice|style|guide|standard)/i,
      /(guideline|standard|consisten).*(brand)/i,
      /on.?brand/i,
      /brand.*(tone|identity|message)/i,
    ],
  },
  {
    skill: 'content-production',
    path: 'skills/content-production/SKILL.md',
    keywords: ['content pipeline', 'content production', 'content calendar', 'editorial calendar', 'content workflow'],
    intents: [
      /content.*(pipeline|production|calendar|workflow|schedule)/i,
      /(editorial|content).?calendar/i,
      /(plan|manage|schedule).*(content|editorial)/i,
    ],
  },
  {
    skill: 'marketing-ops',
    path: 'skills/marketing-ops/SKILL.md',
    keywords: ['marketing ops', 'marketing operations', 'martech', 'marketing stack', 'marketing automation'],
    intents: [
      /market.*(ops|operation|automat|stack)/i,
      /martech/i,
      /(set up|configure|optimize).*(marketing|martech|hubspot|mailchimp)/i,
      /marketing.*(tool|platform|integration)/i,
    ],
  },

  // ── Compliance / Quality (batch 2) ────────────────────────────
  {
    skill: 'soc2-compliance',
    path: 'skills/soc2-compliance/SKILL.md',
    keywords: ['soc2', 'soc 2', 'soc2 compliance', 'trust service criteria', 'soc audit'],
    intents: [
      /soc.?2/i,
      /trust.?service.?criteria/i,
      /compliance.*(audit|check|ready|prep)/i,
      /(audit|compliance).*(soc|security|control)/i,
    ],
  },
  {
    skill: 'gdpr-dsgvo-expert',
    path: 'skills/gdpr-dsgvo-expert/SKILL.md',
    keywords: ['gdpr', 'dsgvo', 'data privacy', 'data protection', 'privacy compliance'],
    intents: [
      /GDPR|DSGVO/i,
      /data.*(privacy|protection|subject|processor)/i,
      /privacy.*(compliance|policy|impact|assess)/i,
      /(right to|data).*(erasure|forget|portab|access request)/i,
    ],
  },
  {
    skill: 'risk-management-specialist',
    path: 'skills/risk-management-specialist/SKILL.md',
    keywords: ['risk assessment', 'risk management', 'risk matrix', 'risk register', 'risk mitigation'],
    intents: [
      /risk.*(assess|manag|matrix|register|mitigat|analys)/i,
      /(assess|analyz|identify|mitigat).*(risk)/i,
      /what (could|can|might) go wrong/i,
      /risk.*(score|priorit|rank)/i,
    ],
  },

  // ── Product (batch 2) ─────────────────────────────────────────
  {
    skill: 'agile-product-owner',
    path: 'skills/agile-product-owner/SKILL.md',
    keywords: ['product owner', 'user stories', 'backlog grooming', 'sprint planning', 'agile po'],
    intents: [
      /product.?owner/i,
      /user.?stor(y|ies)/i,
      /backlog.*(groom|refin|priorit)/i,
      /sprint.*(plan|review|retro)/i,
      /(write|create|draft).*(user stor|epic|backlog)/i,
    ],
  },
  {
    skill: 'code-to-prd',
    path: 'skills/code-to-prd/SKILL.md',
    keywords: ['code to prd', 'reverse engineer prd', 'generate prd', 'prd from code', 'product requirements'],
    intents: [
      /reverse.?engineer.*(prd|spec|requirement)/i,
      /(generate|create|write).*(prd|product requirement)/i,
      /prd.*(from|based on).*(code|codebase|repo)/i,
      /what does this (code|system|app) do/i,
    ],
  },
  {
    skill: 'product-analytics',
    path: 'skills/product-analytics/SKILL.md',
    keywords: ['product analytics', 'product metrics', 'retention analysis', 'funnel analysis', 'cohort analysis'],
    intents: [
      /product.*(analytic|metric|data|insight)/i,
      /(retention|funnel|cohort|churn).*(analys|metric)/i,
      /(analyz|track|measure).*(product|feature|usage)/i,
      /(DAU|MAU|WAU|NPS|CSAT|activation rate)/i,
    ],
  },
  {
    skill: 'product-strategist',
    path: 'skills/product-strategist/SKILL.md',
    keywords: ['product strategy', 'product roadmap', 'product vision', 'product positioning', 'go to market'],
    intents: [
      /product.*(strategy|roadmap|vision|position|direction)/i,
      /(roadmap|strategy|vision).*(product|feature)/i,
      /go.?to.?market/i,
      /product.*(market|fit|pmf)/i,
    ],
  },
  {
    skill: 'ux-researcher-designer',
    path: 'skills/ux-researcher-designer/SKILL.md',
    keywords: ['ux research', 'ux design', 'user research', 'usability test', 'wireframe'],
    intents: [
      /ux.*(research|design|audit|review)/i,
      /user.*(research|interview|testing|journey)/i,
      /usability.*(test|study|review)/i,
      /(wireframe|prototype|mockup|user flow)/i,
    ],
  },

  // ── Finance / PM (batch 2) ────────────────────────────────────
  {
    skill: 'financial-analyst',
    path: 'skills/financial-analyst/SKILL.md',
    keywords: ['financial model', 'financial analysis', 'revenue model', 'unit economics', 'financial forecast'],
    intents: [
      /financial.*(model|analys|forecast|project|plan)/i,
      /(revenue|cost|profit|margin).*(model|analys|forecast)/i,
      /unit.?economics/i,
      /(burn rate|runway|cash flow|p&l|balance sheet)/i,
    ],
  },
  {
    skill: 'saas-metrics-coach',
    path: 'skills/saas-metrics-coach/SKILL.md',
    keywords: ['saas metrics', 'mrr', 'arr', 'churn rate', 'ltv cac', 'saas kpi'],
    intents: [
      /saas.*(metric|kpi|benchmark|health)/i,
      /(MRR|ARR|LTV|CAC|NRR|GRR)/i,
      /churn.*(rate|analys|reduc)/i,
      /(ltv|lifetime value).*(cac|acquisition cost)/i,
    ],
  },
  {
    skill: 'senior-pm',
    path: 'skills/senior-pm/SKILL.md',
    keywords: ['project management', 'project plan', 'gantt chart', 'project timeline', 'milestone planning'],
    intents: [
      /project.*(manag|plan|timeline|milestone|schedule)/i,
      /(manage|plan|track|schedule).*(project|deliverable|milestone)/i,
      /gantt/i,
      /(RACI|stakeholder|status report|standup)/i,
    ],
  },
  {
    skill: 'scrum-master',
    path: 'skills/scrum-master/SKILL.md',
    keywords: ['scrum master', 'scrum ceremony', 'daily standup', 'retrospective', 'sprint velocity'],
    intents: [
      /scrum.*(master|ceremony|process|framework)/i,
      /(daily|standup|retro|retrospective|sprint review)/i,
      /sprint.*(velocity|burndown|board)/i,
      /(impediment|blocker).*(remove|clear|resolv)/i,
    ],
  },

  // ── Previously unrouted (from original install) ───────────────
  {
    skill: 'adversarial-review',
    path: 'skills/adversarial-review/SKILL.md',
    keywords: ['adversarial review', 'critic defender', 'devil advocate', 'stress test idea', 'challenge this'],
    intents: [
      /(adversarial|critic|challenge|stress.?test).*(review|idea|plan|proposal)/i,
      /devil.?s?.?advocate/i,
      /poke holes/i,
      /what.*(wrong|weak|flaw).*(with|about|in) (this|my|the)/i,
    ],
  },
  {
    skill: 'systematic-debugging',
    path: 'skills/systematic-debugging/SKILL.md',
    keywords: ['systematic debug', 'root cause analysis', 'debug this', 'why is this failing', 'trace the bug'],
    intents: [
      /systematic.*(debug|diagnos|troubleshoot)/i,
      /root.?cause.*(analy|find|identif)/i,
      /why (is|does|did) (this|it).*(fail|crash|break|error|hang)/i,
      /trace.*(bug|error|failure|crash)/i,
    ],
  },
  {
    skill: 'verification-before-completion',
    path: 'skills/verification-before-completion/SKILL.md',
    keywords: ['verify before done', 'verification checklist', 'pre-completion check', 'done checklist', 'verify completion'],
    intents: [
      /verif.*(before|prior|completion|done|ship)/i,
      /(check|verify|confirm).*(done|complete|ready|ship)/i,
      /are (we|you) (actually|really) done/i,
      /definition of done/i,
    ],
  },

  // ── Remaining skills (full coverage) ─────────────────────────
  {
    skill: 'ab-test-setup',
    path: 'skills/ab-test-setup/SKILL.md',
    keywords: ['a/b test', 'ab test', 'split test', 'test setup', 'variant test'],
    intents: [/(a.?b|split|variant).?test/i, /(set up|design|plan).*(test|experiment)/i],
  },
  {
    skill: 'ad-creative',
    path: 'skills/ad-creative/SKILL.md',
    keywords: ['ad creative', 'ad copy', 'ad design', 'creative brief', 'ad variations'],
    intents: [/(ad|creative|banner).*(copy|design|variation|brief)/i, /(write|create|generate).*(ad|creative|banner)/i],
  },
  {
    skill: 'agent-scaffold',
    path: 'skills/agent-scaffold/SKILL.md',
    keywords: ['scaffold agent', 'new agent', 'create agent', 'agent template'],
    intents: [/(scaffold|create|build|generate).*(agent|bot)/i, /agent.*(scaffold|template|boilerplate)/i],
  },
  {
    skill: 'ai-seo',
    path: 'skills/ai-seo/SKILL.md',
    keywords: ['ai seo', 'llm seo', 'ai search optimization', 'get cited by ai'],
    intents: [/ai.*(seo|search|citation)/i, /(optimize|rank).*(ai|llm|chatgpt|perplexity)/i],
  },
  {
    skill: 'analytics-tracking',
    path: 'skills/analytics-tracking/SKILL.md',
    keywords: ['analytics tracking', 'tracking setup', 'gtm', 'google analytics', 'event tracking'],
    intents: [/(set up|implement|audit).*(analytics|tracking|gtm|ga4)/i, /tracking.*(plan|setup|audit|implement)/i],
  },
  {
    skill: 'brainstorming',
    path: 'skills/brainstorming/SKILL.md',
    keywords: ['brainstorm', 'ideate', 'creative ideas', 'idea generation'],
    intents: [/brainstorm/i, /(generate|come up with|think of).*(idea|concept|approach)/i],
  },
  {
    skill: 'business-growth',
    path: 'skills/business-growth/SKILL.md',
    keywords: ['business growth', 'growth strategy', 'revenue growth', 'customer success'],
    intents: [/(business|revenue|customer).*(growth|scale|expand)/i, /growth.*(strategy|plan|lever)/i],
  },
  {
    skill: 'buyer-psychology',
    path: 'skills/buyer-psychology/SKILL.md',
    keywords: ['buyer psychology', 'buying behavior', 'purchase decision', 'buyer motivation'],
    intents: [/buyer.*(psychology|behavior|motivation|decision)/i, /(why|how) (do |does )?(buyer|customer|prospect)s? (buy|decide|choose)/i],
  },
  {
    skill: 'churn-prevention',
    path: 'skills/churn-prevention/SKILL.md',
    keywords: ['churn prevention', 'reduce churn', 'retention', 'cancel flow', 'save offer'],
    intents: [/churn.*(prevent|reduc|stop)/i, /(retention|cancel|save).*(flow|offer|strategy)/i],
  },
  {
    skill: 'c-level-advisor',
    path: 'skills/c-level-advisor/SKILL.md',
    keywords: ['c-level', 'ceo advisor', 'cto advisor', 'cfo advisor', 'executive advisor', 'board meeting'],
    intents: [/(ceo|cto|cfo|cmo|coo|ciso|cro|cpo).*(advi|counsel|perspective)/i, /(executive|board|c.level).*(advi|meeting|decision)/i],
  },
  {
    skill: 'cold-email',
    path: 'skills/cold-email/SKILL.md',
    keywords: ['cold email', 'outreach email', 'prospecting email', 'cold outreach'],
    intents: [/cold.*(email|outreach)/i, /(write|draft|send).*(cold|outreach|prospect).*(email|message)/i],
  },
  {
    skill: 'cold-email-manifesto',
    path: 'skills/cold-email-manifesto/SKILL.md',
    keywords: ['email manifesto', 'cold email framework', 'email conversion'],
    intents: [/cold email.*(framework|method|manifesto|system)/i],
  },
  {
    skill: 'competitor-alternatives',
    path: 'skills/competitor-alternatives/SKILL.md',
    keywords: ['competitor page', 'alternatives page', 'versus page', 'comparison page'],
    intents: [/(competitor|alternative|versus|comparison).*(page|landing|seo)/i],
  },
  {
    skill: 'competitor-research',
    path: 'skills/competitor-research/SKILL.md',
    keywords: ['competitor research', 'research competitor', 'competitive intel'],
    intents: [/research.*(competitor|competition)/i, /(competitor|competitive).*(research|intel|brief)/i],
  },
  {
    skill: 'content-strategy',
    path: 'skills/content-strategy/SKILL.md',
    keywords: ['content strategy', 'content plan', 'content calendar', 'editorial calendar'],
    intents: [/content.*(strategy|plan|calendar|roadmap)/i, /(plan|strategy).*(content|editorial|blog)/i],
  },
  {
    skill: 'copy-editing',
    path: 'skills/copy-editing/SKILL.md',
    keywords: ['copy edit', 'edit copy', 'proofread', 'improve copy', 'review copy'],
    intents: [/(edit|improve|review|proofread).*(copy|text|writing|content)/i, /copy.*(edit|review|improve)/i],
  },
  {
    skill: 'copywriting',
    path: 'skills/copywriting/SKILL.md',
    keywords: ['copywriting', 'write copy', 'marketing copy', 'landing page copy', 'headline'],
    intents: [/(write|create|improve).*(copy|headline|tagline|slogan)/i, /copywriting/i],
  },
  {
    skill: 'dispatching-parallel-agents',
    path: 'skills/dispatching-parallel-agents/SKILL.md',
    keywords: ['dispatch agents', 'parallel agents', 'run agents in parallel'],
    intents: [/dispatch.*(agent|task|parallel)/i, /parallel.*(agent|dispatch|run)/i],
  },
  {
    skill: 'email-sequence',
    path: 'skills/email-sequence/SKILL.md',
    keywords: ['email sequence', 'drip campaign', 'email series', 'nurture sequence'],
    intents: [/(email|drip|nurture).*(sequence|series|campaign|flow)/i],
  },
  {
    skill: 'enrich',
    path: 'skills/enrich/SKILL.md',
    keywords: ['enrich lead', 'enrich contact', 'find email', 'verify email', 'prospeo', 'zerobounce'],
    intents: [/enrich.*(lead|contact|email|data)/i, /(find|verify|validate).*(email|phone|contact)/i],
  },
  {
    skill: 'executing-plans',
    path: 'skills/executing-plans/SKILL.md',
    keywords: ['execute plan', 'follow plan', 'run the plan'],
    intents: [/execut.*(plan|spec|task)/i, /(follow|implement|run).*(plan|spec)/i],
  },
  {
    skill: 'fanatical-prospecting',
    path: 'skills/fanatical-prospecting/SKILL.md',
    keywords: ['fanatical prospecting', 'prospecting discipline', 'outbound discipline'],
    intents: [/fanatical.*(prospect)/i, /prospect.*(discipline|framework|method)/i],
  },
  {
    skill: 'finishing-a-development-branch',
    path: 'skills/finishing-a-development-branch/SKILL.md',
    keywords: ['finish branch', 'merge branch', 'branch done', 'ready to merge'],
    intents: [/(finish|complete|done with).*(branch|feature)/i, /ready to merge/i],
  },
  {
    skill: 'fitfo',
    path: 'skills/fitfo/SKILL.md',
    keywords: ['fitfo', 'stuck', 'figure it out', 'blocked'],
    intents: [/(stuck|blocked|can.?t figure)/i, /how (do|can) (I|we) (fix|solve|figure)/i],
  },
  {
    skill: 'form-cro',
    path: 'skills/form-cro/SKILL.md',
    keywords: ['form optimization', 'form cro', 'optimize form', 'form conversion'],
    intents: [/(optimize|improve|fix).*(form|input|field)/i, /form.*(conversion|optimization|cro)/i],
  },
  {
    skill: 'free-tool-strategy',
    path: 'skills/free-tool-strategy/SKILL.md',
    keywords: ['free tool', 'free tool strategy', 'lead gen tool', 'free calculator'],
    intents: [/(free|lead gen).*(tool|calculator|checker|generator)/i, /(build|create).*(free|lead).*(tool)/i],
  },
  {
    skill: 'jolt-indecision',
    path: 'skills/jolt-indecision/SKILL.md',
    keywords: ['jolt', 'indecision', 'overcome objection', 'deal stuck', 'prospect indecisive'],
    intents: [/(indecis|hesitat|stall|object)/i, /(deal|prospect|buyer).*(stuck|stall|objection|indecis)/i],
  },
  {
    skill: 'launch-strategy',
    path: 'skills/launch-strategy/SKILL.md',
    keywords: ['launch strategy', 'product launch', 'go to market', 'gtm', 'launch plan'],
    intents: [/(launch|go.to.market|gtm).*(strategy|plan)/i, /(plan|strategy).*(launch|release|announce)/i],
  },
  {
    skill: 'lead-magnets',
    path: 'skills/lead-magnets/SKILL.md',
    keywords: ['lead magnet', 'ebook', 'whitepaper', 'gated content', 'email capture'],
    intents: [/lead.?magnet/i, /(create|build|plan).*(ebook|whitepaper|gated|magnet)/i],
  },
  {
    skill: 'lead-pipeline',
    path: 'skills/lead-pipeline/SKILL.md',
    keywords: ['lead pipeline', 'pipeline management', 'enrichment pipeline'],
    intents: [/lead.*(pipeline|flow|funnel)/i, /pipeline.*(manage|track|status)/i],
  },
  {
    skill: 'loop',
    path: 'skills/loop/SKILL.md',
    keywords: ['sales loop', 'touch tracking', 'interaction log', 'outcome tracking'],
    intents: [/(track|log).*(touch|interaction|outcome|reply)/i, /sales.*(loop|intelligence|tracking)/i],
  },
  {
    skill: 'marketing-ideas',
    path: 'skills/marketing-ideas/SKILL.md',
    keywords: ['marketing ideas', 'marketing inspiration', 'growth ideas'],
    intents: [/marketing.*(idea|inspiration|tactic)/i, /(idea|tactic|hack).*(marketing|growth)/i],
  },
  {
    skill: 'marketing-psychology',
    path: 'skills/marketing-psychology/SKILL.md',
    keywords: ['marketing psychology', 'persuasion', 'behavioral science', 'cognitive bias'],
    intents: [/marketing.*(psychology|persuasion|bias)/i, /(persuasion|behavioral|cognitive).*(marketing|copy|design)/i],
  },
  {
    skill: 'n8n-workflow-patterns',
    path: 'skills/n8n-workflow-patterns/SKILL.md',
    keywords: ['n8n', 'n8n workflow', 'n8n automation', 'n8n pattern'],
    intents: [/n8n/i, /workflow.*(automat|pattern|node)/i],
  },
  {
    skill: 'obsidian-cli',
    path: 'skills/obsidian-cli/SKILL.md',
    keywords: ['obsidian', 'vault note', 'obsidian note', 'wiki link'],
    intents: [/obsidian.*(note|vault|cli|manage)/i, /(create|update|search).*(vault|obsidian).*(note)/i],
  },
  {
    skill: 'onboarding-cro',
    path: 'skills/onboarding-cro/SKILL.md',
    keywords: ['onboarding optimization', 'onboarding cro', 'activation flow', 'first run'],
    intents: [/onboarding.*(optim|improv|cro|flow)/i, /(activation|first.?run).*(flow|experience|optim)/i],
  },
  {
    skill: 'outbound-playbook',
    path: 'skills/outbound-playbook/SKILL.md',
    keywords: ['outbound playbook', 'outbound sales', 'outbound strategy'],
    intents: [/outbound.*(playbook|strategy|method)/i],
  },
  {
    skill: 'page-cro',
    path: 'skills/page-cro/SKILL.md',
    keywords: ['page optimization', 'landing page cro', 'page cro', 'convert landing page'],
    intents: [/(landing|marketing|pricing).*(page).*(optim|cro|convert)/i, /page.*(cro|conversion|optim)/i],
  },
  {
    skill: 'paid-ads',
    path: 'skills/paid-ads/SKILL.md',
    keywords: ['paid ads', 'google ads', 'facebook ads', 'meta ads', 'linkedin ads', 'ppc'],
    intents: [/(paid|google|facebook|meta|linkedin|tiktok).*(ads?|ppc|campaign)/i, /ppc/i],
  },
  {
    skill: 'paywall-upgrade-cro',
    path: 'skills/paywall-upgrade-cro/SKILL.md',
    keywords: ['paywall', 'upgrade screen', 'upsell', 'feature gate'],
    intents: [/(paywall|upgrade|upsell|feature.?gate).*(optim|design|cro)/i],
  },
  {
    skill: 'pdf',
    path: 'skills/pdf/SKILL.md',
    keywords: ['pdf', 'create pdf', 'merge pdf', 'extract pdf'],
    intents: [/(create|merge|extract|read|modify|split).*(pdf)/i, /pdf.*(create|merge|extract|modify)/i],
  },
  {
    skill: 'playwright-skill',
    path: 'skills/playwright-skill/SKILL.md',
    keywords: ['browse website', 'scrape page', 'visit url', 'open browser'],
    intents: [/(browse|visit|scrape|open).*(website|page|url|site)/i, /(screenshot|automate).*(browser|page)/i],
  },
  {
    skill: 'popup-cro',
    path: 'skills/popup-cro/SKILL.md',
    keywords: ['popup', 'modal optimization', 'exit intent', 'slide-in'],
    intents: [/(popup|modal|overlay|slide.?in).*(optim|design|create|cro)/i],
  },
  {
    skill: 'post-call',
    path: 'skills/post-call/SKILL.md',
    keywords: ['post call', 'after the call', 'call summary', 'call follow up', 'call recap'],
    intents: [/(post|after).*(call|demo|meeting)/i, /(call|demo|meeting).*(summary|recap|follow.?up|notes)/i],
  },
  {
    skill: 'pptx',
    path: 'skills/pptx/SKILL.md',
    keywords: ['powerpoint', 'pptx', 'slide deck', 'presentation file'],
    intents: [/(create|edit|modify|convert).*(pptx|powerpoint|presentation)/i, /pptx/i],
  },
  {
    skill: 'pricing-strategy',
    path: 'skills/pricing-strategy/SKILL.md',
    keywords: ['pricing strategy', 'pricing model', 'monetization', 'price point'],
    intents: [/(pricing|monetiz|price).*(strategy|model|structure|tier)/i, /how (should|do) (we|I) price/i],
  },
  {
    skill: 'product-marketing-context',
    path: 'skills/product-marketing-context/SKILL.md',
    keywords: ['product marketing context', 'marketing context', 'pmm context'],
    intents: [/product.?marketing.*(context|doc|brief)/i],
  },
  {
    skill: 'programmatic-seo',
    path: 'skills/programmatic-seo/SKILL.md',
    keywords: ['programmatic seo', 'seo at scale', 'template pages', 'seo pages'],
    intents: [/programmatic.*(seo|page)/i, /seo.*(scale|template|programmatic|automat)/i],
  },
  {
    skill: 'receiving-code-review',
    path: 'skills/receiving-code-review/SKILL.md',
    keywords: ['receiving review', 'review feedback', 'address review comments'],
    intents: [/(receiv|address|respond).*(review|feedback|comment)/i],
  },
  {
    skill: 'referral-program',
    path: 'skills/referral-program/SKILL.md',
    keywords: ['referral program', 'affiliate program', 'refer a friend', 'referral'],
    intents: [/(referral|affiliate).*(program|system|scheme)/i, /(create|build|design).*(referral|affiliate)/i],
  },
  {
    skill: 'requesting-code-review',
    path: 'skills/requesting-code-review/SKILL.md',
    keywords: ['request review', 'ask for review', 'pre-merge checklist'],
    intents: [/(request|ask for|need).*(review|feedback)/i, /pre.?merge/i],
  },
  {
    skill: 'revops',
    path: 'skills/revops/SKILL.md',
    keywords: ['revops', 'revenue operations', 'lead lifecycle', 'marketing to sales handoff'],
    intents: [/rev.?ops/i, /revenue.*(operations|ops)/i, /(marketing|lead).*(handoff|handover|lifecycle)/i],
  },
  {
    skill: 'rule-validator',
    path: 'skills/rule-validator/SKILL.md',
    keywords: ['validate rules', 'rule conflicts', 'carl validation', 'rule audit'],
    intents: [/(validate|check|audit).*(rule|carl|constraint)/i, /rule.*(conflict|valid|audit)/i],
  },
  {
    skill: 'sales-enablement',
    path: 'skills/sales-enablement/SKILL.md',
    keywords: ['sales enablement', 'sales deck', 'sales collateral', 'battle card'],
    intents: [/sales.*(enablement|deck|collateral|battle.?card)/i, /(create|build).*(sales|pitch).*(deck|material)/i],
  },
  {
    skill: 'sales-skills',
    path: 'skills/sales-skills/SKILL.md',
    keywords: ['sales skills', 'selling technique', 'sales training', 'close deal'],
    intents: [/sales.*(skill|technique|training|tactic)/i, /(close|negotiate|handle).*(deal|objection)/i],
  },
  {
    skill: 'schema-markup',
    path: 'skills/schema-markup/SKILL.md',
    keywords: ['schema markup', 'structured data', 'json-ld', 'rich snippets'],
    intents: [/schema.*(markup|data|json)/i, /structured.?data/i, /rich.?snippet/i],
  },
  {
    skill: 'self-audit',
    path: 'skills/self-audit/SKILL.md',
    keywords: ['self audit', 'system audit', 'intelligence review', 'pattern review'],
    intents: [/self.?audit/i, /(audit|review).*(intelligence|pattern|system|brain)/i],
  },
  {
    skill: 'seo-audit',
    path: 'skills/seo-audit/SKILL.md',
    keywords: ['seo audit', 'seo review', 'seo issues', 'seo check'],
    intents: [/seo.*(audit|review|check|issue|diagnos)/i, /(audit|review|check).*(seo|search|ranking)/i],
  },
  {
    skill: 'signup-flow-cro',
    path: 'skills/signup-flow-cro/SKILL.md',
    keywords: ['signup flow', 'registration flow', 'signup optimization'],
    intents: [/(signup|registration|sign.up).*(flow|optim|cro|improve)/i],
  },
  {
    skill: 'site-architecture',
    path: 'skills/site-architecture/SKILL.md',
    keywords: ['site architecture', 'site structure', 'navigation structure', 'url structure'],
    intents: [/site.*(architecture|structure|hierarchy|navigation)/i, /(url|nav|information).*(architecture|structure)/i],
  },
  {
    skill: 'social-content',
    path: 'skills/social-content/SKILL.md',
    keywords: ['social media content', 'social post', 'linkedin post', 'twitter post'],
    intents: [/(social|linkedin|twitter|x\.com).*(content|post|write|draft)/i, /(write|create|draft).*(social|linkedin|twitter).*(post|content)/i],
  },
  {
    skill: 'subagent-driven-development',
    path: 'skills/subagent-driven-development/SKILL.md',
    keywords: ['subagent development', 'delegate to agents', 'agent driven'],
    intents: [/subagent.*(develop|driv|dispatch)/i, /delegate.*(agent|subagent)/i],
  },
  {
    skill: 'tech-stack-evaluator',
    path: 'skills/tech-stack-evaluator/SKILL.md',
    keywords: ['tech stack', 'stack evaluation', 'technology choice', 'framework comparison'],
    intents: [/tech.*(stack|choice|evaluation)/i, /(evaluate|compare|choose).*(framework|stack|tool|technology)/i],
  },
  {
    skill: 'ui-ux-pro-max',
    path: 'skills/ui-ux-pro-max/SKILL.md',
    keywords: ['ui design', 'ux design', 'design system', 'component design', 'ui/ux'],
    intents: [/(ui|ux).*(design|system|component)/i, /design.*(system|component|ui|interface)/i],
  },
  {
    skill: 'using-git-worktrees',
    path: 'skills/using-git-worktrees/SKILL.md',
    keywords: ['git worktree', 'worktree', 'isolated branch'],
    intents: [/worktree/i, /isolated.*(branch|workspace|copy)/i],
  },
  {
    skill: 'writing-plans',
    path: 'skills/writing-plans/SKILL.md',
    keywords: ['write plan', 'implementation plan', 'task breakdown'],
    intents: [/(write|create|draft).*(plan|breakdown)/i, /implementation.*(plan|spec)/i],
  },
  {
    skill: 'xlsx',
    path: 'skills/xlsx/SKILL.md',
    keywords: ['xlsx', 'excel', 'spreadsheet', 'csv to excel'],
    intents: [/(create|edit|read|modify).*(xlsx|excel|spreadsheet)/i, /xlsx/i],
  },
  {
    skill: 'one-step-better',
    path: 'skills/one-step-better/SKILL.md',
    keywords: ['one step better', 'improvement tips', 'session tips'],
    intents: [/one.?step.?better/i, /(improvement|session).*(tip|suggestion)/i],
  },
  {
    skill: 'quality-loop',
    path: 'skills/quality-loop/SKILL.md',
    keywords: ['quality loop', 'system health', 'quality check'],
    intents: [/quality.*(loop|check|health)/i, /system.*(health|quality|check)/i],
  },

  // ── .claude/skills (plugin skills) ──────────────────────────
  {
    skill: 'autoresearch',
    path: '.claude/skills/autoresearch/SKILL.md',
    keywords: ['autoresearch', 'autonomous iteration', 'iterate autonomously', 'auto improve'],
    intents: [/autonom.*(iterat|improv|optim|loop)/i, /auto.?research/i, /keep (trying|iterating|improving) until/i],
  },
  {
    skill: 'e2e-testing',
    path: '.claude/skills/e2e-testing/SKILL.md',
    keywords: ['e2e test', 'end to end test', 'playwright test', 'write a test'],
    intents: [/(e2e|end.to.end).*(test|spec)/i, /(write|create|add).*(test|spec).*(flow|page|feature)/i],
  },
  {
    skill: 'frontend-slides',
    path: '.claude/skills/frontend-slides/SKILL.md',
    keywords: ['html presentation', 'create slides', 'convert ppt', 'html slides'],
    intents: [/(create|build|convert).*(slide|presentation|deck).*(html|web)/i, /(ppt|powerpoint).*(html|web|convert)/i],
  },
  {
    skill: 'modern-python',
    path: '.claude/skills/modern-python/SKILL.md',
    keywords: ['modern python', 'uv setup', 'ruff setup', 'python project setup'],
    intents: [/(set up|configure|init).*(python|uv|ruff)/i, /modern.?python/i, /(uv|ruff|ty).*(config|setup|init)/i],
  },
  {
    skill: 'notebooklm',
    path: '.claude/skills/notebooklm/SKILL.md',
    keywords: ['notebooklm', 'notebook lm', 'google notebook', 'create podcast'],
    intents: [/notebook.?lm/i, /(create|generate).*(podcast|audio overview)/i],
  },
  {
    skill: 'property-based-testing',
    path: '.claude/skills/property-based-testing/SKILL.md',
    keywords: ['property based testing', 'hypothesis testing', 'fuzz testing', 'property test'],
    intents: [/property.?based/i, /hypothesis.*(test|framework)/i, /fuzz.*(test|input)/i],
  },
  {
    skill: 'research',
    path: '.claude/skills/research/SKILL.md',
    keywords: ['deep research', 'research this', 'investigate', 'deep dive'],
    intents: [/(deep|thorough).*(research|dive|investigation)/i, /research.*(deep|thorough|comprehensive)/i, /investigate.*(market|competitor|technology|vendor)/i],
  },
  {
    skill: 'security-scan',
    path: '.claude/skills/security-scan/SKILL.md',
    keywords: ['security scan', 'scan config', 'agentshield', 'scan claude config'],
    intents: [/(scan|audit).*(security|config|claude|hooks)/i, /agentshield/i],
  },
];

// ── Matching engine ──────────────────────────────────────────────
const matches = [];

for (const skill of SKILLS) {
  let matched = false;
  let matchType = '';

  // Tier 1: keyword match (fast)
  for (const kw of skill.keywords) {
    if (message.includes(kw.toLowerCase())) {
      matched = true;
      matchType = 'keyword';
      break;
    }
  }

  // Tier 2: intent regex (broader)
  if (!matched && skill.intents) {
    for (const re of skill.intents) {
      if (re.test(message)) {
        matched = true;
        matchType = 'intent';
        break;
      }
    }
  }

  if (matched) {
    matches.push({ skill: skill.skill, path: skill.path, matchType });
  }
}

// ── Output ───────────────────────────────────────────────────────
if (matches.length > 0) {
  const lines = matches.map(m =>
    `SKILL MATCH [${m.matchType}]: Load ${m.path} (${m.skill})`
  );
  process.stdout.write(JSON.stringify({
    result: lines.join('\n')
  }));
}
