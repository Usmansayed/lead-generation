import { useEffect, useState, useRef } from 'react'
import { listJobs, startJob, cancelJob, getConfig, getStats, getJob, type Job, type Stats } from '../api'
import { PageHeader, Card, Badge, Button, LoadingState, Alert } from '../components/ui'
import { Loader2, Send, Database, Filter } from 'lucide-react'

const STAGES: { id: string; label: string; shortLabel: string; description: string; icon: typeof Database }[] = [
  {
    id: 'ingest',
    label: 'Scrape raw posts',
    shortLabel: 'Scrape',
    description: 'Fetch posts from Apify (platforms from Settings). Results go to raw posts.',
    icon: Database,
  },
  {
    id: 'filter_and_prepare',
    label: 'Filter & prepare emails',
    shortLabel: 'Filter & prepare',
    description: 'Static filter + AI filter + email generation. Qualified leads get emails in queue or go to No email (manual DM).',
    icon: Filter,
  },
  {
    id: 'send_email',
    label: 'Send emails',
    shortLabel: 'Send',
    description: 'Send pending emails in the queue via SES. No-email leads stay on the manual page for you to DM and mark done.',
    icon: Send,
  },
]

function formatDuration(start: string | null | undefined, end: string | null | undefined): string {
  if (!start) return '—'
  const a = new Date(start).getTime()
  const b = end ? new Date(end).getTime() : Date.now()
  const ms = b - a
  if (ms >= 60000) return `${(ms / 60000).toFixed(1)}m`
  return `${(ms / 1000).toFixed(0)}s`
}

function formatTime(iso: string | null | undefined): string {
  if (!iso) return '—'
  const d = new Date(iso)
  const now = new Date()
  const sameDay = d.toDateString() === now.toDateString()
  return sameDay ? d.toLocaleTimeString() : d.toLocaleString()
}

function JobOutput({ job, defaultOpen = false }: { job: Job; defaultOpen?: boolean }) {
  const stdout = (job.result as { stdout?: string } | null)?.stdout
  const err = job.error
  const hasOutput = (stdout && stdout.trim()) || (err && err.trim())
  const [open, setOpen] = useState(defaultOpen)
  if (!hasOutput) return null
  return (
    <div className="mt-2">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="text-xs font-medium text-muted-foreground hover:text-foreground cursor-pointer"
      >
        {open ? 'Hide output' : 'Show output'}
      </button>
      {open && (
        <pre className="mt-2 p-3 rounded-lg bg-black/60 border border-border text-xs text-muted-foreground overflow-x-auto overflow-y-auto max-h-64 whitespace-pre-wrap font-mono">
          {err && (
            <span className="text-red-400">
              {err}
              {'\n'}
            </span>
          )}
          {stdout}
        </pre>
      )}
    </div>
  )
}

