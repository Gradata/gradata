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
  recurrence_blocked?: boolean
  last_recurrence_at?: string | null
  graduated_at?: string | null
  correction_count?: number
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

export interface UserProfile {
  user_id: string
  email: string | null
  display_name: string | null
  plan: string | null
  workspaces: Array<{
    id: string
    name: string
    plan: string
    role: string | null
  }>
  created_at: string | null
}

export interface PaginatedResponse<T> {
  data: T[]
  total: number
  page: number
  per_page: number
}

// Operator / god-mode (require_operator gated)
export interface AdminGlobalKpis {
  mrr_usd: number
  arr_usd: number
  mrr_delta_pct: number
  customers_total: number
  customers_active: number
  churn_rate: number
  net_revenue_retention: number
}

export interface AdminCustomer {
  id: string
  company: string
  plan: 'free' | 'cloud' | 'team' | 'enterprise' | string
  mrr_usd: number
  active_users: number
  brains: number
  last_active: string | null
  health: 'healthy' | 'at-risk' | 'churning'
}

export interface AdminAlert {
  id: string
  kind: 'churn-risk' | 'failed-payment' | 'usage-spike'
  customer: string
  detail: string
  created_at: string
}
