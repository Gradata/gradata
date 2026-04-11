import { useState } from 'react'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select'
import { LoadingSpinner } from '@/components/shared/LoadingSpinner'
import { ErrorState } from '@/components/shared/ErrorState'
import { EmptyState } from '@/components/shared/EmptyState'
import { useApi } from '@/hooks/useApi'
import type { Correction } from '@/types/api'

const SEVERITIES = ['ALL', 'trivial', 'minor', 'moderate', 'major', 'rewrite'] as const

const severityColor: Record<string, string> = {
  trivial: 'bg-muted text-muted-foreground',
  minor: 'bg-blue-500/10 text-blue-400',
  moderate: 'bg-yellow-500/10 text-yellow-400',
  major: 'bg-orange-500/10 text-orange-400',
  rewrite: 'bg-red-500/10 text-red-400',
}

interface CorrectionsTabProps {
  brainId: string
}

export function CorrectionsTab({ brainId }: CorrectionsTabProps) {
  const [severity, setSeverity] = useState('ALL')
  const [category, setCategory] = useState('')

  const params: Record<string, string | undefined> = {
    severity: severity === 'ALL' ? undefined : severity,
    category: category || undefined,
  }

  const { data: corrections, loading, error, refetch } = useApi<Correction[]>(
    `/brains/${brainId}/corrections`,
    params,
  )

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-3">
        <Select value={severity} onValueChange={(v) => v && setSeverity(v)}>
          <SelectTrigger className="w-36">
            <SelectValue placeholder="Severity" />
          </SelectTrigger>
          <SelectContent>
            {SEVERITIES.map((s) => (
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
      </div>

      {loading && <LoadingSpinner className="py-10" />}
      {error && <ErrorState message={error} onRetry={refetch} />}
      {!loading && !error && !corrections?.length && (
        <EmptyState title="No corrections" description="No corrections match your filters." />
      )}
      {!loading && !error && corrections && corrections.length > 0 && (
        <div className="space-y-3">
          {corrections.map((c) => (
            <CorrectionCard key={c.id} correction={c} />
          ))}
        </div>
      )}
    </div>
  )
}

function CorrectionCard({ correction }: { correction: Correction }) {
  const date = new Date(correction.created_at).toLocaleDateString('en-US', {
    month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
  })

  return (
    <Card>
      <CardHeader className="pb-2 flex-row items-center gap-3 space-y-0">
        <Badge className={`text-xs ${severityColor[correction.severity] ?? ''}`}>
          {correction.severity}
        </Badge>
        <Badge variant="outline" className="text-xs">{correction.category}</Badge>
        <span className="ml-auto text-xs text-muted-foreground">{date}</span>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-sm">{correction.description}</p>
        {(correction.draft_text || correction.final_text) && (
          <div className="grid gap-3 sm:grid-cols-2">
            {correction.draft_text && (
              <div className="rounded-md bg-red-500/5 p-3">
                <p className="mb-1 text-xs font-medium text-red-400">Draft</p>
                <p className="text-xs text-muted-foreground whitespace-pre-wrap">
                  {correction.draft_text}
                </p>
              </div>
            )}
            {correction.final_text && (
              <div className="rounded-md bg-green-500/5 p-3">
                <p className="mb-1 text-xs font-medium text-green-400">Final</p>
                <p className="text-xs text-muted-foreground whitespace-pre-wrap">
                  {correction.final_text}
                </p>
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
