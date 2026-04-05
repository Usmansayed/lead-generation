import { useEffect, useState } from 'react'
import { PieChart, Pie, Cell, Legend, Tooltip, ResponsiveContainer } from 'recharts'
import { getStats, listEmailQueue, pauseSending, resumeSending, getConfig, cancelQueuedEmail } from '../api'
import { PageHeader, Card, Badge, Button, LoadingState, Alert } from '../components/ui'

type QueueItem = { _id: string; status?: string; toEmail?: string; subject?: string; createdAt?: string }

const QUEUE_CHART_THEME = {
  pending: '#eab308',
  sent: '#22c55e',
  failed: '#f87171',
  empty: '#475569',
}

const queueChartData = (stats: { email_queue?: { pending?: number; sent?: number; failed?: number } } | null) => {
  const p = stats?.email_queue?.pending ?? 0
  const s = stats?.email_queue?.sent ?? 0
  const f = stats?.email_queue?.failed ?? 0
  const arr = [
    { name: 'Pending', value: p, fill: QUEUE_CHART_THEME.pending },
    { name: 'Sent', value: s, fill: QUEUE_CHART_THEME.sent },
    { name: 'Failed', value: f, fill: QUEUE_CHART_THEME.failed },
  ].filter((d) => d.value > 0)
  return arr.length > 0 ? arr : [{ name: 'Empty', value: 1, fill: QUEUE_CHART_THEME.empty }]
}

function QueuePieChart({ stats }: { stats: { email_queue?: { pending?: number; sent?: number; failed?: number } } | null }) {
  const data = queueChartData(stats)
  return (
    <ResponsiveContainer width="100%" height="100%">
      <PieChart>
        <Pie data={data} cx="50%" cy="50%" innerRadius={40} outerRadius={65} paddingAngle={3} dataKey="value" nameKey="name">
          {data.map((entry, i) => (
            <Cell key={i} fill={entry.fill} stroke="#1e293b" strokeWidth={2} />
          ))}
        </Pie>
        <Tooltip
          contentStyle={{
            backgroundColor: '#1e293b',
            border: '1px solid #334155',
            borderRadius: '8px',
            color: '#f1f5f9',
          }}
        />
        <Legend wrapperStyle={{ fontSize: '12px' }} iconType="circle" iconSize={8} />
      </PieChart>
    </ResponsiveContainer>
  )
}

export default function EmailControl() {
  const [stats, setStats] = useState<{ email_queue?: { pending: number; sent: number; failed: number } } | null>(null)
  const [queue, setQueue] = useState<{ items: QueueItem[]; total: number } | null>(null)
  const [config, setConfig] = useState<{ sending_paused?: boolean } | null>(null)
  const [loading, setLoading] = useState(true)
  const [actionLoading, setActionLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const load = () =>
    Promise.all([
      getStats(),
      listEmailQueue({ status: 'pending', limit: 50 }),
      getConfig(),
    ]).then(([statsData, queueData, configData]) => {
      setStats(statsData)
      setQueue(queueData)
      setConfig(configData)
    })

  useEffect(() => {
    load().catch((e) => setError(e.message)).finally(() => setLoading(false))
  }, [])

  const paused = config?.sending_paused ?? false

  const handlePause = () => {
    setActionLoading(true)
    setError(null)
    pauseSending()
      .then(load)
      .catch((e) => setError(e.message))
      .finally(() => setActionLoading(false))
  }

  const handleResume = () => {
    setActionLoading(true)
    setError(null)
    resumeSending()
      .then(load)
      .catch((e) => setError(e.message))
      .finally(() => setActionLoading(false))
  }

  const handleCancel = (id: string) => {
    setError(null)
    cancelQueuedEmail(id)
      .then(load)
      .catch((e) => setError(e.message))
  }

  if (loading && !stats) return <LoadingState message="Loading email control…" />

  return (
    <div className="space-y-8">
      <PageHeader
        title="Email"
        subtitle="Pause or resume sending; view and cancel pending emails."
      />
      {error && <Alert variant="error">{error}</Alert>}

      <section>
        <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-4">Queue summary</h2>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="grid grid-cols-3 gap-4">
            <div className="rounded-xl border border-border bg-card p-6 shadow-card">
              <div className="text-sm font-medium text-muted-foreground">Pending</div>
              <div className="mt-2 text-3xl font-semibold text-amber-400">{stats?.email_queue?.pending ?? 0}</div>
              <div className="mt-1 text-xs text-muted-foreground">Ready to send</div>
            </div>
            <div className="rounded-xl border border-border bg-card p-6 shadow-card">
              <div className="text-sm font-medium text-muted-foreground">Sent</div>
              <div className="mt-2 text-3xl font-semibold text-emerald-400">{stats?.email_queue?.sent ?? 0}</div>
            </div>
            <div className="rounded-xl border border-border bg-card p-6 shadow-card">
              <div className="text-sm font-medium text-muted-foreground">Failed</div>
              <div className="mt-2 text-3xl font-semibold text-red-400">{stats?.email_queue?.failed ?? 0}</div>
            </div>
          </div>
          <div className="rounded-xl border border-border bg-card p-6 shadow-card">
            <div className="text-sm font-medium text-muted-foreground mb-4">Queue breakdown</div>
            <div className="h-48">
              <QueuePieChart stats={stats} />
            </div>
          </div>
        </div>
      </section>

      <Card
        title="Sending"
        subtitle={paused ? 'Sending is paused. Resume to allow the Send emails stage to deliver.' : 'Sending is active. Pause to stop delivery without cancelling the queue.'}
      >
        <div className="flex flex-wrap items-center gap-4">
          <Button variant="secondary" onClick={handlePause} disabled={paused || actionLoading}>
            Pause sending
          </Button>
          <Button variant="primary" onClick={handleResume} disabled={!paused || actionLoading}>
            Resume sending
          </Button>
          {paused && <Badge variant="warning">Paused</Badge>}
        </div>
      </Card>

      <Card
        title="Pending queue"
        subtitle="Emails waiting to be sent. Cancel to remove from the queue."
      >
        {!queue ? (
          <LoadingState message="Loading queue…" />
        ) : queue.items.length === 0 ? (
          <div className="py-12 text-center text-muted-foreground">No pending emails.</div>
        ) : (
          <div className="overflow-x-auto table-row-hover">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border bg-muted/50">
                  <th className="text-left py-3 px-4 font-medium text-muted-foreground">To</th>
                  <th className="text-left py-3 px-4 font-medium text-muted-foreground">Subject</th>
                  <th className="text-left py-3 px-4 font-medium text-muted-foreground">Action</th>
                </tr>
              </thead>
              <tbody>
                {queue.items.map((item) => (
                  <tr key={item._id} className="border-b border-border/50">
                    <td className="py-3 px-4 font-mono text-xs text-foreground">{item.toEmail ?? '—'}</td>
                    <td className="py-3 px-4 text-muted-foreground max-w-md truncate">{(item.subject ?? '').slice(0, 60)}{(item.subject?.length ?? 0) > 60 ? '…' : ''}</td>
                    <td className="py-3 px-4">
                      <Button variant="danger" onClick={() => handleCancel(item._id)}>Cancel</Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  )
}
