// TODO(backend): replace when /api/v1/brains/{id}/rule-patches endpoint ships.
// Per feedback_rule_to_hook_graduation memory — rules auto-evolve when
// deterministic, self-healing adjusts wording based on recurrence.

export type PatchKind = 'auto-evolve' | 'recurrence-fix' | 'contradiction-resolve' | 'hook-promotion'

export interface MockPatch {
  id: string
  lesson_id: string
  kind: PatchKind
  old_description: string
  new_description: string
  reason: string
  created_at: string
  /** Did the patch reduce recurrence? Null = not yet measured */
  recurrence_change_pct: number | null
  __mocked: true
}

export const mockPatches: MockPatch[] = [
  {
    id: 'p1',
    lesson_id: 'r3',
    kind: 'recurrence-fix',
    old_description: 'Verify URLs before including them',
    new_description: 'Verify every URL against the source document before including it; never paraphrase a URL',
    reason: 'Same rule fired 5× but error recurred 3× — description was too soft on the enforcement step',
    created_at: new Date(Date.now() - 2 * 3600_000).toISOString(),
    recurrence_change_pct: -68,
    __mocked: true,
  },
  {
    id: 'p2',
    lesson_id: 'r7',
    kind: 'auto-evolve',
    old_description: 'Keep emails concise',
    new_description: 'Keep emails under 120 words; one-sentence openings; no hedging',
    reason: 'Graduated rule kept producing medium-length emails; corrections narrowed the wording',
    created_at: new Date(Date.now() - 14 * 3600_000).toISOString(),
    recurrence_change_pct: -41,
    __mocked: true,
  },
  {
    id: 'p3',
    lesson_id: 'r11',
    kind: 'contradiction-resolve',
    old_description: 'Always confirm before acting on assumptions',
    new_description: 'Confirm before acting on assumptions, EXCEPT when user explicitly invokes "godmode" / "OODA" — then proceed',
    reason: 'Rule conflicted with godmode directive; resolved in favor of godmode with explicit carve-out',
    created_at: new Date(Date.now() - 30 * 3600_000).toISOString(),
    recurrence_change_pct: null,
    __mocked: true,
  },
  {
    id: 'p4',
    lesson_id: 'r18',
    kind: 'hook-promotion',
    old_description: '(rule injected via prompt)',
    new_description: '(promoted to deterministic hook: em_dash_replacer)',
    reason: 'Rule was 100% deterministic (regex-replaceable); promoted from prompt injection to code hook',
    created_at: new Date(Date.now() - 3 * 24 * 3600_000).toISOString(),
    recurrence_change_pct: -100,
    __mocked: true,
  },
]
