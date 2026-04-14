import { describe, it, expect } from 'vitest'
import {
  computeKpis,
  computeGraduationCounts,
  buildDecayCurve,
  computeTimeSaved,
  computeWoWDelta,
  computeRuleStreak,
} from '@/lib/analytics-client'
import type { BrainAnalytics, Correction, Lesson } from '@/types/api'

const emptyAnalytics: BrainAnalytics = {
  total_lessons: 0,
  total_corrections: 0,
  graduation_rate: 0,
  avg_confidence: 0,
  lessons_by_state: {},
  corrections_by_severity: {},
  corrections_by_category: {},
}

const mkCorr = (id: string, daysAgo: number): Correction => ({
  id,
  brain_id: 'b1',
  severity: 'minor',
  category: 'TONE',
  description: 'x',
  draft_preview: null,
  final_preview: null,
  created_at: new Date(Date.now() - daysAgo * 24 * 3600_000).toISOString(),
})

const mkLesson = (
  id: string,
  state: Lesson['state'],
  confidence = 0.5,
  fire_count = 0,
): Lesson => ({
  id,
  brain_id: 'b1',
  description: id,
  category: 'TONE',
  state,
  confidence,
  fire_count,
  created_at: new Date().toISOString(),
})

describe('computeKpis', () => {
  it('returns zero-value KPIs for empty inputs without crashing', () => {
    const k = computeKpis(emptyAnalytics, [], [])
    expect(k.correctionRateDeltaPct).toBe(0)
    expect(k.correctionsThisWeek).toBe(0)
    expect(k.correctionsPriorWeek).toBe(0)
    expect(k.sessionsToGraduation).toBe(0)
    expect(k.misfireCount).toBe(0)
    expect(k.totalFires).toBe(0)
    expect(k.footprintKb).toBe(0)
  })

  it('computes negative delta when prior-week was higher than this week', () => {
    // 1 correction in last 7d, 4 corrections in 7-14d window
    const corrections = [
      mkCorr('c1', 1),
      mkCorr('p1', 8),
      mkCorr('p2', 9),
      mkCorr('p3', 10),
      mkCorr('p4', 11),
    ]
    const k = computeKpis(emptyAnalytics, corrections, [])
    expect(k.correctionsThisWeek).toBe(1)
    expect(k.correctionsPriorWeek).toBe(4)
    expect(k.correctionRateDeltaPct).toBeLessThan(0)
    // (1 - 4) / 4 * 100 = -75
    expect(k.correctionRateDeltaPct).toBeCloseTo(-75, 5)
  })

  it('footprint = 11 KB * correction count', () => {
    const corrections = [mkCorr('a', 1), mkCorr('b', 2), mkCorr('c', 3)]
    const k = computeKpis(emptyAnalytics, corrections, [])
    expect(k.footprintKb).toBe(33)
  })

  it('totalFires sums fire_count of RULE + PATTERN lessons only', () => {
    const lessons = [
      mkLesson('r1', 'RULE', 0.95, 10),
      mkLesson('p1', 'PATTERN', 0.7, 5),
      mkLesson('i1', 'INSTINCT', 0.3, 99), // should be ignored
    ]
    const k = computeKpis(emptyAnalytics, [], lessons)
    expect(k.totalFires).toBe(15)
  })
})

describe('computeGraduationCounts', () => {
  it('counts each state and totalActive = pattern + rule', () => {
    const lessons = [
      mkLesson('i1', 'INSTINCT', 0.3),
      mkLesson('i2', 'INSTINCT', 0.4),
      mkLesson('p1', 'PATTERN', 0.6),
      mkLesson('r1', 'RULE', 0.95),
      mkLesson('r2', 'RULE', 0.91),
    ]
    const g = computeGraduationCounts(lessons)
    expect(g.instinct).toBe(2)
    expect(g.pattern).toBe(1)
    expect(g.rule).toBe(2)
    expect(g.totalActive).toBe(3)
    expect(g.avgConfidenceByState.RULE).toBeCloseTo(0.93, 2)
  })

  it('avg confidence is 0 when state has no lessons', () => {
    const g = computeGraduationCounts([])
    expect(g.avgConfidenceByState.INSTINCT).toBe(0)
    expect(g.avgConfidenceByState.PATTERN).toBe(0)
    expect(g.avgConfidenceByState.RULE).toBe(0)
  })
})

