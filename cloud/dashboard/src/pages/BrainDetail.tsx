import { useParams } from 'react-router-dom'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { LoadingSpinner } from '@/components/shared/LoadingSpinner'
import { ErrorState } from '@/components/shared/ErrorState'
import { useApi } from '@/hooks/useApi'
import type { Brain } from '@/types/api'
import { OverviewTab } from '@/components/brain/OverviewTab'
import { LessonsTab } from '@/components/brain/LessonsTab'
import { CorrectionsTab } from '@/components/brain/CorrectionsTab'
import { AnalyticsTab } from '@/components/brain/AnalyticsTab'

export function BrainDetail() {
  const { id } = useParams<{ id: string }>()
  const { data: brain, loading, error, refetch } = useApi<Brain>(`/brains/${id}`)

  if (loading) return <LoadingSpinner className="py-20" />
  if (error) return <ErrorState message={error} onRetry={refetch} />
  if (!brain || !id) return <ErrorState message="Brain not found" />

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{brain.name}</h1>
        <p className="text-sm text-muted-foreground mt-1">{brain.domain}</p>
      </div>

      <Tabs defaultValue="overview">
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="lessons">Lessons</TabsTrigger>
          <TabsTrigger value="corrections">Corrections</TabsTrigger>
          <TabsTrigger value="analytics">Analytics</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="mt-4">
          <OverviewTab brain={brain} />
        </TabsContent>

        <TabsContent value="lessons" className="mt-4">
          <LessonsTab brainId={id} />
        </TabsContent>

        <TabsContent value="corrections" className="mt-4">
          <CorrectionsTab brainId={id} />
        </TabsContent>

        <TabsContent value="analytics" className="mt-4">
          <AnalyticsTab brainId={id} />
        </TabsContent>
      </Tabs>
    </div>
  )
}
