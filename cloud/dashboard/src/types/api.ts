export interface Brain {
  id: string
  user_id: string
  name: string
  domain: string
  lesson_count: number
  correction_count: number
  last_sync: string | null
  created_at: string
}

export interface Lesson {
  id: string
  brain_id: string
  description: string
  category: string
  state: 'INSTINCT' | 'PATTERN' | 'RULE'
  confidence: number
  fire_count: number
  created_at: string
}

export interface Correction {
  id: string
  brain_id: string
  severity: 'trivial' | 'minor' | 'moderate' | 'major' | 'rewrite'
  category: string
  description: string
  draft_preview: string | null
  final_preview: string | null
  created_at: string
}

export interface BrainAnalytics {
  total_lessons: number
  total_corrections: number
  graduation_rate: number
  avg_confidence: number
  lessons_by_state: Record<string, number>
  corrections_by_severity: Record<string, number>
  corrections_by_category: Record<string, number>
}

export interface ApiKey {
  id: string
  key_prefix: string
  name: string
  created_at: string
  last_used: string | null
}

export interface ApiKeyCreateResponse {
  id: string
  key: string
  name: string
}

export interface UserProfile {
  id: string
  email: string
  display_name: string | null
  plan: string
  created_at: string
}

export interface PaginatedResponse<T> {
  data: T[]
  total: number
  page: number
  per_page: number
}
