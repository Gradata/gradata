// TODO(backend): replace when /api/v1/workspaces/{id}/team endpoints ship.
// Shapes match the intended real API so component code won't change.

export type MemberRole = 'owner' | 'admin' | 'member'
export type MemberStatus = 'active' | 'inactive'

export interface MockMember {
  id: string
  email: string
  name: string
  role: MemberRole
  status: MemberStatus
  last_sync_at: string | null
  /** Corrections this week */
  corrections_week: number
  /** % change vs prior week, negative = learning */
  correction_delta_pct: number
  /** Rules graduated to RULE state in last 30d */
  rules_graduated_30d: number
  /** Fraction of rules that have not recurred */
  recurrence_rate: number
  __mocked: true
}

export const mockTeam: MockMember[] = [
  { id: 'u1', name: 'Oliver Le',      email: 'oliver@gradata.ai', role: 'owner',  status: 'active',   last_sync_at: new Date(Date.now() - 45 * 60_000).toISOString(),  corrections_week: 12, correction_delta_pct: -42, rules_graduated_30d: 7, recurrence_rate: 0.03, __mocked: true },
  { id: 'u2', name: 'Priya Shah',     email: 'priya@example.com',  role: 'admin',  status: 'active',   last_sync_at: new Date(Date.now() - 2 * 3600_000).toISOString(), corrections_week: 8,  correction_delta_pct: -58, rules_graduated_30d: 5, recurrence_rate: 0.00, __mocked: true },
  { id: 'u3', name: 'Marcus Chen',    email: 'marcus@example.com', role: 'member', status: 'active',   last_sync_at: new Date(Date.now() - 1 * 3600_000).toISOString(), corrections_week: 21, correction_delta_pct: +12, rules_graduated_30d: 3, recurrence_rate: 0.14, __mocked: true },
  { id: 'u4', name: 'Ana Rodríguez',  email: 'ana@example.com',    role: 'member', status: 'active',   last_sync_at: new Date(Date.now() - 8 * 3600_000).toISOString(), corrections_week: 6,  correction_delta_pct: -33, rules_graduated_30d: 4, recurrence_rate: 0.05, __mocked: true },
  { id: 'u5', name: 'Jon Lee',        email: 'jon@example.com',    role: 'member', status: 'inactive', last_sync_at: new Date(Date.now() - 9 * 24 * 3600_000).toISOString(), corrections_week: 0,  correction_delta_pct: 0,   rules_graduated_30d: 0, recurrence_rate: 0.00, __mocked: true },
  { id: 'u6', name: 'Sam Park',       email: 'sam@example.com',    role: 'member', status: 'active',   last_sync_at: new Date(Date.now() - 30 * 60_000).toISOString(),  corrections_week: 14, correction_delta_pct: -18, rules_graduated_30d: 2, recurrence_rate: 0.08, __mocked: true },
]

export function computeTeamAggregate(members: MockMember[]) {
  const active = members.filter((m) => m.status === 'active')
  const correctionsWeek = members.reduce((s, m) => s + m.corrections_week, 0)
  const rulesGraduated = members.reduce((s, m) => s + m.rules_graduated_30d, 0)
  const avgRecurrence =
    active.length === 0
      ? 0
      : active.reduce((s, m) => s + m.recurrence_rate, 0) / active.length
  const avgDelta =
    active.length === 0
      ? 0
      : active.reduce((s, m) => s + m.correction_delta_pct, 0) / active.length
  return {
    correctionsWeek,
    rulesGraduated,
    avgRecurrence,
    avgDelta,
    activeBrains: active.length,
    totalMembers: members.length,
  }
}