describe('buildDecayCurve', () => {
  it.each([
    [7, 7],
    [30, 30],
    [90, 90],
  ])('returns %i buckets for %i-day range', (days, expected) => {
    const curve = buildDecayCurve([], days)
    expect(curve).toHaveLength(expected)
  })

  it('each bucket has empirical, fitted, ciLow, ciHigh fields', () => {
    const curve = buildDecayCurve([mkCorr('a', 1)], 7)
    expect(curve[0]).toHaveProperty('empirical')
    expect(curve[0]).toHaveProperty('fitted')
    expect(curve[0]).toHaveProperty('ciLow')
    expect(curve[0]).toHaveProperty('ciHigh')
    expect(curve[0]).toHaveProperty('day')
  })
})

describe('computeTimeSaved', () => {
  it('returns 0 minutes for no lessons', () => {
    expect(computeTimeSaved([])).toBe(0)
  })

  it('counts only fires on rules with recurrence_blocked=true (honest formula)', () => {
    const lessons = [
      mkLesson('a', 'RULE', 0.9, 4),
      mkLesson('b', 'RULE', 0.9, 2),
    ]
    ;(lessons[0] as any).recurrence_blocked = true
    ;(lessons[1] as any).recurrence_blocked = false
    // honest: 3 min × 4 fires on rule a = 12
    expect(computeTimeSaved(lessons)).toBe(12)
  })

  it('falls back to fire_count > 1 AND correction_count > 0 when recurrence_blocked missing', () => {
    const lessons = [
      mkLesson('a', 'RULE', 0.9, 5),
      mkLesson('b', 'RULE', 0.9, 1),
      mkLesson('c', 'RULE', 0.9, 3),
    ]
    ;(lessons[0] as any).correction_count = 2 // counts: 5 fires
    ;(lessons[1] as any).correction_count = 1 // excluded: fire_count not > 1
    ;(lessons[2] as any).correction_count = 0 // excluded: correction_count 0
    // 3 min × 5 fires = 15
    expect(computeTimeSaved(lessons)).toBe(15)
  })

  it('returns whole minutes, floored/rounded to nearest whole minute', () => {
    const lessons = [mkLesson('a', 'RULE', 0.9, 7)]
    ;(lessons[0] as any).recurrence_blocked = true
    expect(computeTimeSaved(lessons)).toBe(21)
  })
})

describe('computeWoWDelta', () => {
  it('returns null when either week below sample-size floor', () => {
    expect(computeWoWDelta(3, 10, { floor: 5 })).toBeNull()
    expect(computeWoWDelta(10, 4, { floor: 5 })).toBeNull()
    expect(computeWoWDelta(2, 2, { floor: 5 })).toBeNull()
  })

  it('returns percent change when both weeks meet floor', () => {
    expect(computeWoWDelta(12, 10, { floor: 5 })).toBe(20)
    expect(computeWoWDelta(8, 10, { floor: 5 })).toBe(-20)
  })

  it('handles zero prior with this-week positive as null (undefined ratio)', () => {
    expect(computeWoWDelta(10, 0, { floor: 5 })).toBeNull()
  })

  it('uses default floor of 5 when no options passed', () => {
    expect(computeWoWDelta(4, 4)).toBeNull()
    expect(computeWoWDelta(6, 5)).toBe(20)
  })

  it('rounds to whole percent', () => {
    expect(computeWoWDelta(10, 6, { floor: 5 })).toBe(67)
  })
})

describe('computeRuleStreak', () => {
  const now = () => new Date().toISOString()
  const daysAgo = (n: number) => new Date(Date.now() - n * 86_400_000).toISOString()

  it('returns null when no timestamps present', () => {
    const l = mkLesson('a', 'RULE', 0.9, 0)
    expect(computeRuleStreak(l)).toBeNull()
  })

  it('uses last_recurrence_at when present', () => {
    const l = mkLesson('a', 'RULE', 0.9, 0)
    ;(l as any).last_recurrence_at = daysAgo(14)
    expect(computeRuleStreak(l)).toBe(14)
  })

  it('falls back to graduated_at when no recurrences', () => {
    const l = mkLesson('a', 'RULE', 0.9, 0)
    ;(l as any).graduated_at = daysAgo(21)
    expect(computeRuleStreak(l)).toBe(21)
  })

  it('prefers max of last_recurrence_at and graduated_at', () => {
    const l = mkLesson('a', 'RULE', 0.9, 0)
    ;(l as any).last_recurrence_at = daysAgo(2)
    ;(l as any).graduated_at = daysAgo(30)
    expect(computeRuleStreak(l)).toBe(2)
  })

  it('returns 0 for same day', () => {
    const l = mkLesson('a', 'RULE', 0.9, 0)
    ;(l as any).graduated_at = now()
    expect(computeRuleStreak(l)).toBe(0)
  })
})
