/**
 * Operator / god-mode domain check.
 *
 * Mirrors the backend allowlist in `cloud/app/auth.py` (`OPERATOR_DOMAINS`).
 * When a user's email matches one of these domains, the frontend should
 * bypass `PlanGate` blur overlays so operators can preview gated features
 * without having to upgrade their plan.
 *
 * This is UX-only. The backend still enforces plan gates on data endpoints;
 * if an operator viewport hits a 403, the page will still surface an error.
 */
const OPERATOR_DOMAINS = ['gradata.ai', 'sprites.ai']

export function isOperatorEmail(email: string | null | undefined): boolean {
  if (!email) return false
  const trimmed = email.trim()
  // Reject multi-@ inputs (e.g. "user@evil.com@gradata.ai") to match backend semantics.
  const parts = trimmed.split('@')
  if (parts.length !== 2) return false
  const domain = parts[1].toLowerCase()
  return OPERATOR_DOMAINS.includes(domain)
}
