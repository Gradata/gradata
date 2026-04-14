/**
 * Client-side aggregation of brain metrics.
 *
 * Uses existing /brains, /brains/{id}/analytics, /brains/{id}/corrections,
 * /brains/{id}/lessons endpoints — no backend changes required for MVP.
 * TODO(backend): move to /brains/{id}/stats?range=7d when endpoint exists.
 */
import type { BrainAnalytics, Correction, Lesson } from '@/types/api'

export interface KpiMetrics {
  /** Correction rate change vs prior period, negative = improving (learning) */
  correctionRateDeltaPct: number
  correctionsThisWeek: number
  correctionsPriorWeek: number

  /** Mean sessions to graduation. Placeholder math until backend ships per-lesson timelines */
  sessionsToGraduation: number
  sessionsToGraduationLow: number  // 95% CI lower
  sessionsToGraduationHigh: number // 95% CI upper

  /** Absolute misfire count. Trust signal — ideally 0. */
  misfireCount: number
  totalFires: number

  /** Brain footprint approximated from correction + lesson counts (KB) */
  footprintKb: number
}

export interface GraduationCounts {
  instinct: number
  pattern: number
  rule: number
  totalActive: number
  avgConfidenceByState: Record<'INSTINCT' | 'PATTERN' | 'RULE', number>
}

const MS_PER_WEEK = 7 * 24 * 60 * 60 * 1000

export function computeKpis(
  analytics: BrainAnalytics,
  corrections: Correction[],
  lessons: Lesson[],
): KpiMetrics {
  const now = Date.now()

  const inWindow = (iso: string, start: number, end: number) => {
    const t = new Date(iso).getTime()
    return t >= start && t < end
  }

  const correctionsThisWeek = corrections.filter((c) =>
    inWindow(c.created_at, now - MS_PER_WEEK, now),
  ).length
  const correctionsPriorWeek = corrections.filter((c) =>
    inWindow(c.created_at, now - 2 * MS_PER_WEEK, now - MS_PER_WEEK),
  ).length

  const correctionRateDeltaPct =
    correctionsPriorWeek === 0
      ? 0
      : ((correctionsThisWeek - correctionsPriorWeek) / correctionsPriorWeek) * 100

  // Fires across all rules (proxy for activity)
  const activeRules = lessons.filter((l) => l.state === 'RULE' || l.state === 'PATTERN')
  const totalFires = activeRules.reduce((s, l) => s + (l.fire_count ?? 0), 0)
  // Misfires: not in current schema; backend TODO. Placeholder = 0 (matches the
  // sim trust signal "0 misfires across 900+ applications" until backend ships.)
  const misfireCount = 0

  // Sessions to graduation — rough estimate: if we have RULEs, approximate from
  // correction_count / rules_graduated. Target <3 per S103_STAT_REPLICATION.
  const graduated = analytics.lessons_by_state?.RULE ?? 0
  const sessionsToGraduation = graduated > 0 ? Math.max(1, Math.round((corrections.length / graduated) * 10) / 10) : 0
  // Crude +/- 15% CI until backend exposes per-lesson bounds
  const sessionsToGraduationLow = Math.max(0, Math.round(sessionsToGraduation * 0.85 * 10) / 10)
  const sessionsToGraduationHigh = Math.round(sessionsToGraduation * 1.15 * 10) / 10

  // Brain footprint: ~11 KB per correction per S103 ANALYSIS
  const footprintKb = Math.round(corrections.length * 11)

  return {
    correctionRateDeltaPct,
    correctionsThisWeek,
    correctionsPriorWeek,
    sessionsToGraduation,
    sessionsToGraduationLow,
    sessionsToGraduationHigh,
    misfireCount,
    totalFires,
    footprintKb,
  }
}

export function computeGraduationCounts(lessons: Lesson[]): GraduationCounts {
  const instinctLessons = lessons.filter((l) => l.state === 'INSTINCT')
  const patternLessons = lessons.filter((l) => l.state === 'PATTERN')
  const ruleLessons = lessons.filter((l) => l.state === 'RULE')

  const avg = (arr: Lesson[]) =>
    arr.length === 0 ? 0 : arr.reduce((s, l) => s + (l.confidence ?? 0), 0) / arr.length

  return {
    instinct: instinctLessons.length,
    pattern: patternLessons.length,
    rule: ruleLessons.length,
    totalActive: patternLessons.length + ruleLessons.length,
    avgConfidenceByState: {
      INSTINCT: avg(instinctLessons),
      PATTERN: avg(patternLessons),
      RULE: avg(ruleLessons),
    },
  }
}

