import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  BarChart, Bar, PieChart, Pie, Cell, XAxis, YAxis,
  CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from 'recharts'
import { LoadingSpinner } from '@/components/shared/LoadingSpinner'
import { ErrorState } from '@/components/shared/ErrorState'
import { useApi } from '@/hooks/useApi'
import type { BrainAnalytics } from '@/types/api'

const COLORS = [
  'hsl(263, 70%, 50%)',
  'hsl(160, 60%, 45%)',
  'hsl(30, 80%, 55%)',
  'hsl(280, 65%, 60%)',
  'hsl(340, 75%, 55%)',
]

interface AnalyticsTabProps {
  brainId: string
}

export function AnalyticsTab({ brainId }: AnalyticsTabProps) {
  const { data, loading, error, refetch } = useApi<BrainAnalytics>(
    `/brains/${brainId}/analytics`,
  )

  if (loading) return <LoadingSpinner className="py-10" />
  if (error) return <ErrorState message={error} onRetry={refetch} />
  if (!data) return <ErrorState message="No analytics available" />

  const stateData = Object.entries(data.lessons_by_state).map(([name, value]) => ({
    name, value,
  }))
  const severityData = Object.entries(data.corrections_by_severity).map(([name, value]) => ({
    name, value,
  }))
  const categoryData = Object.entries(data.corrections_by_category).map(([name, value]) => ({
    name, value,
  }))

  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <HeroMetric title="Total Lessons" value={data.total_lessons} />
        <HeroMetric title="Total Corrections" value={data.total_corrections} />
        <HeroMetric title="Graduation Rate" value={`${(data.graduation_rate * 100).toFixed(1)}%`} />
        <HeroMetric title="Avg Confidence" value={`${(data.avg_confidence * 100).toFixed(1)}%`} />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Lessons by State</CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={stateData}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(217, 33%, 17%)" />
                <XAxis dataKey="name" tick={{ fontSize: 12, fill: 'hsl(215, 20%, 65%)' }} />
                <YAxis tick={{ fontSize: 12, fill: 'hsl(215, 20%, 65%)' }} />
                <Tooltip contentStyle={tooltipStyle} />
                <Bar dataKey="value" fill={COLORS[0]} radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Corrections by Severity</CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={250}>
              <PieChart>
                <Pie
                  data={severityData}
                  dataKey="value"
                  nameKey="name"
                  cx="50%"
                  cy="50%"
                  outerRadius={80}
                  label={({ name, percent }) => `${name} ${((percent ?? 0) * 100).toFixed(0)}%`}
                >
                  {severityData.map((_, i) => (
                    <Cell key={i} fill={COLORS[i % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip contentStyle={tooltipStyle} />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="text-sm">Corrections by Category</CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={categoryData}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(217, 33%, 17%)" />
                <XAxis dataKey="name" tick={{ fontSize: 11, fill: 'hsl(215, 20%, 65%)' }} />
                <YAxis tick={{ fontSize: 12, fill: 'hsl(215, 20%, 65%)' }} />
                <Tooltip contentStyle={tooltipStyle} />
                <Bar dataKey="value" fill={COLORS[1]} radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

const tooltipStyle: React.CSSProperties = {
  backgroundColor: 'hsl(222.2, 84%, 4.9%)',
  border: '1px solid hsl(217.2, 32.6%, 17.5%)',
  borderRadius: '6px',
  fontSize: '12px',
}

function HeroMetric({ title, value }: { title: string; value: string | number }) {
  return (
    <Card>
      <CardHeader className="pb-1">
        <CardTitle className="text-sm font-medium text-muted-foreground">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-2xl font-bold">{value}</p>
      </CardContent>
    </Card>
  )
}
