// Operator/admin view data (Oliver's god-mode). Hidden from non-Gradata users.
// TODO(backend): replace when /api/v1/admin/* endpoints ship.

export interface AdminCustomer {
  id: string
  company: string
  plan: 'free' | 'cloud' | 'team' | 'enterprise'
  mrr_usd: number
  active_users: number
  brains: number
  last_active: string
  health: 'healthy' | 'at-risk' | 'churning'
  __mocked: true
}

export interface AdminGlobalKpis {
  mrr_usd: number
  arr_usd: number
  mrr_delta_pct: number
  customers_total: number
  customers_active: number
  churn_rate: number
  net_revenue_retention: number
}

export const mockGlobalKpis: AdminGlobalKpis = {
  mrr_usd: 4_872,
  arr_usd: 58_464,
  mrr_delta_pct: 23.4,
  customers_total: 148,
  customers_active: 112,
  churn_rate: 0.028,
  net_revenue_retention: 1.12,
}

export const mockCustomers: AdminCustomer[] = [
  { id: 'c01', company: 'Stripe',                plan: 'team',       mrr_usd: 99, active_users: 14, brains: 14, last_active: new Date(Date.now() - 30 * 60_000).toISOString(),       health: 'healthy', __mocked: true },
  { id: 'c02', company: 'Linear',                plan: 'team',       mrr_usd: 99, active_users: 9,  brains: 9,  last_active: new Date(Date.now() - 3 * 3600_000).toISOString(),      health: 'healthy', __mocked: true },
  { id: 'c03', company: 'Vercel',                plan: 'team',       mrr_usd: 99, active_users: 12, brains: 12, last_active: new Date(Date.now() - 2 * 3600_000).toISOString(),      health: 'healthy', __mocked: true },
  { id: 'c04', company: 'Cursor',                plan: 'cloud',      mrr_usd: 29, active_users: 1,  brains: 1,  last_active: new Date(Date.now() - 5 * 3600_000).toISOString(),      health: 'healthy', __mocked: true },
  { id: 'c05', company: 'Raycast',               plan: 'cloud',      mrr_usd: 29, active_users: 1,  brains: 1,  last_active: new Date(Date.now() - 12 * 3600_000).toISOString(),     health: 'healthy', __mocked: true },
  { id: 'c06', company: 'HashiCorp',             plan: 'enterprise', mrr_usd: 2_400, active_users: 180, brains: 180, last_active: new Date(Date.now() - 1 * 3600_000).toISOString(), health: 'healthy', __mocked: true },
  { id: 'c07', company: 'DatabricksLabs (trial)',plan: 'free',       mrr_usd: 0,  active_users: 3, brains: 3,  last_active: new Date(Date.now() - 16 * 24 * 3600_000).toISOString(), health: 'at-risk', __mocked: true },
  { id: 'c08', company: 'Acme (legal)',          plan: 'cloud',      mrr_usd: 29, active_users: 1,  brains: 1,  last_active: new Date(Date.now() - 28 * 24 * 3600_000).toISOString(), health: 'churning', __mocked: true },
]

export interface AdminAlert {
  id: string
  kind: 'churn-risk' | 'failed-payment' | 'usage-spike'
  customer: string
  detail: string
  created_at: string
  __mocked: true
}

export const mockAlerts: AdminAlert[] = [
  { id: 'al1', kind: 'churn-risk',     customer: 'DatabricksLabs (trial)', detail: '16 days inactive',              created_at: new Date(Date.now() - 4 * 3600_000).toISOString(),  __mocked: true },
  { id: 'al2', kind: 'failed-payment', customer: 'Acme (legal)',           detail: 'Stripe invoice unpaid 28d',     created_at: new Date(Date.now() - 22 * 3600_000).toISOString(), __mocked: true },
  { id: 'al3', kind: 'usage-spike',    customer: 'HashiCorp',              detail: 'corrections 3× weekly average', created_at: new Date(Date.now() - 1 * 3600_000).toISOString(),  __mocked: true },
]
