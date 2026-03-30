#!/usr/bin/env node
/**
 * research-synthesizer.js -- Multi-source research synthesis utility
 * Takes raw outputs from Apollo, Pipedrive, Gemini, NotebookLM, Fireflies,
 * and brain/prospects/ and produces a single prioritized brief.
 *
 * NOT a hook -- called by the orchestrator during workflows.
 *
 * Usage:
 *   const { synthesize } = require('./research-synthesizer.js');
 *   const brief = synthesize({
 *     prospect: 'Drew',
 *     company: 'Acme Corp',
 *     workflow: 'demo-prep',  // or 'email-outreach', 'pre-call', 'prospecting'
 *     sources: {
 *       apollo: { ... },       // raw Apollo contact/company data
 *       pipedrive: { ... },    // deal data, stage, activities
 *       gemini: '...',         // Gemini research output (string)
 *       notebooklm: '...',     // NotebookLM query results
 *       fireflies: '...',      // call transcript excerpts
 *       brain: '...',          // brain/prospects/ note content
 *       patterns: '...',       // PATTERNS.md relevant section
 *     }
 *   });
 *
 * Or from CLI for testing:
 *   node research-synthesizer.js --test
 */

// Synthesis templates by workflow type
const SYNTHESIS_TEMPLATES = {
  'demo-prep': {
    sections: [
      { key: 'company_explainer', label: 'What This Company Does', priority: 1,
        prompt: 'In 3 sentences, explain what {company} does, who their customers are, and how their product works. Write for someone who has never heard of them.' },
      { key: 'why_they_booked', label: 'Why They Booked', priority: 1,
        prompt: 'Based on their campaign origin, comment/signup context, and any prior interactions: why did this person book a demo? What are they hoping to solve?' },
      { key: 'pain_points', label: 'Likely Pain Points', priority: 1,
        prompt: 'Based on their role ({role}), company size, and industry: what are the top 3 pain points Sprites can address? Rank by likelihood.' },
      { key: 'sprites_fit', label: 'How Sprites Solves It', priority: 1,
        prompt: 'Map each pain point to a specific Sprites feature. Include which demo thread to show.' },
      { key: 'red_flags', label: 'Red Flags / Objections to Expect', priority: 2,
        prompt: 'What objections might come up? Budget concerns? Competitor loyalty? Technical hesitation? Check patterns for this persona type.' },
      { key: 'talking_points', label: 'Personalized Talking Points', priority: 1,
        prompt: 'List 3 specific, referenceable things about this person or company. Recent LinkedIn posts, company news, mutual connections, career moves.' },
      { key: 'competitors', label: 'Competitive Landscape', priority: 3,
        prompt: 'What tools/agencies is this company likely using? Check their tech stack, job postings, ad library.' },
      { key: 'pricing_angle', label: 'Pricing Strategy', priority: 2,
        prompt: 'Based on company size and likely use case: which Sprites tier to target? Starter ($60), Standard ($500-1K), or custom?' },
    ],
  },
  'email-outreach': {
    sections: [
      { key: 'personalization', label: 'Personalization Hooks', priority: 1,
        prompt: 'Find 2-3 specific, referenceable details about this person for the email opener. LinkedIn activity, company news, role changes.' },
      { key: 'pain_angle', label: 'Best Angle for This Prospect', priority: 1,
        prompt: 'Based on their role and company, which email angle will resonate? Check PATTERNS.md for what works with this persona type.' },
      { key: 'case_study_match', label: 'Best Case Study Match', priority: 2,
        prompt: 'Which Sprites case study is closest to this prospect\'s situation? Match by industry, company size, or use case.' },
      { key: 'avoid', label: 'What to Avoid', priority: 2,
        prompt: 'Check prior outreach history. What angles already failed? What tone didn\'t work? Don\'t repeat.' },
    ],
  },
  'pre-call': {
    sections: [
      { key: 'since_last_contact', label: 'What Changed Since Last Contact', priority: 1,
        prompt: 'Any company news, role changes, funding, product launches, or LinkedIn activity since {last_touch_date}?' },
      { key: 'open_items', label: 'Open Items from Last Interaction', priority: 1,
        prompt: 'What was promised, what questions were left unanswered, what next steps were agreed?' },
      { key: 'call_objective', label: 'Call Objective', priority: 1,
        prompt: 'Based on deal stage and history: what is the ONE thing this call should accomplish?' },
      { key: 'risk_factors', label: 'Risk Factors', priority: 2,
        prompt: 'Is the deal going cold? How many days since last touch? Any signals of disengagement?' },
    ],
  },
  'post-demo': {
    sections: [
      { key: 'key_moments', label: 'Key Moments from the Call', priority: 1,
        prompt: 'What were the highest-signal moments? Buying signals, objections raised, features that resonated, features that fell flat.' },
      { key: 'pain_confirmed', label: 'Confirmed Pain Points', priority: 1,
        prompt: 'Which pain points did the prospect actually confirm during the call? These are gold for follow-up.' },
      { key: 'next_steps', label: 'Agreed Next Steps', priority: 1,
        prompt: 'What was explicitly agreed? Trial? Another call? Internal review? Who else needs to be involved?' },
      { key: 'follow_up_angle', label: 'Best Follow-Up Angle', priority: 1,
        prompt: 'Based on what resonated, what should the follow-up email lead with? Not features, but their specific concern + how we solve it.' },
      { key: 'deal_update', label: 'CRM Updates Needed', priority: 2,
        prompt: 'What fields need updating? Stage change, health score adjustment, next touch date, notes.' },
    ],
  },
  'prospecting': {
    sections: [
      { key: 'icp_fit', label: 'ICP Fit Assessment', priority: 1,
        prompt: 'Does this prospect match the Sprites ICP? Score: role fit, company size fit, industry fit, tech stack fit, budget fit.' },
      { key: 'campaign_match', label: 'Best Campaign Match', priority: 1,
        prompt: 'Which existing Instantly campaign would this lead fit best? Or does a new sequence need to be created?' },
      { key: 'tier', label: 'Recommended Tier', priority: 1,
        prompt: 'T1 (high-value, personalized outreach), T2 (standard sequence), T3 (batch only), or REMOVE?' },
      { key: 'enrichment_gaps', label: 'Missing Data', priority: 2,
        prompt: 'What data is missing? Email? Phone? Company details? What enrichment sources could fill the gaps?' },
    ],
  },
};

