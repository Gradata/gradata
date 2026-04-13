// TODO(backend): replace when /api/v1/brains/{id}/activity endpoint exists.
export type ActivityKind = 'graduation' | 'self-healing' | 'recurrence' | 'meta-rule' | 'alert' | 'convergence'

export interface MockActivity {
  id: string
  kind: ActivityKind
  title: string
  detail: string
  created_at: string
  __mocked: true
}

export const mockActivity: MockActivity[] = [
  { id: 'a1', kind: 'graduation',   title: 'Rule graduated to RULE state', detail: '"Verify claims against source"', created_at: new Date(Date.now() - 2 * 3600_000).toISOString(),  __mocked: true },
  { id: 'a2', kind: 'self-healing', title: 'Self-healing patch applied',    detail: 'URL verification',                created_at: new Date(Date.now() - 8 * 3600_000).toISOString(),  __mocked: true },
  { id: 'a3', kind: 'convergence',  title: 'Convergence signal',            detail: '4 users corrected same direction', created_at: new Date(Date.now() - 14 * 3600_000).toISOString(), __mocked: true },
  { id: 'a4', kind: 'recurrence',   title: 'Recurrence detected',           detail: 'Tone pattern returned',           created_at: new Date(Date.now() - 22 * 3600_000).toISOString(), __mocked: true },
  { id: 'a5', kind: 'meta-rule',    title: 'Meta-rule emerged',             detail: '"Cut ceremony" — 4 source rules', created_at: new Date(Date.now() - 36 * 3600_000).toISOString(), __mocked: true },
  { id: 'a6', kind: 'alert',        title: 'Factual correction ×3',         detail: 'spike this week',                 created_at: new Date(Date.now() - 60 * 3600_000).toISOString(), __mocked: true },
]
