import { useState, useEffect } from 'react'
import { dashboardAPI } from '../services/api'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/Card'
import { Badge } from '../components/Badge'
import {
  FileText,
  Filter,
  Sparkles,
  Mail,
  Clock,
  RefreshCw,
  AlertCircle,
} from 'lucide-react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'

const COLORS = ['#a1a1aa', '#22c55e', '#eab308', '#3b82f6', '#a855f7', '#ef4444']

function ChartTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  const value = payload[0]?.value
  return (
    <div className="rounded-lg border border-zinc-600 bg-zinc-900/95 px-4 py-3 shadow-xl backdrop-blur">
      <p className="text-zinc-400 text-xs font-medium uppercase tracking-wider">{label}</p>
      <p className="text-white text-lg font-semibold mt-0.5">{value} posts</p>
    </div>
  )
}

function StatCard({ title, value, icon: Icon, subtitle, accent }) {
  return (
    <Card className="overflow-hidden transition-shadow hover:shadow-md">
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">{title}</CardTitle>
        {Icon && (
          <span className={`rounded-lg p-2 ${accent || 'bg-muted'}`}>
            <Icon className="h-4 w-4 text-muted-foreground" />
          </span>
        )}
      </CardHeader>
      <CardContent>
        <div className="text-3xl font-bold tracking-tight">{value}</div>
        {subtitle != null && (
          <p className="text-xs text-muted-foreground mt-2 leading-relaxed">{subtitle}</p>
        )}
      </CardContent>
    </Card>
  )
}

function Dashboard() {
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const fetchStats = async () => {
    try {
      setLoading(true)
      const data = await dashboardAPI.getStats()
      setStats(data)
      setError(null)
    } catch (err) {
      setError(err?.response?.data?.detail || 'Failed to load stats')
      setStats(null)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchStats()
  }, [])

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  if (error) {
    return (
      <Card className="border-destructive/40">
        <CardContent className="pt-6">
          <div className="flex items-center gap-3 text-destructive">
            <AlertCircle className="h-5 w-5 shrink-0" />
            <span className="font-medium">{error}</span>
          </div>
          <p className="text-sm text-muted-foreground mt-3 max-w-lg">
            Ensure MongoDB is running and MONGODB_URI is set (e.g. in .env). Start the API with: uvicorn main:app --port 8000
          </p>
          <button
            onClick={fetchStats}
            className="mt-5 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90 transition-opacity"
          >
            Retry
          </button>
        </CardContent>
      </Card>
    )
  }

  const raw = stats?.raw_posts ?? {}
  const byStatus = raw.by_status ?? {}
  const totalRaw = raw.total ?? 0
  const qualified = stats?.qualified_leads_count ?? 0
  const queue = stats?.email_queue ?? {}
  const pipeline = stats?.pipeline_state ?? {}

  const chartData = Object.entries(byStatus).map(([name, value]) => ({ name, value }))

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold tracking-tight">Dashboard</h2>
        <button
          onClick={fetchStats}
          className="inline-flex items-center gap-2 rounded-lg border border-border bg-card px-4 py-2 text-sm font-medium text-foreground hover:bg-accent transition-colors"
        >
          <RefreshCw className="h-4 w-4" />
          Refresh
        </button>
      </div>

      <div className="grid gap-5 md:grid-cols-2 lg:grid-cols-4">
        <StatCard
          title="Posts scraped"
          value={totalRaw}
          icon={FileText}
          subtitle="Total in raw_posts"
        />
        <StatCard
          title="Passed static filter"
          value={byStatus.filtered ?? 0}
          icon={Filter}
          subtitle="Eligible for AI"
        />
        <StatCard
          title="AI qualified"
          value={qualified}
          icon={Sparkles}
          subtitle="Ready for email"
        />
        <StatCard
          title="Email queue"
          value={(queue.pending ?? 0) + (queue.sent ?? 0) + (queue.failed ?? 0)}
          icon={Mail}
          subtitle={`${queue.pending ?? 0} pending · ${queue.sent ?? 0} sent · ${queue.failed ?? 0} failed`}
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Raw posts by status</CardTitle>
            <CardDescription>Pipeline stage distribution</CardDescription>
          </CardHeader>
          <CardContent>
            {chartData.length > 0 ? (
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={chartData} margin={{ top: 16, right: 16, left: 0, bottom: 8 }}>
                  <XAxis
                    dataKey="name"
                    tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 12 }}
                    axisLine={{ stroke: 'hsl(var(--border))' }}
                    tickLine={{ stroke: 'hsl(var(--border))' }}
                  />
                  <YAxis
                    tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 12 }}
                    axisLine={false}
                    tickLine={{ stroke: 'hsl(var(--border))' }}
                  />
                  <Tooltip content={<ChartTooltip />} cursor={{ fill: 'hsl(var(--muted))', radius: 4 }} />
                  <Bar dataKey="value" radius={[6, 6, 0, 0]} maxBarSize={56}>
                    {chartData.map((_, i) => (
                      <Cell key={i} fill={COLORS[i % COLORS.length]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex flex-col items-center justify-center py-16 text-center">
                <p className="text-muted-foreground text-sm">No data yet.</p>
                <p className="text-muted-foreground/80 text-xs mt-1">Run ingestion to see distribution.</p>
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Pipeline state</CardTitle>
            <CardDescription>Last run and cursors</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center gap-3 rounded-lg bg-muted/50 px-3 py-2.5">
              <Clock className="h-4 w-4 text-muted-foreground shrink-0" />
              <div className="min-w-0">
                <span className="text-xs text-muted-foreground block">Last run</span>
                <span className="text-sm font-medium truncate block">
                  {pipeline.lastRunAt
                    ? new Date(pipeline.lastRunAt).toLocaleString()
                    : 'Never'}
                </span>
              </div>
            </div>
            {pipeline.cursors && Object.keys(pipeline.cursors).length > 0 && (
              <div className="text-sm space-y-2">
                <span className="text-muted-foreground">Cursors</span>
                <div className="flex flex-wrap gap-2">
                  {Object.entries(pipeline.cursors).map(([platform, ts]) => (
                    <Badge key={platform} variant="secondary" className="font-mono text-xs">
                      {platform}: {typeof ts === 'number' ? new Date(ts * 1000).toISOString().slice(0, 10) : String(ts)}
                    </Badge>
                  ))}
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

export default Dashboard
