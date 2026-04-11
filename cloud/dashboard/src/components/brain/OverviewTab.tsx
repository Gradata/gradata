import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import type { Brain } from '@/types/api'

interface OverviewTabProps {
  brain: Brain
}

export function OverviewTab({ brain }: OverviewTabProps) {
  const created = new Date(brain.created_at).toLocaleDateString('en-US', {
    year: 'numeric', month: 'long', day: 'numeric',
  })
  const lastSync = brain.last_sync
    ? new Date(brain.last_sync).toLocaleString('en-US', {
        year: 'numeric', month: 'short', day: 'numeric',
        hour: '2-digit', minute: '2-digit',
      })
    : 'Never synced'

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      <MetricCard title="Domain" value={brain.domain} />
      <MetricCard title="Lessons" value={brain.lesson_count.toString()} />
      <MetricCard title="Corrections" value={brain.correction_count.toString()} />
      <MetricCard title="Last Sync" value={lastSync} />
      <Card className="sm:col-span-2 lg:col-span-4">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium text-muted-foreground">Details</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          <Row label="Brain ID" value={brain.id} mono />
          <Row label="Created" value={created} />
          <Row label="Last updated" value={new Date(brain.updated_at).toLocaleString()} />
        </CardContent>
      </Card>
    </div>
  )
}

function MetricCard({ title, value }: { title: string; value: string }) {
  return (
    <Card>
      <CardHeader className="pb-1">
        <CardTitle className="text-sm font-medium text-muted-foreground">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-2xl font-semibold">{value}</p>
      </CardContent>
    </Card>
  )
}

function Row({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex justify-between">
      <span className="text-muted-foreground">{label}</span>
      <span className={mono ? 'font-mono text-xs' : ''}>{value}</span>
    </div>
  )
}
