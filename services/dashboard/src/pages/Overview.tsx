import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Legend,
} from 'recharts'
import { getStats, getHealth, type Stats } from '../api'
import { PageHeader, Card, Badge, Button, LoadingState, Alert } from '../components/ui'

/* Refined palette: softer, harmonious, works on dark theme */
const PLATFORM_COLORS: Record<string, string> = {
  reddit: '#f97316',      /* softer orange */
  twitter: '#0ea5e9',     /* sky blue */
  instagram: '#ec4899',   /* pink */
  facebook: '#3b82f6',    /* blue */
  linkedin: '#0d9488',    /* teal */
  unknown: '#64748b',     /* slate */
}

const STATUS_COLORS: Record<string, string> = {
  raw: '#6366f1',         /* indigo */
  filtered: '#8b5cf6',    /* violet */
  qualified: '#22c55e',   /* green */
  rejected: '#ef4444',    /* red */
  ai_rejected: '#eab308', /* amber */
  '?': '#64748b',         /* slate */
}

const CHART_THEME = {
  grid: 'rgba(148, 163, 184, 0.15)',
  axis: '#94a3b8',
  tooltip: {
    bg: '#1e293b',
    border: '#334155',
    text: '#f1f5f9',
  },
}

export default function Overview() {
  const [stats, setStats] = useState<Stats | null>(null)
  const [health, setHealth] = useState<boolean | null>(null)
  const [err, setErr] = useState<string | null>(null)

  const load = () => {
    getHealth().then((h) => setHealth(h.ok)).catch(() => setHealth(false))
    getStats().then(setStats).catch((e) => setErr(e.message))
  }

  useEffect(() => {
    load()
    const t = setInterval(load, 30000)
    return () => clearInterval(t)
  }, [])

  if (err) return <Alert variant="error">{err}</Alert>
  if (!stats) return <LoadingState message="Loading overview…" />

  const byStatus = stats.raw_posts.by_status || {}
  const byPlatform = stats.raw_posts.by_platform || {}
  const qualByPlatform = stats.qualified_leads_by_platform || {}
  const jobSummary = stats.job_summary || []

  const platformBarData = Object.entries(byPlatform).map(([name, count]) => ({ name, count, fill: PLATFORM_COLORS[name] || PLATFORM_COLORS.unknown }))
  const statusPieData = Object.entries(byStatus)
    .filter(([, n]) => n > 0)
    .map(([name, value]) => ({ name, value, fill: STATUS_COLORS[name] || STATUS_COLORS['?'] }))

  const qualPlatformBarData = Object.entries(qualByPlatform).map(([name, count]) => ({ name, count, fill: PLATFORM_COLORS[name] || PLATFORM_COLORS.unknown }))

  const emailQueueData = [
    { name: 'Pending', value: stats.email_queue.pending, fill: '#eab308' },
    { name: 'Sent', value: stats.email_queue.sent, fill: '#22c55e' },
    { name: 'Failed', value: stats.email_queue.failed, fill: '#f87171' },
  ].filter((d) => d.value > 0)
  if (emailQueueData.length === 0) emailQueueData.push({ name: 'Empty', value: 1, fill: '#475569' })

  const pendingFilter = stats.raw_posts.pending_filter ?? 0
  const funnelData = [
    { stage: 'Pending filter', count: pendingFilter, fill: '#6366f1', sub: `${stats.raw_posts.total} total scraped` },
    { stage: 'Passed static', count: (byStatus['filtered'] || 0) + (byStatus['qualified'] || 0), fill: '#8b5cf6', sub: '' },
    { stage: 'AI qualified', count: stats.qualified_leads_count, fill: '#22c55e', sub: '' },
    { stage: 'Queue (pending)', count: stats.email_queue.pending, fill: '#eab308', sub: '' },
    { stage: 'Sent', count: stats.email_queue.sent, fill: '#14b8a6', sub: '' },
  ]

  const jobBarData = jobSummary.map((j) => ({
    name: `${j.jobType} (${j.status})`,
    count: j.count,
    fill: j.status === 'completed' ? '#22c55e' : j.status === 'failed' || j.status === 'cancelled' ? '#f87171' : j.status === 'running' ? '#6366f1' : '#64748b',
  }))

  const lastRun = stats.pipeline_state?.lastRunAt
    ? new Date(stats.pipeline_state.lastRunAt).toLocaleString()
    : 'Never'

  return (
    <div className="space-y-8">
      <PageHeader
        title="Overview"
        subtitle="Pipeline stats, charts, and quick actions"
        action={
          <div className="flex items-center gap-3">
            {health !== null && (
              <Badge variant={health ? 'success' : 'danger'}>
                {health ? 'Connected' : 'Disconnected'}
              </Badge>
            )}
            <Link to="/pipeline">
              <Button variant="primary">Open Pipeline</Button>
            </Link>
          </div>
        }
      />

      {/* Top KPI cards */}
      <section>
        <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-4">At a glance</h2>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-7 gap-4">
          <Link to="/data?tab=raw&status=raw" className="block cursor-pointer group">
            <div className="rounded-xl border border-primary/30 bg-card p-5 shadow-card transition-all duration-200 group-hover:shadow-card-hover group-hover:border-primary/40">
              <div className="text-xs font-medium text-primary/90">Pending filter</div>
              <div className="mt-1 text-2xl font-semibold text-foreground">{stats.raw_posts.pending_filter ?? 0}</div>
              <div className="text-xs text-muted-foreground mt-0.5">
                to process next run
              </div>
            </div>
          </Link>
          <Link to="/data?tab=raw" className="block cursor-pointer group">
            <div className="rounded-xl border border-border bg-card/60 p-5 shadow-card transition-all duration-200 group-hover:shadow-card-hover group-hover:border-muted-foreground/20">
              <div className="text-xs font-medium text-muted-foreground">Posts scraped till now</div>
              <div className="mt-1 text-2xl font-semibold text-muted-foreground">{stats.raw_posts.total}</div>
              <div className="text-xs text-muted-foreground/80 mt-0.5">
                reference only · already processed or pending
              </div>
            </div>
          </Link>
          <Link to="/data?tab=qualified" className="block cursor-pointer group">
            <div className="rounded-xl border border-border bg-card p-5 shadow-card transition-all duration-200 group-hover:shadow-card-hover group-hover:border-primary/20">
              <div className="text-xs font-medium text-muted-foreground">Qualified</div>
              <div className="mt-1 text-2xl font-semibold text-foreground">{stats.qualified_leads_count}</div>
              {stats.qualified_breakdown && (
                <div className="text-xs text-muted-foreground mt-0.5">
                  queue: {(stats.qualified_breakdown.in_queue_pending ?? 0) + (stats.qualified_breakdown.in_queue_sent ?? 0)} · no email: {stats.qualified_breakdown.in_no_email ?? 0} · to process: {stats.qualified_breakdown.to_process ?? 0}
                </div>
              )}
            </div>
          </Link>
          <Link to="/email" className="block cursor-pointer group">
            <div className="rounded-xl border border-border bg-card p-5 shadow-card transition-all duration-200 group-hover:shadow-card-hover group-hover:border-primary/20">
              <div className="text-xs font-medium text-muted-foreground">Pending</div>
              <div className="mt-1 text-2xl font-semibold text-amber-400">{stats.email_queue.pending}</div>
            </div>
          </Link>
          <Link to="/email" className="block cursor-pointer group">
            <div className="rounded-xl border border-border bg-card p-5 shadow-card transition-all duration-200 group-hover:shadow-card-hover group-hover:border-primary/20">
              <div className="text-xs font-medium text-muted-foreground">Sent</div>
              <div className="mt-1 text-2xl font-semibold text-emerald-400">{stats.email_queue.sent}</div>
            </div>
          </Link>
          <Link to="/manual-outreach" className="block cursor-pointer group">
            <div className="rounded-xl border border-border bg-card p-5 shadow-card transition-all duration-200 group-hover:shadow-card-hover group-hover:border-primary/20">
              <div className="text-xs font-medium text-muted-foreground">No email (manual)</div>
              <div className="mt-1 text-2xl font-semibold text-foreground">{stats.leads_no_email?.pending ?? 0}</div>
              <div className="text-xs text-muted-foreground mt-0.5">pending</div>
            </div>
          </Link>
          <Link to="/data?tab=suppression" className="block cursor-pointer group">
            <div className="rounded-xl border border-border bg-card p-5 shadow-card transition-all duration-200 group-hover:shadow-card-hover group-hover:border-primary/20">
              <div className="text-xs font-medium text-muted-foreground">Suppression</div>
              <div className="mt-1 text-2xl font-semibold text-foreground">{stats.suppression_count}</div>
            </div>
          </Link>
          <div className="rounded-xl border border-border bg-card p-5 shadow-card">
            <div className="text-xs font-medium text-muted-foreground">Seen hashes</div>
            <div className="mt-1 text-2xl font-semibold text-muted-foreground">{stats.seen_post_hashes_count ?? '—'}</div>
          </div>
          <Link to="/data?tab=raw" className="block cursor-pointer group">
            <div className="rounded-xl border border-border bg-card p-5 shadow-card transition-all duration-200 group-hover:shadow-card-hover group-hover:border-primary/20">
              <div className="text-xs font-medium text-muted-foreground">Stale (&gt;30d)</div>
              <div className="mt-1 text-2xl font-semibold text-amber-500">
                {(stats.stale?.raw_stale_count ?? 0) + (stats.stale?.qualified_stale_count ?? 0)}
              </div>
              <div className="text-xs text-muted-foreground mt-0.5">raw + qualified</div>
            </div>
          </Link>
        </div>
      </section>

      {/* Charts row 1 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card title="Posts by platform" subtitle="Posts scraped till now (reference) — by source">
          {platformBarData.length > 0 ? (
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={platformBarData} layout="vertical" margin={{ left: 20, right: 20 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke={CHART_THEME.grid} vertical={false} />
                  <XAxis type="number" stroke={CHART_THEME.axis} fontSize={12} tick={{ fill: '#94a3b8' }} />
                  <YAxis type="category" dataKey="name" width={80} stroke={CHART_THEME.axis} fontSize={12} tick={{ fill: '#94a3b8' }} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: CHART_THEME.tooltip.bg,
                      border: `1px solid ${CHART_THEME.tooltip.border}`,
                      borderRadius: '8px',
                      color: CHART_THEME.tooltip.text,
                      fontSize: '13px',
                    }}
                    cursor={{ fill: 'rgba(148,163,184,0.08)' }}
                  />
                  <Bar dataKey="count" radius={[0, 6, 6, 0]} maxBarSize={28} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <p className="text-sm text-muted-foreground py-8 text-center">No data yet. Run Scrape posts.</p>
          )}
        </Card>

        <Card title="Raw posts by status" subtitle="Pipeline stage breakdown">
          {statusPieData.length > 0 ? (
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={statusPieData}
                    cx="50%"
                    cy="50%"
                    innerRadius={55}
                    outerRadius={82}
                    paddingAngle={3}
                    dataKey="value"
                    nameKey="name"
                    stroke="transparent"
                    strokeWidth={1}
                  >
                    {statusPieData.map((entry, i) => (
                      <Cell key={i} fill={entry.fill} stroke="#1e293b" strokeWidth={2} />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{
                      backgroundColor: CHART_THEME.tooltip.bg,
                      border: `1px solid ${CHART_THEME.tooltip.border}`,
                      borderRadius: '8px',
                      color: CHART_THEME.tooltip.text,
                    }}
                  />
                  <Legend wrapperStyle={{ fontSize: '12px' }} iconType="circle" iconSize={8} />
                </PieChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <p className="text-sm text-muted-foreground py-8 text-center">No raw posts yet.</p>
          )}
        </Card>
      </div>

      {/* Charts row 2 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card title="Qualified leads by platform" subtitle="AI-qualified leads per source">
          {qualPlatformBarData.length > 0 ? (
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={qualPlatformBarData} layout="vertical" margin={{ left: 20, right: 20 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke={CHART_THEME.grid} vertical={false} />
                  <XAxis type="number" stroke={CHART_THEME.axis} fontSize={12} tick={{ fill: '#94a3b8' }} />
                  <YAxis type="category" dataKey="name" width={80} stroke={CHART_THEME.axis} fontSize={12} tick={{ fill: '#94a3b8' }} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: CHART_THEME.tooltip.bg,
                      border: `1px solid ${CHART_THEME.tooltip.border}`,
                      borderRadius: '8px',
                      color: CHART_THEME.tooltip.text,
                    }}
                    cursor={{ fill: 'rgba(148,163,184,0.08)' }}
                  />
                  <Bar dataKey="count" radius={[0, 6, 6, 0]} fill="#22c55e" maxBarSize={28} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <p className="text-sm text-muted-foreground py-8 text-center">No qualified leads yet.</p>
          )}
        </Card>

        <Card title="Email queue" subtitle="Pending, sent, and failed">
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={emailQueueData} cx="50%" cy="50%" innerRadius={55} outerRadius={82} paddingAngle={3} dataKey="value" nameKey="name">
                  {emailQueueData.map((entry, i) => (
                    <Cell key={i} fill={entry.fill} stroke="#1e293b" strokeWidth={2} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{
                    backgroundColor: CHART_THEME.tooltip.bg,
                    border: `1px solid ${CHART_THEME.tooltip.border}`,
                    borderRadius: '8px',
                    color: CHART_THEME.tooltip.text,
                  }}
                />
                <Legend wrapperStyle={{ fontSize: '12px' }} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </Card>
      </div>

      {/* Pipeline funnel + Job history */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card title="Pipeline funnel" subtitle="Pending → static filter → AI qualified → queue → sent (transparent counts)">
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={funnelData} layout="vertical" margin={{ left: 20, right: 20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={CHART_THEME.grid} vertical={false} />
                <XAxis type="number" stroke={CHART_THEME.axis} fontSize={12} tick={{ fill: '#94a3b8' }} />
                <YAxis type="category" dataKey="stage" width={110} stroke={CHART_THEME.axis} fontSize={12} tick={{ fill: '#94a3b8' }} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: CHART_THEME.tooltip.bg,
                    border: `1px solid ${CHART_THEME.tooltip.border}`,
                    borderRadius: '8px',
                    color: CHART_THEME.tooltip.text,
                  }}
                  cursor={{ fill: 'rgba(148,163,184,0.08)' }}
                />
                <Bar dataKey="count" radius={[0, 6, 6, 0]} maxBarSize={28} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <Card title="Job runs by stage" subtitle="Completed, failed, running">
          {jobBarData.length > 0 ? (
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={jobBarData} layout="vertical" margin={{ left: 20, right: 20 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke={CHART_THEME.grid} vertical={false} />
                  <XAxis type="number" stroke={CHART_THEME.axis} fontSize={12} tick={{ fill: '#94a3b8' }} />
                  <YAxis type="category" dataKey="name" width={120} stroke={CHART_THEME.axis} fontSize={11} tick={{ fill: '#94a3b8' }} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: CHART_THEME.tooltip.bg,
                      border: `1px solid ${CHART_THEME.tooltip.border}`,
                      borderRadius: '8px',
                      color: CHART_THEME.tooltip.text,
                    }}
                    cursor={{ fill: 'rgba(148,163,184,0.08)' }}
                  />
                  <Bar dataKey="count" radius={[0, 6, 6, 0]} maxBarSize={28} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <p className="text-sm text-muted-foreground py-8 text-center">No job history yet.</p>
          )}
        </Card>
      </div>

      {/* Last run + Quick actions */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card title="Pipeline state" subtitle="Last ingestion run">
          <div className="space-y-2">
            <p className="text-sm text-foreground">
              <span className="text-muted-foreground">Last run:</span> {lastRun}
            </p>
            <p className="text-xs text-muted-foreground">Cursors and since dates are used to avoid re-fetching the same posts.</p>
          </div>
        </Card>

        <Card title="Quick actions" subtitle="Run pipeline stages or manage data">
          <div className="flex flex-wrap gap-3">
            <Link to="/pipeline">
              <Button variant="primary">Pipeline</Button>
            </Link>
            <Link to="/email">
              <Button variant="secondary">Email control</Button>
            </Link>
            <Link to="/data">
              <Button variant="ghost">Browse data</Button>
            </Link>
            <Link to="/settings">
              <Button variant="ghost">Settings</Button>
            </Link>
          </div>
        </Card>
      </div>
    </div>
  )
}
