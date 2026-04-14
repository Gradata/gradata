// TODO(backend): replace when /api/v1/brains/{id}/meta-rules endpoint exists.
// Structure per SIM101/102: 2-layer (Objective / Subjective) with Goal
// Alignment as the governing node above both layers.

export type MetaRuleLayer = 'goal' | 'objective' | 'subjective'
export type MetaRuleTier = 'universal' | 'strong' | 'minority'

export interface MockMetaRule {
  id: string
  title: string
  layer: MetaRuleLayer
  tier: MetaRuleTier
  source_description: string
  source_rule_ids: string[]
  source_categories: string[]
  __mocked: true
}

export const mockMetaRules: MockMetaRule[] = [
  {
    id: 'm0',
    title: 'Every output must serve the stated goal',
    layer: 'goal',
    tier: 'universal',
    source_description: 'Derived from 6 rules across all categories',
    source_rule_ids: ['r1', 'r2', 'r3', 'r4', 'r5', 'r6'],
    source_categories: ['Goal Alignment'],
    __mocked: true,
  },
  {
    id: 'm1',
    title: 'Verify claims against source before asserting',
    layer: 'objective',
    tier: 'universal',
    source_description: 'From 3 rules: Factual Integrity + Domain Fit',
    source_rule_ids: ['r1', 'r2', 'r3'],
    source_categories: ['Factual Integrity', 'Domain Fit'],
    __mocked: true,
  },
  {
    id: 'm2',
    title: 'Prefer concise prose; cut ceremony',
    layer: 'objective',
    tier: 'strong',
    source_description: 'From 4 rules: Clarity & Structure',
    source_rule_ids: ['r4', 'r5', 'r6', 'r7'],
    source_categories: ['Clarity & Structure'],
    __mocked: true,
  },
  {
    id: 'm3',
    title: 'Keep professional communication direct, not warm',
    layer: 'subjective',
    tier: 'strong',
    source_description: 'From 3 rules: Tone & Register',
    source_rule_ids: ['r8', 'r9', 'r10'],
    source_categories: ['Tone & Register'],
    __mocked: true,
  },
  {
    id: 'm4',
    title: 'Close with a clear next action',
    layer: 'subjective',
    tier: 'minority',
    source_description: 'From 3 rules: Actionability',
    source_rule_ids: ['r11', 'r12', 'r13'],
    source_categories: ['Actionability'],
    __mocked: true,
  },
]
