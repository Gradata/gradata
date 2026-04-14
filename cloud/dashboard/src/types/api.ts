export interface Brain {
  id: string
  user_id: string
  name: string
  domain: string
  lesson_count: number
  correction_count: number
  last_sync: string | null
  created_at: string
}

export interface Lesson {
  id: string
  brain_id: string
  description: string
  category: string
  state: 'INSTINCT' | 'PATTERN' | 'RULE'
  confidence: number
  fire_count: number
  created_at: string
}

export interface Correction {
  id: string
  brain_id: string
  severity: 'trivial' | 'minor' | 'moderate' | 'major' | 'rewrite'
  category: string
  description: string
  draft_preview: string | null
  final_preview: string | null
  created_at: string
}

export interface BrainAnalytics {
  total_lessons: number
  total_corrections: number
  graduation_rate: number
  avg_confidence: number
  lessons_by_state: Record<string, number>
  corrections_by_severity: Record<string, number>
  corrections_by_category: Record<string, number>
}

export interface ApiKey {
  id: string
  key_prefix: string
  name: string
  created_at: string
  last_used: string | null
}

export interface ApiKeyCreateResponse {
  id: string
  key: string
  name: string
}

export interface WorkspaceSummary {
  id: string
  name?: string
  plan?: string
  role?: string
}

export interface UserProfile {
  user_id: string
  // `email` and `plan` may be omitted by /users/me depending on backend
  // version (auth payload can be thin). Mark optional so the compiler
  // catches missing-field usages in callers.
  email?: string | null
  display_name: string | null
  plan?: string | null
  created_at: string | null
  workspaces?: WorkspaceSummary[]
}

export interface PaginatedResponse<T> {
  data: T[]
  total: number
  page: number
  per_page: number
}

// -----------------------------------------------------------------------------
// Team / workspace members
// -----------------------------------------------------------------------------

export type MemberRole = 'owner' | 'admin' | 'member'
export type InviteRole = 'admin' | 'member'

export interface TeamMember {
  user_id: string
  email: string | null
  display_name: string | null
  role: MemberRole
  joined_at: string | null
  last_sync_at: string | null
}

export interface InviteResponse {
  id: string
  email: string
  role: InviteRole
  token: string
  accept_url: string
  expires_at: string | null
}

// -----------------------------------------------------------------------------
// Operator / god-mode (require_operator gated)
// -----------------------------------------------------------------------------

export interface AdminGlobalKpis {
  mrr_usd: number
  arr_usd: number
  mrr_delta_pct: number
  customers_total: number
  customers_active: number
  churn_rate: number
  net_revenue_retention: number
}

export type AdminHealth = 'healthy' | 'at-risk' | 'churning'
export type AdminPlan = 'free' | 'cloud' | 'team' | 'enterprise' | 'pro'

export interface AdminCustomer {
  id: string
  company: string
  plan: AdminPlan | string
  mrr_usd: number
  active_users: number
  brains: number
  last_active: string | null
  health: AdminHealth
}

export type AdminAlertKind = 'churn-risk' | 'failed-payment' | 'usage-spike'

export interface AdminAlert {
  id: string
  kind: AdminAlertKind | string
  customer: string
  detail: string
  created_at: string
}

// -----------------------------------------------------------------------------
// Clear demo response
// -----------------------------------------------------------------------------

export interface ClearDemoResponse {
  deleted: number
  by_table: Record<string, number>
}