/** Live progress: shows streaming stdout for a running job. Auto-scrolls to bottom. */
function LiveProgress({ jobId, stepLabel, onCancel }: { jobId: string; stepLabel: string; onCancel: (id: string) => void }) {
  const [job, setJob] = useState<Job | null>(null)
  const [cancelLoading, setCancelLoading] = useState(false)
  const preRef = useRef<HTMLPreElement>(null)

  useEffect(() => {
    if (!jobId) return
    const fetchJob = () => {
      getJob(jobId)
        .then(setJob)
        .catch(() => {})
    }
    fetchJob()
    const t = setInterval(fetchJob, 1000)
    return () => clearInterval(t)
  }, [jobId])

  useEffect(() => {
    if (preRef.current) preRef.current.scrollTop = preRef.current.scrollHeight
  }, [job?.result])

  const stdout = (job?.result as { stdout?: string } | null)?.stdout ?? ''
  const err = job?.error ?? ''
  const isRunning = job?.status === 'running'
  const isFailed = job?.status === 'failed'
  const totalLeadsMatch = stdout.match(/total_leads=(\d+)/)
  const totalLeads = totalLeadsMatch ? parseInt(totalLeadsMatch[1], 10) : 0
  const isIngestWithZeroInsert = !isRunning && job?.jobType === 'ingest' && /inserted=0/.test(stdout) && totalLeads > 0

  const handleCancel = () => {
    setCancelLoading(true)
    onCancel(jobId)
    setTimeout(() => setCancelLoading(false), 1000)
  }

  if (!job) return null

  return (
    <Card title="Live progress" subtitle={`${stepLabel} — ${isRunning ? 'running…' : job.status}`} className="border-primary/30">
      <div className="flex flex-wrap items-center gap-3 mb-2">
        {isRunning && <Loader2 className="h-4 w-4 animate-spin text-primary shrink-0" />}
        <span className="text-xs font-medium text-muted-foreground">
          {isRunning ? 'Output updates every second. If stuck, click Cancel below.' : isFailed ? 'Job failed. See error below.' : 'Job finished. Output below.'}
        </span>
        {isRunning && (
          <Button variant="danger" onClick={handleCancel} disabled={cancelLoading} className="shrink-0">
            {cancelLoading ? 'Cancelling…' : 'Cancel job'}
          </Button>
        )}
      </div>
      {isFailed && err && (
        <div className="mb-3 p-3 rounded-lg bg-red-500/10 border border-red-500/30 text-red-400 text-sm font-mono whitespace-pre-wrap">
          {err}
        </div>
      )}
      {isIngestWithZeroInsert && (
        <div className="mb-3 p-3 rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-600 dark:text-amber-400 text-sm">
          This run had 0 new posts stored — all fetched leads were already in the database (deduplication). Restart the API if you changed .env, or run again later for new posts.
        </div>
      )}
      <pre
        ref={preRef}
        className="p-4 rounded-lg bg-black/80 border border-border text-xs text-muted-foreground overflow-x-auto overflow-y-auto max-h-[320px] whitespace-pre-wrap font-mono"
      >
        {stdout || (isRunning ? 'Waiting for output… (if nothing appears, check API is running and pipeline started)' : 'No output.')}
      </pre>
    </Card>
  )
}

const DEFAULT_RAW_TO_FILTER = 200

