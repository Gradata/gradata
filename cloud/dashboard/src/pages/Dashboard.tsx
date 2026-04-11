import { Link } from 'react-router-dom'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { LoadingSpinner } from '@/components/shared/LoadingSpinner'
import { ErrorState } from '@/components/shared/ErrorState'
import { EmptyState } from '@/components/shared/EmptyState'
import { useApi } from '@/hooks/useApi'
import type { Brain } from '@/types/api'

export function Dashboard() {
  const { data: brains, loading, error, refetch } = useApi<Brain[]>('/brains')

  if (loading) return <LoadingSpinner className="py-20" />
  if (error) return <ErrorState message={error} onRetry={refetch} />
  if (!brains?.length) {
    return (
      <EmptyState
        title="No brains yet"
        description="Connect your first brain via the SDK to see it here."
        icon={
          <svg className="h-12 w-12" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round"
              d="M9.75 3.104v5.714a2.25 2.25 0 01-.659 1.591L5 14.5M9.75 3.104c-.251.023-.501.05-.75.082m.75-.082a24.301 24.301 0 014.5 0m0 0v5.714c0 .597.237 1.17.659 1.591L19.8 15.3M14.25 3.104c.251.023.501.05.75.082M19.8 15.3l-1.57.393A9.065 9.065 0 0112 15a9.065 9.065 0 00-6.23.693L5 14.5m14.8.8l1.402 1.402c1.232 1.232.65 3.318-1.067 3.611A48.653 48.653 0 0112 21a48.653 48.653 0 01-7.562-.813c-1.717-.293-2.3-2.379-1.067-3.61L5 14.5" />
          </svg>
        }
      />
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Your Brains</h1>
        <p className="text-sm text-muted-foreground mt-1">
          {brains.length} brain{brains.length !== 1 ? 's' : ''} connected
        </p>
      </div>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {brains.map((brain) => (
          <BrainCard key={brain.id} brain={brain} />
        ))}
      </div>
    </div>
  )
}

function BrainCard({ brain }: { brain: Brain }) {
  const lastSync = brain.last_sync
    ? new Date(brain.last_sync).toLocaleDateString()
    : 'Never'

  return (
    <Link to={`/dashboard/brains/${brain.id}`}>
      <Card className="transition-colors hover:border-primary/50 cursor-pointer">
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <CardTitle className="text-base">{brain.name}</CardTitle>
            <Badge variant="outline" className="text-xs">{brain.domain}</Badge>
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-3 gap-2 text-center">
            <Stat label="Lessons" value={brain.lesson_count} />
            <Stat label="Corrections" value={brain.correction_count} />
            <Stat label="Last sync" value={lastSync} />
          </div>
        </CardContent>
      </Card>
    </Link>
  )
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div>
      <p className="text-lg font-semibold">{value}</p>
      <p className="text-xs text-muted-foreground">{label}</p>
    </div>
  )
}
