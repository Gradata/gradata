import Link from 'next/link'
import { GlassCard } from '@/components/layout/GlassCard'
import { computeRuleStreak } from '@/lib/analytics-client'
import type { Lesson } from '@/types/api'

type RuleStatus = 'clean-durable' | 'clean-new' | 'recurred' | 'unknown'

function statusFor(lesson: Lesson): { status: RuleStatus; streakDays: number | null; recurredDays: number | null } {
  const streakDays = computeRuleStreak(lesson)
  const lastRec = (lesson as unknown as { last_recurrence_at?: string }).last_recurrence_at
  const recurredDays = lastRec ? Math.floor((Date.now() - new Date(lastRec).getTime()) / 86_400_000) : null

  if (streakDays === null) return { status: 'unknown', streakDays: null, recurredDays: null }
  if (recurredDays !== null && recurredDays < 7) return { status: 'recurred', streakDays, recurredDays }
  if (streakDays >= 7) return { status: 'clean-durable', streakDays, recurredDays }
  return { status: 'clean-new', streakDays, recurredDays }
}

function glyph(status: RuleStatus): React.ReactNode {
  const base = 'mt-1.5 h-2 w-2 rounded-full'
  if (status === 'clean-durable')
    return <span data-glyph="clean-durable" className={`${base} bg-[var(--color-success)]`} aria-hidden />
  if (status === 'clean-new')
    return <span data-glyph="clean-new" className={`${base} border border-[var(--color-success)]`} aria-hidden />
  if (status === 'recurred')
    return (
      <span data-glyph="recurred" className={`${base} relative overflow-hidden`} aria-hidden>
        <span className="absolute inset-y-0 left-0 w-1 bg-[var(--color-accent-blue)]" />
        <span className="absolute inset-y-0 right-0 w-1 bg-transparent border border-[var(--color-accent-blue)]" />
      </span>
    )
  return <span data-glyph="unknown" className={`${base} bg-[var(--color-body)]/30`} aria-hidden />
}

function suffix(s: { status: RuleStatus; streakDays: number | null; recurredDays: number | null }): string {
  if (s.status === 'unknown') return '—'
  if (s.status === 'recurred' && s.recurredDays !== null) return `recurred ${s.recurredDays}d ago`
  if (s.streakDays !== null) return `${s.streakDays}d clean`
  return '—'
}

export function ActiveRulesPanel({ lessons }: { lessons: Lesson[] }) {
  const rules = lessons
    .filter((l) => l.state === 'RULE' || l.state === 'PATTERN')
    .sort((a, b) => (b.confidence ?? 0) - (a.confidence ?? 0))
    .slice(0, 8)

  return (
    <GlassCard gradTop>
      <div className="mb-5 flex items-baseline justify-between">
        <h3 className="text-[15px] font-semibold">Active Rules</h3>
        <span className="text-[12px] text-[var(--color-body)]">top 8</span>
      </div>
      <ul className="space-y-3">
        {rules.length === 0 && (
          <li className="text-[13px] text-[var(--color-body)]">
            No graduated rules yet. Keep correcting and patterns will emerge.
          </li>
        )}
        {rules.map((rule) => {
          const s = statusFor(rule)
          return (
            <li key={rule.id} data-rule-row className="flex items-start gap-3">
              {glyph(s.status)}
              <div className="flex-1 min-w-0">
                <div className="text-[13px]">{rule.description}</div>
                <div className="mt-0.5 flex flex-wrap gap-x-3 gap-y-0.5 font-mono text-[10px] text-[var(--color-body)]">
                  <span>{rule.category}</span>
                  <span className="uppercase">{rule.state}</span>
                  <span>{(rule.confidence ?? 0).toFixed(2)}</span>
                  <span>{suffix(s)}</span>
                </div>
              </div>
            </li>
          )
        })}
      </ul>
      <div className="mt-5 text-right">
        <Link
          href="/rules"
          className="text-[12px] text-[var(--color-accent-blue)] hover:underline"
        >
          See all rules →
        </Link>
      </div>
    </GlassCard>
  )
}
