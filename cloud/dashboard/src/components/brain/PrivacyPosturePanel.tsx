import { GlassCard } from '@/components/layout/GlassCard'

/**
 * Trust signal surface per SIM_A §5A + SIM_B §3: explicit privacy
 * posture. Raw corrections never leave the device; the dashboard is
 * an observability lens, not the system of record.
 *
 * Differentiator vs Mem0/Letta — neither exposes privacy guarantees.
 */
export function PrivacyPosturePanel({
  footprintKb,
  injectionCap = 10,
  epsilonBudget,
}: {
  footprintKb: number
  injectionCap?: number
  epsilonBudget?: number
}) {
  const items: Array<{ label: string; value: string; tone: 'pos' | 'neu' }> = [
    {
      label: 'Raw corrections',
      value: 'Never leave your device',
      tone: 'pos',
    },
    {
      label: 'What cloud stores',
      value: 'Synthesized principles only',
      tone: 'pos',
    },
    {
      label: 'Injection cap',
      value: `max ${injectionCap} rules per session`,
      tone: 'neu',
    },
    {
      label: 'Brain footprint',
      value: footprintKb >= 1024
        ? `${(footprintKb / 1024).toFixed(1)} MB on device`
        : `${footprintKb} KB on device`,
      tone: 'neu',
    },
    ...(epsilonBudget !== undefined
      ? [{ label: 'Privacy budget (ε)', value: `${epsilonBudget.toFixed(2)}`, tone: 'neu' as const }]
      : []),
  ]

  return (
    <GlassCard gradTop>
      <div className="mb-5 flex items-baseline justify-between">
        <h3 className="text-[15px] font-semibold">Privacy Posture</h3>
        <span className="text-[12px] text-[var(--color-body)]">local-first</span>
      </div>
      <ul className="space-y-3">
        {items.map((item) => (
          <li key={item.label} className="flex items-start gap-3">
            <span
              className={`mt-1 h-2 w-2 shrink-0 rounded-full ${
                item.tone === 'pos'
                  ? 'bg-[var(--color-success)]'
                  : 'bg-[var(--color-accent-blue)]'
              }`}
              aria-hidden
            />
            <div className="flex-1 flex items-baseline justify-between gap-3">
              <span className="text-[13px] text-[var(--color-body)]">{item.label}</span>
              <span className="text-right text-[13px]">{item.value}</span>
            </div>
          </li>
        ))}
      </ul>
    </GlassCard>
  )
}
