import { useState } from 'react'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select'
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/table'
import { LoadingSpinner } from '@/components/shared/LoadingSpinner'
import { ErrorState } from '@/components/shared/ErrorState'
import { EmptyState } from '@/components/shared/EmptyState'
import { useApi } from '@/hooks/useApi'
import type { Lesson } from '@/types/api'

const STATES = ['ALL', 'INSTINCT', 'PATTERN', 'RULE'] as const

const stateBadgeVariant: Record<string, 'default' | 'secondary' | 'outline'> = {
  INSTINCT: 'outline',
  PATTERN: 'secondary',
  RULE: 'default',
}

interface LessonsTabProps {
  brainId: string
}

export function LessonsTab({ brainId }: LessonsTabProps) {
  const [stateFilter, setStateFilter] = useState('ALL')
  const [category, setCategory] = useState('')
  const [minConfidence, setMinConfidence] = useState('')

  const params: Record<string, string | undefined> = {
    state: stateFilter === 'ALL' ? undefined : stateFilter,
    category: category || undefined,
    min_confidence: minConfidence || undefined,
  }

  const { data: lessons, loading, error, refetch } = useApi<Lesson[]>(
    `/brains/${brainId}/lessons`,
    params,
  )

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-3">
        <Select value={stateFilter} onValueChange={(v) => v && setStateFilter(v)}>
          <SelectTrigger className="w-36">
            <SelectValue placeholder="State" />
          </SelectTrigger>
          <SelectContent>
            {STATES.map((s) => (
              <SelectItem key={s} value={s}>{s}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Input
          placeholder="Category"
          value={category}
          onChange={(e) => setCategory(e.target.value)}
          className="w-40"
        />
        <Input
          placeholder="Min confidence"
          type="number"
          step="0.1"
          min="0"
          max="1"
          value={minConfidence}
          onChange={(e) => setMinConfidence(e.target.value)}
          className="w-36"
        />
      </div>

      {loading && <LoadingSpinner className="py-10" />}
      {error && <ErrorState message={error} onRetry={refetch} />}
      {!loading && !error && !lessons?.length && (
        <EmptyState title="No lessons" description="No lessons match your filters." />
      )}
      {!loading && !error && lessons && lessons.length > 0 && (
        <LessonsTable lessons={lessons} />
      )}
    </div>
  )
}

function LessonsTable({ lessons }: { lessons: Lesson[] }) {
  return (
    <div className="rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Description</TableHead>
            <TableHead className="w-28">Category</TableHead>
            <TableHead className="w-24">State</TableHead>
            <TableHead className="w-24 text-right">Confidence</TableHead>
            <TableHead className="w-20 text-right">Fires</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {lessons.map((lesson) => (
            <TableRow key={lesson.id}>
              <TableCell className="max-w-md truncate text-sm">
                {lesson.description}
              </TableCell>
              <TableCell>
                <Badge variant="outline" className="text-xs">{lesson.category}</Badge>
              </TableCell>
              <TableCell>
                <Badge variant={stateBadgeVariant[lesson.state] ?? 'outline'} className="text-xs">
                  {lesson.state}
                </Badge>
              </TableCell>
              <TableCell className="text-right font-mono text-sm">
                {(lesson.confidence * 100).toFixed(0)}%
              </TableCell>
              <TableCell className="text-right font-mono text-sm">
                {lesson.fire_count}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}
