import Link from 'next/link'
import { GlassCard } from '@/components/layout/GlassCard'
import { computeRuleStreak } from '@/lib/analytics-client'
import type { Lesson } from '@/types/api'

type RuleStatus = 'clean-durable' | 'clean-new' | 'recurred' | 'unknown'

function statusFor(lesson: Lesson): { status: RuleStatus; streakDays: number | null; recurredDays: number | null } {
  const streakDays = computeRuleStreak(lesson)
  const lastRec = lesson.last_recurrence_at
  const lastGrad = lesson.graduated_at
  const recMs =
    typeof lastRec === 'string' && lastRec.length > 0 ? new Date(lastRec).getTime() : null
  const gradMs =
    typeof lastGrad === 'string' && lastGrad.length > 0 ? new Date(lastGrad).getTime() : null
  const recurredDays =
    recMs === null ? null : Math.max(0, Math.floor((Date.now() - recMs) / 86_400_000))

  if (streakDays === null) return { status: 'unknown', streakDays: null, recurredDays: null }
  // Only flag as recurred if the recurrence is the LATEST event. If the rule
  // was re-graduated AFTER slipping, the recurrence is stale and the streak
  // (which already starts from graduated_at) tells the truth.
  if (recurredDays !== null && recurredDays < 7 && (gradMs === null || recMs! >= gradMs)) {
    return { status: 'recurred', streakDays, recurredDays }
  }
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
  if (s.status === 'unknown') return 'just learned'
  if (s.status === 'recurred' && s.recurredDays !== null) {
    return s.recurredDays === 0 ? 'slipped today' : `slipped ${s.recurredDays}d ago`
  }
  if (s.streakDays !== null) {
    if (s.streakDays === 0) return 'graduated today'
    return `${s.streakDays} days holding`
  }
  return 'just learned'
}

const STATE_LABEL: Record<string, string> = {
  RULE: 'Graduated',
  PATTERN: 'Learning',
  INSTINCT: 'Watching',
}

export function ActiveRulesPanel({ lessons }: { lessons: Lesson[] }) {
  const rules = lessons
    .filter((l) => l.state === 'RULE' || l.state === 'PATTERN')
    .sort((a, b) => (b.confidence ?? 0) - (a.confidence ?? 0))
    .slice(0, 8)

  return (
    <GlassCard gradTop>
      <div className="mb-5 flex items-baseline justify-between">
        <h3 className="text-[15px] font-semibold">Your Rules</h3>
        <span className="text-[12px] text-[var(--color-body)]">what your AI learned</span>
      </div>
      <ul className="space-y-3">
        {rules.length === 0 && (
          <li className="text-[13px] text-[var(--color-body)]">
            Nothing graduated yet. Keep correcting — rules emerge after your AI sees a pattern 3+ times.
          </li>
        )}
        {rules.map((rule) => {
          const s = statusFor(rule)
          const stateLabel = STATE_LABEL[rule.state] ?? rule.state
          return (
            <li key={rule.id} data-rule-row className="flex items-start gap-3">
              {glyph(s.status)}
              <div className="flex-1 min-w-0">
                <div className="text-[13px]">{rule.description}</div>
                <div className="mt-0.5 flex flex-wrap gap-x-2 gap-y-0.5 text-[11px] text-[var(--color-body)]">
                  <span>{stateLabel}</span>
                  <span>·</span>
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
          See all your rules →
        </Link>
      </div>
    </GlassCard>
  )
}
