/**
 * Plan tiers per S104 Stripe products:
 * - Free: metrics only
 * - Cloud: $29/mo, rules + trends, single user
 * - Team: $99/mo, leaderboard + team analytics, 15+ seats
 *
 * `rank` is used for comparisons (e.g. can this user access a Team-only feature?).
 */
export type PlanTier = 'free' | 'cloud' | 'team' | 'enterprise'

interface PlanMeta {
  name: string
  price: string
  priceUnit?: string
  rank: number
  features: string[]
  /** Color class for badge + CTAs */
  tone: 'neutral' | 'blue' | 'violet' | 'gold'
}

export const PLANS: Record<PlanTier, PlanMeta> = {
  free: {
    name: 'Free',
    price: '$0',
    priceUnit: '/mo',
    rank: 0,
    features: ['Metrics only', 'Single brain', 'Community support'],
    tone: 'neutral',
  },
  cloud: {
    name: 'Cloud',
    price: '$29',
    priceUnit: '/mo',
    rank: 1,
    features: ['Rules + trends', 'Meta-rules', 'Self-healing patches', 'Email support'],
    tone: 'blue',
  },
  team: {
    name: 'Team',
    price: '$99',
    priceUnit: '/mo',
    rank: 2,
    features: ['Everything in Cloud', 'Leaderboard', 'Team analytics', '15+ seats'],
    tone: 'violet',
  },
  enterprise: {
    name: 'Enterprise',
    price: 'Custom',
    rank: 3,
    features: ['SSO + SAML', 'On-prem option', 'Dedicated support', 'Custom SLAs'],
    tone: 'gold',
  },
}

const BADGE_STYLE: Record<PlanMeta['tone'], string> = {
  neutral: 'bg-white/[0.06] text-[var(--color-body)]',
  blue: 'bg-[rgba(58,130,255,0.12)] text-[var(--color-accent-blue)]',
  violet: 'bg-[rgba(124,58,237,0.12)] text-[var(--color-accent-violet)]',
  gold: 'bg-[rgba(234,179,8,0.12)] text-[var(--color-warning)]',
}

export function PlanBadge({ tier }: { tier: PlanTier }) {
  const plan = PLANS[tier] ?? PLANS.free
  return (
    <span
      className={`rounded-[0.25rem] px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wider ${BADGE_STYLE[plan.tone]}`}
    >
      {plan.name}
    </span>
  )
}

/**
 * "Upgrade to unlock" gate. Wraps children with a blur + CTA when the
 * current plan's rank is below `requires`. Renders children normally otherwise.
 */
export function PlanGate({
  current,
  requires,
  children,
  featureName,
}: {
  current: PlanTier
  requires: PlanTier
  children: React.ReactNode
  featureName: string
}) {
  if (PLANS[current].rank >= PLANS[requires].rank) return <>{children}</>

  return (
    <div className="relative">
      <div className="pointer-events-none select-none opacity-30 blur-[2px]">{children}</div>
      <div className="absolute inset-0 flex items-center justify-center">
        <div className="max-w-sm rounded-[0.5rem] border border-[var(--color-border-hover)] bg-[rgba(21,29,48,0.9)] p-5 text-center backdrop-blur-md">
          <div className="mb-2 flex justify-center">
            <PlanBadge tier={requires} />
          </div>
          <p className="mb-3 text-[13px]">
            <span className="font-semibold">{featureName}</span> is available on the {PLANS[requires].name} plan
          </p>
          <a
            href="/settings"
            className="inline-block rounded-[0.5rem] bg-gradient-brand px-4 py-2 text-[13px] font-medium text-white transition-all hover:opacity-90"
          >
            Upgrade to {PLANS[requires].name}
          </a>
        </div>
      </div>
    </div>
  )
}
