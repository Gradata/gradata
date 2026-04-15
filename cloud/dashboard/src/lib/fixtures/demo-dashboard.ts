/**
 * Sample data for the /dashboard "Preview with sample data" demo mode.
 *
 * Used when a user has not yet synced a brain but wants to see what the
 * dashboard will look like once data arrives. Numbers are realistic but
 * clearly synthetic (round week counts, "Demo Brain" label).
 */
import type {
  BrainAnalytics,
  Correction,
  Lesson,
} from '@/types/api'

const now = Date.now()
const daysAgo = (n: number) => new Date(now - n * 86_400_000).toISOString()

export const demoBrain = {
  id: 'demo',
  name: 'Demo Brain',
}

export const demoAnalytics: BrainAnalytics = {
  total_lessons: 23,
  total_corrections: 142,
  graduation_rate: 0.48,
  avg_confidence: 0.82,
  lessons_by_state: { INSTINCT: 7, PATTERN: 5, RULE: 11 },
  corrections_by_severity: { trivial: 34, minor: 62, moderate: 31, major: 12, rewrite: 3 },
  corrections_by_category: {
    TONE: 48,
    ACCURACY: 37,
    FORMATTING: 22,
    COMPLETENESS: 19,
    DRAFTING: 11,
    OTHER: 5,
  },
}

export const demoCorrections: Correction[] = Array.from({ length: 142 }, (_, i) => ({
  id: `demo-c-${i}`,
  brain_id: 'demo',
  severity: (['trivial', 'minor', 'moderate', 'major', 'rewrite'] as const)[i % 5],
  category: (['TONE', 'ACCURACY', 'FORMATTING', 'COMPLETENESS', 'DRAFTING'] as const)[i % 5],
  description: `Sample correction ${i + 1}`,
  draft_preview: null,
  final_preview: null,
  // Weighted toward recent: ~80 in last 7d, ~40 in 7–14d, rest older
  created_at: daysAgo(i < 80 ? (i * 7) / 80 : i < 120 ? 7 + ((i - 80) * 7) / 40 : 14 + ((i - 120) * 30) / 22),
}))

export const demoLessons: Lesson[] = [
  {
    id: 'demo-l-1',
    brain_id: 'demo',
    description: 'Never use em dashes in emails',
    category: 'TONE',
    state: 'RULE',
    confidence: 0.94,
    fire_count: 31,
    created_at: daysAgo(45),
    graduated_at: daysAgo(21),
    correction_count: 8,
    recurrence_blocked: true,
  },
  {
    id: 'demo-l-2',
    brain_id: 'demo',
    description: 'Plan + adversary before implementing',
    category: 'PROCESS',
    state: 'RULE',
    confidence: 0.91,
    fire_count: 24,
    created_at: daysAgo(38),
    graduated_at: daysAgo(14),
    correction_count: 6,
    recurrence_blocked: true,
  },
  {
    id: 'demo-l-3',
    brain_id: 'demo',
    description: 'Use colons over dashes in prose',
    category: 'TONE',
    state: 'PATTERN',
    confidence: 0.78,
    fire_count: 12,
    created_at: daysAgo(20),
    graduated_at: daysAgo(9),
    correction_count: 4,
    last_recurrence_at: daysAgo(2),
  },
  {
    id: 'demo-l-4',
    brain_id: 'demo',
    description: 'Attach case studies as PDF',
    category: 'FORMATTING',
    state: 'RULE',
    confidence: 0.89,
    fire_count: 17,
    created_at: daysAgo(30),
    graduated_at: daysAgo(9),
    correction_count: 5,
    recurrence_blocked: true,
  },
  {
    id: 'demo-l-5',
    brain_id: 'demo',
    description: 'Never commit secrets or API keys',
    category: 'ACCURACY',
    state: 'RULE',
    confidence: 0.97,
    fire_count: 9,
    created_at: daysAgo(52),
    graduated_at: daysAgo(40),
    correction_count: 3,
    recurrence_blocked: true,
  },
  {
    id: 'demo-l-6',
    brain_id: 'demo',
    description: 'Include Calendly link in outreach emails',
    category: 'COMPLETENESS',
    state: 'PATTERN',
    confidence: 0.72,
    fire_count: 5,
    created_at: daysAgo(11),
    graduated_at: daysAgo(5),
    correction_count: 2,
  },
  {
    id: 'demo-l-7',
    brain_id: 'demo',
    description: 'No headline-only filtering for lead lists',
    category: 'PROCESS',
    state: 'INSTINCT',
    confidence: 0.55,
    fire_count: 0,
    created_at: daysAgo(4),
  },
  {
    id: 'demo-l-8',
    brain_id: 'demo',
    description: 'Save lead CSVs to Leads/active/',
    category: 'FORMATTING',
    state: 'INSTINCT',
    confidence: 0.48,
    fire_count: 0,
    created_at: daysAgo(3),
  },
]
