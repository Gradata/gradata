import Link from 'next/link'

/**
 * Tiny Privacy · Terms links for the bottom of auth cards
 * (login, signup, forgot password). Font-mono, opacity 50%.
 */
export function AuthLegalLinks() {
  return (
    <div className="mt-6 flex items-center justify-center gap-3 font-mono text-[10px] uppercase tracking-wider text-[var(--color-body)] opacity-50">
      <Link
        href="/legal/privacy"
        className="transition-colors hover:text-[var(--color-accent-blue)] hover:opacity-100"
      >
        Privacy
      </Link>
      <span aria-hidden>·</span>
      <Link
        href="/legal/terms"
        className="transition-colors hover:text-[var(--color-accent-blue)] hover:opacity-100"
      >
        Terms
      </Link>
    </div>
  )
}