export default function Pipeline() {
  const [jobs, setJobs] = useState<Job[]>([])
  const [runningIds, setRunningIds] = useState<string[]>([])
  const [stats, setStats] = useState<Stats | null>(null)
  const [config, setConfig] = useState<{ default_platforms?: string[] } | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [starting, setStarting] = useState<string | null>(null)
  const [liveJobId, setLiveJobId] = useState<string | null>(null)
  const [rawToFilter, setRawToFilter] = useState<number>(DEFAULT_RAW_TO_FILTER)

  const loadJobs = () => {
    listJobs({ limit: 30 })
      .then((d) => {
        setJobs(d.items)
        setRunningIds(d.runningIds || [])
      })
      .catch((e) => setError(e.message))
  }

  const loadStats = () => {
    getStats()
      .then(setStats)
      .catch(() => {})
  }

  useEffect(() => {
    setLoading(true)
    loadJobs()
    loadStats()
    getConfig().then(setConfig).catch(() => {})
    setLoading(false)
  }, [])

  useEffect(() => {
    const t = setInterval(() => {
      loadJobs()
      loadStats()
    }, 2000)
    return () => clearInterval(t)
  }, [])

  const getIngestOptions = (): Record<string, unknown> | undefined => {
    const raw = config?.default_platforms
    const defaultList = ['reddit', 'twitter', 'instagram', 'facebook', 'linkedin']
    if (raw && Array.isArray(raw) && raw.length > 0) return { platforms: raw }
    if (raw && typeof raw === 'string') return { platforms: [raw] }
    return { platforms: defaultList }
  }

  const handleStart = (jobType: string, options?: Record<string, unknown>) => {
    setStarting(jobType)
    setError(null)
    setLiveJobId(null)
    let finalOptions: Record<string, unknown> = options ?? {}
    if (jobType === 'ingest') {
      finalOptions = getIngestOptions() ?? {}
    } else if (jobType === 'filter_and_prepare') {
      finalOptions = {
        after_filter_limit: rawToFilter,
        ...options,
      }
    }
    console.log('[Pipeline] DEBUG starting job', { jobType, options: finalOptions })
    startJob({ jobType, options: Object.keys(finalOptions).length ? finalOptions : undefined })
      .then((j) => {
        console.log('[Pipeline] DEBUG job started', { jobId: j._id, status: j.status })
        setLiveJobId(j._id)
        loadJobs()
        loadStats()
      })
      .catch((e) => {
        console.error('[Pipeline] DEBUG job start failed', e)
        setError(e.message)
      })
      .finally(() => setStarting(null))
  }

  const handleCancel = (id: string) => {
    cancelJob(id)
      .then(() => { loadJobs(); loadStats(); })
      .catch((e) => setError(e?.message || 'Cancel failed'))
  }

  const getLastJob = (type: string) => jobs.find((j) => j.jobType === type && j.status !== 'pending')
  const isRunning = (type: string) =>
    runningIds.some((id) => jobs.find((j) => j._id === id)?.jobType === type) ||
    jobs.some((j) => j.jobType === type && j.status === 'running')

  if (loading && jobs.length === 0) return <LoadingState message="Loading pipeline…" />

  const rawTotal = stats?.raw_posts?.total ?? 0
  const rawPendingFilter = stats?.raw_posts?.pending_filter ?? 0
  const qualifiedTotal = stats?.qualified_leads_count ?? 0
  const breakdown = stats?.qualified_breakdown
  const pendingEmails = stats?.email_queue?.pending ?? 0
  const noEmailPending = stats?.leads_no_email?.pending ?? 0
  const byStatus = stats?.raw_posts?.by_status ?? {}

  const runningJobId = liveJobId ?? runningIds[0] ?? null
  const runningJob = runningJobId ? jobs.find((j) => j._id === runningJobId) : null
  const runningStepLabel = runningJob ? STAGES.find((s) => s.id === runningJob.jobType)?.label ?? runningJob.jobType : STAGES.find((s) => s.id === (jobs.find((j) => j._id === runningJobId)?.jobType))?.label ?? 'Running'

  return (
    <div className="space-y-8">
      <PageHeader
        title="Pipeline"
        subtitle="Three steps: scrape posts → filter & prepare emails → send. You trigger each step. See live counts below."
      />
      {error && <Alert variant="error">{error}</Alert>}

      <div className="rounded-lg border border-border bg-muted/20 px-4 py-2 text-xs text-muted-foreground">
        <strong className="text-foreground/90">You have full control:</strong> choose platforms to scrape, set how many raw posts to send to the filter per run, run or cancel each step, and see exactly what is pending vs reference (scraped till now).
      </div>

      {/* Visual progress: which step is running / last completed */}
      <div className="rounded-xl border border-border bg-card p-4">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-3">Pipeline progress</h2>
        <div className="flex flex-wrap items-center gap-2 sm:gap-4">
          {STAGES.map((stage, i) => {
            const running = runningJobId && jobs.find((j) => j._id === runningJobId)?.jobType === stage.id
            const lastJob = getLastJob(stage.id)
            const done = lastJob?.status === 'completed'
            return (
              <div key={stage.id} className="flex items-center gap-2">
                <div
                  className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full border-2 text-xs font-medium ${
                    running
                      ? 'border-primary bg-primary/20 text-primary animate-pulse'
                      : done
                        ? 'border-emerald-500 bg-emerald-500/20 text-emerald-400'
                        : 'border-muted-foreground/50 bg-muted/30 text-muted-foreground'
                  }`}
                  title={stage.description}
                >
                  {running ? <Loader2 className="h-4 w-4 animate-spin" /> : i + 1}
                </div>
                <span className={`text-sm font-medium ${running ? 'text-primary' : done ? 'text-emerald-400' : 'text-muted-foreground'}`}>
                  {stage.shortLabel}
                </span>
                {i < STAGES.length - 1 && (
                  <span className="hidden sm:inline text-muted-foreground/50">→</span>
                )}
              </div>
            )
          })}
        </div>
        {runningJobId && (
          <p className="text-xs text-muted-foreground mt-2">
            Running: <span className="text-primary font-medium">{runningStepLabel}</span>
          </p>
        )}
      </div>

      {/* Live progress: show streaming output when a step is running or just finished */}
      {runningJobId && (
        <LiveProgress jobId={runningJobId} stepLabel={runningStepLabel} onCancel={handleCancel} />
      )}

      {/* Live stats: transparent counts — pending vs total, qualified breakdown */}
      <div className="rounded-xl border border-border bg-card/50 p-4">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-3">Live counts (transparent)</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <div className="text-sm font-medium text-foreground mb-1">Raw posts</div>
            <div className="text-xs text-muted-foreground">
              <span className="font-semibold text-primary">{rawPendingFilter}</span> pending filter (to process)
              <span className="text-muted-foreground/80"> · </span>
              <span className="text-muted-foreground/90">{rawTotal}</span> scraped till now (reference)
            </div>
          </div>
          <div>
            <div className="text-sm font-medium text-foreground mb-1">Passed static</div>
            <div className="text-xs text-muted-foreground">
              <span className="font-semibold text-foreground">{(byStatus['filtered'] ?? 0) + (byStatus['qualified'] ?? 0)}</span> posts
            </div>
          </div>
          <div>
            <div className="text-sm font-medium text-foreground mb-1">Qualified (AI)</div>
            <div className="text-xs text-muted-foreground">
              <span className="font-semibold text-foreground">{qualifiedTotal}</span> total
              {breakdown && (
                <>
                  <span className="text-muted-foreground/80"> · queue: </span>
                  <span className="font-semibold text-amber-400">{breakdown.in_queue_pending}</span> pending
                  <span className="text-muted-foreground/80">, </span>
                  <span className="font-semibold text-emerald-400">{breakdown.in_queue_sent}</span> sent
                  <span className="text-muted-foreground/80"> · no email: </span>
                  <span className="font-semibold text-foreground">{breakdown.in_no_email}</span>
                  <span className="text-muted-foreground/80"> · to process: </span>
                  <span className="font-semibold text-primary">{breakdown.to_process}</span>
                </>
              )}
            </div>
          </div>
          <div>
            <div className="text-sm font-medium text-foreground mb-1">Email & manual</div>
            <div className="text-xs text-muted-foreground">
              Queue pending: <span className="font-semibold text-amber-400">{pendingEmails}</span>
              <span className="text-muted-foreground/80"> · </span>
              No email (manual): <span className="font-semibold text-foreground">{noEmailPending}</span>
            </div>
          </div>
        </div>
      </div>

      {/* 3 steps */}
      <section>
        <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-4">Steps</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {STAGES.map((stage) => {
            const running = isRunning(stage.id)
            const last = getLastJob(stage.id)
            const startingNow = starting === stage.id
            const Icon = stage.icon
            const isFilterStep = stage.id === 'filter_and_prepare'
            return (
              <Card key={stage.id} title={stage.label} subtitle={stage.description}>
                <div className="flex flex-col gap-4">
                  {isFilterStep && (
                    <div className="rounded-lg bg-muted/40 border border-border p-3 space-y-2">
                      <label className="text-sm font-medium text-foreground block">
                        How many posts from the raw posts to send to the filter?
                      </label>
                      <div className="flex items-center gap-2 flex-wrap">
                        <input
                          type="number"
                          min={1}
                          max={10000}
                          value={rawToFilter}
                          onChange={(e) => setRawToFilter(Math.max(1, parseInt(e.target.value, 10) || 0))}
                          className="w-24 rounded border border-border bg-background px-2 py-1.5 text-sm"
                        />
                        <span className="text-xs text-muted-foreground">{rawPendingFilter} pending</span>
                      </div>
                    </div>
                  )}
                  <div className="flex items-center justify-between gap-3 flex-wrap">
                    <Button
                      variant="primary"
                      disabled={running || startingNow}
                      onClick={() => handleStart(stage.id)}
                      className="gap-2"
                    >
                      {startingNow ? (
                        <>Starting…</>
                      ) : running ? (
                        <>
                          <Loader2 className="h-4 w-4 animate-spin" />
                          Running…
                        </>
                      ) : (
                        <>
                          <Icon className="h-4 w-4" />
                          Run
                        </>
                      )}
                    </Button>
                    {running && (() => {
                      const idForStage = runningIds.find((id) => jobs.find((j) => j._id === id)?.jobType === stage.id) ?? (liveJobId && jobs.find((j) => j._id === liveJobId)?.jobType === stage.id ? liveJobId : null)
                      return idForStage ? (
                        <Button variant="danger" onClick={() => handleCancel(idForStage)} className="shrink-0">
                          Cancel
                        </Button>
                      ) : null
                    })()}
                    {last && (
                      <div className="flex items-center gap-2 text-sm">
                        <Badge
                          variant={
                            last.status === 'completed' ? 'success' : last.status === 'failed' || last.status === 'cancelled' ? 'danger' : 'info'
                          }
                        >
                          {last.status}
                        </Badge>
                        <span className="text-muted-foreground">{formatTime(last.startedAt)}</span>
                      </div>
                    )}
                  </div>
                  {running && (
                    <p className="text-xs text-muted-foreground">
                      Raw: {rawTotal} ({rawPendingFilter} pending) · Qualified: {qualifiedTotal} · Pending: {pendingEmails}
                    </p>
                  )}
                </div>
              </Card>
            )
          })}
        </div>
      </section>

      {/* Job history with output */}
      <Card title="Job history" subtitle="Recent runs. Cancel running jobs here. Expand a row to see server output (no need for terminal).">
        <div className="overflow-x-auto -mx-6 -mb-6">
          <table className="w-full text-sm table-row-hover">
            <thead>
              <tr className="border-b border-border bg-muted/30">
                <th className="text-left py-3 px-4 font-medium text-muted-foreground">Step</th>
                <th className="text-left py-3 px-4 font-medium text-muted-foreground">Status</th>
                <th className="text-left py-3 px-4 font-medium text-muted-foreground">Started</th>
                <th className="text-left py-3 px-4 font-medium text-muted-foreground">Duration</th>
                <th className="text-left py-3 px-4 font-medium text-muted-foreground">Action</th>
              </tr>
            </thead>
            <tbody>
              {jobs.length === 0 ? (
                <tr>
                  <td colSpan={5} className="py-12 text-center text-muted-foreground">
                    No jobs yet. Run a step above.
                  </td>
                </tr>
              ) : (
                jobs.map((j) => {
                  const running = j.status === 'running'
                  const label = STAGES.find((s) => s.id === j.jobType)?.label ?? j.jobType
                  return (
                    <tr key={j._id} className="border-b border-border/50">
                      <td className="py-3 px-4 font-medium text-foreground align-top">{label}</td>
                      <td className="py-3 px-4 align-top">
                        <Badge
                          variant={
                            running ? 'info' : j.status === 'completed' ? 'success' : j.status === 'failed' || j.status === 'cancelled' ? 'danger' : 'default'
                          }
                        >
                          {j.status}
                        </Badge>
                      </td>
                      <td className="py-3 px-4 text-muted-foreground align-top">{formatTime(j.startedAt)}</td>
                      <td className="py-3 px-4 text-muted-foreground align-top">{formatDuration(j.startedAt, j.finishedAt)}</td>
                      <td className="py-3 px-4 align-top">
                        {running && (
                          <Button variant="danger" onClick={() => handleCancel(j._id)}>
                            Cancel
                          </Button>
                        )}
                      </td>
                    </tr>
                  )
                })
              )}
            </tbody>
          </table>
        </div>
        {jobs.length > 0 && (() => {
          const withOutput = jobs.find((j) => (j.result as { stdout?: string })?.stdout || j.error)
          return withOutput ? (
            <div className="mt-4 pt-4 border-t border-border">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-3">Server output (no terminal needed)</h3>
              <JobOutput job={withOutput} defaultOpen />
            </div>
          ) : null
        })()}
      </Card>
    </div>
  )
}