/**
 * Build a synthesis prompt from raw source data and workflow template.
 * Returns a structured prompt that Claude or Gemini can process.
 */
function buildSynthesisPrompt(opts) {
  const { prospect, company, workflow, sources, role, lastTouchDate } = opts;
  const template = SYNTHESIS_TEMPLATES[workflow];
  if (!template) return null;

  // Build the source context block
  let context = `# Research Synthesis: ${prospect} at ${company}\n`;
  context += `Workflow: ${workflow}\n\n`;
  context += `## Raw Source Data\n\n`;

  if (sources.apollo) {
    context += `### Apollo Contact/Company Data\n`;
    context += typeof sources.apollo === 'string'
      ? sources.apollo
      : JSON.stringify(sources.apollo, null, 2);
    context += '\n\n';
  }
  if (sources.pipedrive) {
    context += `### Pipedrive Deal Data\n`;
    context += typeof sources.pipedrive === 'string'
      ? sources.pipedrive
      : JSON.stringify(sources.pipedrive, null, 2);
    context += '\n\n';
  }
  if (sources.gemini) {
    context += `### Gemini Research\n${sources.gemini}\n\n`;
  }
  if (sources.notebooklm) {
    context += `### NotebookLM Results\n${sources.notebooklm}\n\n`;
  }
  if (sources.fireflies) {
    context += `### Fireflies Transcript\n${sources.fireflies}\n\n`;
  }
  if (sources.brain) {
    context += `### Existing Prospect Notes (brain/)\n${sources.brain}\n\n`;
  }
  if (sources.patterns) {
    context += `### PATTERNS.md Insights\n${sources.patterns}\n\n`;
  }
  if (sources.web) {
    context += `### Web Research\n${sources.web}\n\n`;
  }

  // Build the synthesis instructions
  context += `## Synthesis Instructions\n\n`;
  context += `Using ALL the source data above, produce a structured brief with these sections.\n`;
  context += `Prioritize information that is ACTIONABLE for a sales call/email.\n`;
  context += `If sources contradict each other, flag the conflict.\n`;
  context += `If a section has insufficient data, say "[INSUFFICIENT — need X]" not a guess.\n\n`;

  for (const section of template.sections) {
    const prompt = section.prompt
      .replace('{company}', company || 'the company')
      .replace('{role}', role || 'their role')
      .replace('{last_touch_date}', lastTouchDate || 'last contact');
    context += `### ${section.label} (P${section.priority})\n`;
    context += `${prompt}\n\n`;
  }

  return context;
}

/**
 * Get the synthesis template for a workflow.
 */
function getTemplate(workflow) {
  return SYNTHESIS_TEMPLATES[workflow] || null;
}

/**
 * List available workflows.
 */
function listWorkflows() {
  return Object.keys(SYNTHESIS_TEMPLATES);
}

// CLI mode
if (require.main === module) {
  const arg = process.argv[2];
  if (arg === '--test') {
    const prompt = buildSynthesisPrompt({
      prospect: 'Drew',
      company: 'Test Corp',
      workflow: 'demo-prep',
      role: 'VP Marketing',
      sources: {
        apollo: { name: 'Drew', title: 'VP Marketing', company: 'Test Corp', employees: 50 },
        gemini: 'Test Corp is a mid-market SaaS company focused on HR tech. Recently raised Series B.',
        brain: 'No prior interactions.',
      },
    });
    console.log(prompt);
  } else {
    console.log('Available workflows:', listWorkflows().join(', '));
    console.log('\nUsage: node research-synthesizer.js --test');
  }
}

module.exports = { buildSynthesisPrompt, getTemplate, listWorkflows, SYNTHESIS_TEMPLATES };