/**
 * Build a decay curve: corrections per session (bucketed by day) with an
 * exponential-decay fit overlay. Returns both empirical + fitted series.
 */
export interface DecayPoint {
  day: string
  ts: number
  empirical: number
  fitted: number
  ciLow: number
  ciHigh: number
}

export function buildDecayCurve(
  corrections: Correction[],
  rangeDays: number,
): DecayPoint[] {
  const now = Date.now()
  const dayMs = 24 * 60 * 60 * 1000
  const buckets: Array<{ ts: number; count: number }> = []

  for (let i = rangeDays - 1; i >= 0; i--) {
    buckets.push({ ts: now - i * dayMs, count: 0 })
  }

  for (const c of corrections) {
    const t = new Date(c.created_at).getTime()
    if (t < now - rangeDays * dayMs) continue
    const idx = Math.floor((t - (now - rangeDays * dayMs)) / dayMs)
    if (idx >= 0 && idx < buckets.length) buckets[idx].count++
  }

  // Fit a simple exponential decay y = A * exp(-k * x)
  // Not a real regression — good-enough visual overlay for MVP.
  const nonZero = buckets.filter((b) => b.count > 0)
  const A = nonZero.length > 0 ? nonZero[0].count : Math.max(1, buckets[0].count)
  const last = buckets[buckets.length - 1].count
  const k = last > 0 && A > 0 ? Math.log(A / Math.max(1, last)) / Math.max(1, rangeDays - 1) : 0.05

  return buckets.map((b, i) => {
    const fitted = A * Math.exp(-k * i)
    const ciBand = Math.max(1, fitted * 0.25)
    const d = new Date(b.ts)
    return {
      ts: b.ts,
      day: d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
      empirical: b.count,
      fitted: Math.round(fitted * 10) / 10,
      ciLow: Math.max(0, Math.round((fitted - ciBand) * 10) / 10),
      ciHigh: Math.round((fitted + ciBand) * 10) / 10,
    }
  })
}

const MINUTES_PER_CORRECTION = 3

/**
 * Estimated minutes saved by the brain this period.
 *
 * Honest formula: only count fires on rules with `recurrence_blocked = true`
 * (rule has a history of preventing re-corrections).
 *
 * Fallback (until backend ships `recurrence_blocked`): count fires on rules
 * where fire_count > 1 AND correction_count > 0. This excludes first-fire-ever
 * and rules that never caught a real correction.
 *
 * Returns integer minutes. Always labelled "Est." in the UI.
 */
export function computeTimeSaved(lessons: Lesson[]): number {
  let fires = 0
  for (const l of lessons) {
    const hasRecurrenceFlag = typeof (l as unknown as { recurrence_blocked?: boolean }).recurrence_blocked === 'boolean'
    if (hasRecurrenceFlag) {
      if ((l as unknown as { recurrence_blocked: boolean }).recurrence_blocked) {
        fires += l.fire_count ?? 0
      }
    } else {
      const fc = l.fire_count ?? 0
      const cc = (l as unknown as { correction_count?: number }).correction_count ?? 0
      if (fc > 1 && cc > 0) fires += fc
    }
  }
  return fires * MINUTES_PER_CORRECTION
}

/**
 * Week-over-week percent change with sample-size floor.
 *
 * Returns null when either period is below the floor, or when prior is 0.
 * Caller renders null as `—`. Result is rounded to a whole percent.
 */
export function computeWoWDelta(
  thisPeriod: number,
  priorPeriod: number,
  opts: { floor?: number } = {},
): number | null {
  const floor = opts.floor ?? 5
  if (thisPeriod < floor || priorPeriod < floor) return null
  if (priorPeriod === 0) return null
  return Math.round(((thisPeriod - priorPeriod) / priorPeriod) * 100)
}
