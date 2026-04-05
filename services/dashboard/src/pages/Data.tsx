import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { listRawPosts, listQualifiedLeads, listEmailQueue, listSuppression, getRawPost, getQualifiedLead } from '../api'
import { PageHeader, Card, Badge, Button, EmptyState, LoadingState, Alert, Sheet } from '../components/ui'

type RawPost = { _id: string; platform?: string; status?: string; postText?: string; postUrl?: string; author?: { name?: string; handle?: string; profileUrl?: string }; createdAt?: string; staticScore?: number; keywordsMatched?: string[]; rejectReason?: string }
type QualifiedLead = { _id: string; platform?: string; postText?: string; postUrl?: string; author?: { name?: string; handle?: string }; createdAt?: string; aiScore?: number }
type QueueItem = { _id: string; status?: string; toEmail?: string; subject?: string; createdAt?: string }
type SuppressionItem = { _id?: string; leadId?: string; email?: string; reason?: string; createdAt?: string }

const TAB = ['raw', 'qualified', 'queue', 'suppression'] as const
type TabId = (typeof TAB)[number]

const PLATFORMS = [
  { value: '', label: 'All platforms' },
  { value: 'reddit', label: 'Reddit' },
  { value: 'twitter', label: 'Twitter' },
  { value: 'instagram', label: 'Instagram' },
  { value: 'facebook', label: 'Facebook' },
  { value: 'linkedin', label: 'LinkedIn' },
]

function truncate(s: string, len: number) {
  if (!s) return '—'
  return s.length <= len ? s : s.slice(0, len) + '…'
}

function DetailContent({ type, id }: { type: 'raw' | 'qualified'; id: string }) {
  const [data, setData] = useState<Record<string, unknown> | null>(null)
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState<string | null>(null)

  useEffect(() => {
    setLoading(true)
    setErr(null)
    const fetchFn = type === 'raw' ? getRawPost : getQualifiedLead
    fetchFn(id)
      .then(setData)
      .catch((e) => setErr(e.message))
      .finally(() => setLoading(false))
  }, [type, id])

  if (loading) return <LoadingState message="Loading…" />
  if (err) return <Alert variant="error">{err}</Alert>
  if (!data) return null

  const author = (data.author as Record<string, unknown> | undefined)
  const name = String(author?.name ?? author?.handle ?? '—')
  const handle = String(author?.handle ?? author?.name ?? '—')
  const postUrl = (data.postUrl as string) ?? ''
  const postText = (data.postText as string) ?? ''
  const platform = (data.platform as string) ?? '—'
  const status = (data.status as string) ?? '—'
  const createdAt = data.createdAt ? new Date(data.createdAt as string).toLocaleString() : '—'

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2">Platform & status</h3>
        <div className="flex flex-wrap gap-2">
          <Badge variant="info">{platform}</Badge>
          <Badge variant="default">{status}</Badge>
          {type === 'raw' && data.staticScore != null && <span className="text-sm text-muted-foreground">Static score: {String(data.staticScore)}</span>}
          {type === 'qualified' && data.aiScore != null && <span className="text-sm text-muted-foreground">AI score: {String(data.aiScore)}</span>}
        </div>
      </div>

      <div>
        <h3 className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2">Author</h3>
        <p className="text-sm text-foreground">{name}</p>
        {String(handle) !== String(name) ? <p className="text-sm text-muted-foreground">@{String(handle)}</p> : null}
        {author?.profileUrl ? (
          <a href={String(author.profileUrl)} target="_blank" rel="noopener noreferrer" className="text-sm text-primary hover:underline mt-1 inline-block">Profile</a>
        ) : null}
      </div>

      <div>
        <h3 className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2">Post</h3>
        <p className="text-sm text-foreground whitespace-pre-wrap break-words">{postText || '—'}</p>
        {postUrl && (
          <a href={postUrl} target="_blank" rel="noopener noreferrer" className="text-sm text-primary hover:underline mt-2 inline-block">Open post</a>
        )}
      </div>

      {type === 'raw' && (data.keywordsMatched as string[] | undefined)?.length ? (
        <div>
          <h3 className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2">Keywords matched</h3>
          <div className="flex flex-wrap gap-1.5">
            {(data.keywordsMatched as string[]).map((k) => (
              <Badge key={k} variant="default">{k}</Badge>
            ))}
          </div>
        </div>
      ) : null}

      {type === 'raw' && data.rejectReason != null ? (
        <div>
          <h3 className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2">Reject reason</h3>
          <p className="text-sm text-muted-foreground">{String(data.rejectReason)}</p>
        </div>
      ) : null}

      <div>
        <h3 className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2">Created</h3>
        <p className="text-sm text-muted-foreground">{createdAt}</p>
      </div>
    </div>
  )
}

export default function Data() {
  const [searchParams, setSearchParams] = useSearchParams()
  const tabParam = (searchParams.get('tab') || 'raw') as TabId
  const tab = TAB.includes(tabParam) ? tabParam : 'raw'

  const [raw, setRaw] = useState<{ items: RawPost[]; total: number } | null>(null)
  const [qual, setQual] = useState<{ items: QualifiedLead[]; total: number } | null>(null)
  const [queue, setQueue] = useState<{ items: QueueItem[]; total: number } | null>(null)
  const [supp, setSupp] = useState<{ items: SuppressionItem[]; total: number } | null>(null)
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState<string | null>(null)
  const [page, setPage] = useState(0)
  const [statusFilter, setStatusFilter] = useState<string>(() => {
    const s = searchParams.get('status')
    if (s) return s
    return tab === 'raw' ? 'raw' : ''
  })
  const [platformFilter, setPlatformFilter] = useState<string>('')
  const [detail, setDetail] = useState<{ type: 'raw' | 'qualified'; id: string } | null>(null)
  const limit = 20

  useEffect(() => {
    setLoading(true)
    setErr(null)
    if (tab === 'raw') listRawPosts({ limit, skip: page * limit, status: statusFilter || undefined, platform: platformFilter || undefined }).then(setRaw).catch((e) => setErr(e.message)).finally(() => setLoading(false))
    if (tab === 'qualified') listQualifiedLeads({ limit, skip: page * limit, platform: platformFilter || undefined }).then(setQual).catch((e) => setErr(e.message)).finally(() => setLoading(false))
    if (tab === 'queue') listEmailQueue({ limit, skip: page * limit }).then(setQueue).catch((e) => setErr(e.message)).finally(() => setLoading(false))
    if (tab === 'suppression') listSuppression({ limit, skip: page * limit }).then(setSupp).catch((e) => setErr(e.message)).finally(() => setLoading(false))
  }, [tab, page, statusFilter, platformFilter])

  const setTab = (t: TabId) => {
    setSearchParams({ tab: t })
    setPage(0)
    if (t === 'raw') setStatusFilter('raw')
  }

  const total = (tab === 'raw' ? raw?.total : tab === 'qualified' ? qual?.total : tab === 'queue' ? queue?.total : supp?.total) ?? 0
  const totalPages = Math.ceil(total / limit)

  return (
    <div className="space-y-6">
      <PageHeader title="Data" subtitle="Browse raw posts, qualified leads, email queue, and suppression list." />
      {err && <Alert variant="error">{err}</Alert>}

      <div className="flex flex-wrap gap-1 rounded-xl border border-border bg-muted/20 p-1">
        {TAB.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2.5 rounded-lg text-sm font-medium transition-colors duration-200 cursor-pointer ${
              tab === t
                ? 'bg-primary text-primary-foreground shadow-sm'
                : 'text-muted-foreground hover:text-foreground hover:bg-muted/50'
            }`}
          >
            {t === 'raw' ? 'Raw posts' : t === 'qualified' ? 'Qualified leads' : t === 'queue' ? 'Email queue' : 'Suppression'}
          </button>
        ))}
      </div>

      <Card>
        {loading ? (
          <LoadingState message={`Loading ${tab}…`} />
        ) : tab === 'raw' && raw ? (
          <>
            <div className="flex flex-wrap items-center justify-between gap-4 mb-2">
              <div className="flex items-center gap-3 flex-wrap">
                <span className="text-sm text-muted-foreground">
                  Showing: {statusFilter ? (statusFilter === 'raw' ? 'Pending filter (raw)' : statusFilter) : 'All scraped'}
                  <span className="text-muted-foreground/80"> · Total: {raw.total}</span>
                </span>
                <select value={statusFilter} onChange={(e) => { setStatusFilter(e.target.value); setPage(0); }} className="rounded-md border border-border bg-background px-3 py-1.5 text-sm text-foreground">
                  <option value="">All scraped (all time)</option>
                  <option value="raw">Pending filter (raw)</option>
                  <option value="filtered">filtered</option>
                  <option value="qualified">qualified</option>
                  <option value="rejected">rejected</option>
                  <option value="ai_rejected">ai_rejected</option>
                </select>
                <select value={platformFilter} onChange={(e) => { setPlatformFilter(e.target.value); setPage(0); }} className="rounded-md border border-border bg-background px-3 py-1.5 text-sm text-foreground">
                  {PLATFORMS.map((p) => <option key={p.value || 'all'} value={p.value}>{p.label}</option>)}
                </select>
              </div>
              {totalPages > 1 && (
                <div className="flex gap-2 items-center">
                  <Button variant="ghost" disabled={page === 0} onClick={() => setPage((p) => p - 1)}>Previous</Button>
                  <span className="py-2 text-sm text-muted-foreground">Page {page + 1} of {totalPages}</span>
                  <Button variant="ghost" disabled={page >= totalPages - 1} onClick={() => setPage((p) => p + 1)}>Next</Button>
                </div>
              )}
            </div>
            {!statusFilter ? (
              <div className="mb-4 rounded-lg border border-amber-500/20 bg-amber-500/5 px-3 py-2 text-xs text-muted-foreground">
                <strong className="text-foreground/80">Reference only.</strong> You are viewing all posts scraped till now (historical). For what to process next, switch to <strong>Pending filter (raw)</strong>.
              </div>
            ) : (
              <p className="text-xs text-muted-foreground mb-4">
                <strong>Pending filter</strong> = not yet run through static filter (use for next run). Use dropdown to see processed or all scraped.
              </p>
            )}
            {raw.items.length === 0 ? (
              <EmptyState
                title={statusFilter === 'raw' ? 'No pending filter posts' : 'No raw posts'}
                description={statusFilter === 'raw' ? 'All scraped posts have been processed, or run Scrape posts first.' : 'Run the Scrape posts stage to ingest data.'}
              />
            ) : (
              <div className="overflow-x-auto table-row-hover">
                <table className="w-full text-sm">
                  <thead><tr className="border-b border-border bg-muted/50"><th className="text-left py-3 px-4 font-medium text-muted-foreground">Platform</th><th className="text-left py-3 px-4 font-medium text-muted-foreground">Status</th><th className="text-left py-3 px-4 font-medium text-muted-foreground">Post</th><th className="text-left py-3 px-4 font-medium text-muted-foreground">Author</th><th className="text-left py-3 px-4 font-medium text-muted-foreground">Link</th></tr></thead>
                  <tbody>
                    {raw.items.map((row) => (
                      <tr key={row._id} className="border-b border-border/50" onClick={() => setDetail({ type: 'raw', id: row._id })}>
                        <td className="py-3 px-4"><Badge variant="default">{row.platform ?? '—'}</Badge></td>
                        <td className="py-3 px-4 text-foreground">{row.status ?? '—'}</td>
                        <td className="py-3 px-4 max-w-xs text-muted-foreground">{truncate(row.postText ?? '', 80)}</td>
                        <td className="py-3 px-4 text-muted-foreground">{row.author?.handle ?? row.author?.name ?? '—'}</td>
                        <td className="py-3 px-4"><a href={row.postUrl} target="_blank" rel="noopener noreferrer" className="text-primary hover:underline" onClick={(e) => e.stopPropagation()}>Open</a></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        ) : tab === 'qualified' && qual ? (
          <>
            <div className="flex flex-wrap items-center justify-between gap-4 mb-4">
              <div className="flex items-center gap-3 flex-wrap">
                <span className="text-sm text-muted-foreground">Total: {qual.total}</span>
                <select value={platformFilter} onChange={(e) => { setPlatformFilter(e.target.value); setPage(0); }} className="rounded-md border border-border bg-background px-3 py-1.5 text-sm text-foreground">
                  {PLATFORMS.map((p) => <option key={p.value || 'all'} value={p.value}>{p.label}</option>)}
                </select>
              </div>
              {totalPages > 1 && (
                <div className="flex gap-2 items-center">
                  <Button variant="ghost" disabled={page === 0} onClick={() => setPage((p) => p - 1)}>Previous</Button>
                  <span className="py-2 text-sm text-muted-foreground">Page {page + 1} of {totalPages}</span>
                  <Button variant="ghost" disabled={page >= totalPages - 1} onClick={() => setPage((p) => p + 1)}>Next</Button>
                </div>
              )}
            </div>
            {qual.items.length === 0 ? (
              <EmptyState title="No qualified leads" description="Run Static filter and AI scoring to qualify leads." />
            ) : (
              <div className="overflow-x-auto table-row-hover">
                <table className="w-full text-sm">
                  <thead><tr className="border-b border-border bg-muted/50"><th className="text-left py-3 px-4 font-medium text-muted-foreground">Platform</th><th className="text-left py-3 px-4 font-medium text-muted-foreground">Post</th><th className="text-left py-3 px-4 font-medium text-muted-foreground">Author</th><th className="text-left py-3 px-4 font-medium text-muted-foreground">Link</th></tr></thead>
                  <tbody>
                    {qual.items.map((row) => (
                      <tr key={row._id} className="border-b border-border/50" onClick={() => setDetail({ type: 'qualified', id: row._id })}>
                        <td className="py-3 px-4"><Badge variant="default">{row.platform ?? '—'}</Badge></td>
                        <td className="py-3 px-4 max-w-xs text-muted-foreground">{truncate(row.postText ?? '', 80)}</td>
                        <td className="py-3 px-4 text-muted-foreground">{row.author?.handle ?? row.author?.name ?? '—'}</td>
                        <td className="py-3 px-4"><a href={row.postUrl} target="_blank" rel="noopener noreferrer" className="text-primary hover:underline" onClick={(e) => e.stopPropagation()}>Open</a></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        ) : tab === 'queue' && queue ? (
          <>
            <div className="flex items-center justify-between mb-4">
              <span className="text-sm text-muted-foreground">Total: {queue.total}</span>
              {totalPages > 1 && (
                <div className="flex gap-2">
                  <Button variant="ghost" disabled={page === 0} onClick={() => setPage((p) => p - 1)}>Previous</Button>
                  <span className="py-2 text-sm text-muted-foreground">Page {page + 1} of {totalPages}</span>
                  <Button variant="ghost" disabled={page >= totalPages - 1} onClick={() => setPage((p) => p + 1)}>Next</Button>
                </div>
              )}
            </div>
            {queue.items.length === 0 ? (
              <EmptyState title="No email queue items" description="Run Research & queue to generate and queue emails." />
            ) : (
              <div className="overflow-x-auto table-row-hover">
                <table className="w-full text-sm">
                  <thead><tr className="border-b border-border bg-muted/50"><th className="text-left py-3 px-4 font-medium text-muted-foreground">To</th><th className="text-left py-3 px-4 font-medium text-muted-foreground">Subject</th><th className="text-left py-3 px-4 font-medium text-muted-foreground">Status</th><th className="text-left py-3 px-4 font-medium text-muted-foreground">Created</th></tr></thead>
                  <tbody>
                    {queue.items.map((row) => (
                      <tr key={row._id} className="border-b border-border/50">
                        <td className="py-3 px-4 font-mono text-xs text-foreground">{row.toEmail ?? '—'}</td>
                        <td className="py-3 px-4 max-w-sm text-muted-foreground">{truncate(row.subject ?? '', 50)}</td>
                        <td className="py-3 px-4"><Badge variant={row.status === 'sent' ? 'success' : row.status === 'failed' ? 'danger' : 'default'}>{row.status ?? '—'}</Badge></td>
                        <td className="py-3 px-4 text-muted-foreground">{row.createdAt ? new Date(row.createdAt).toLocaleString() : '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        ) : tab === 'suppression' && supp ? (
          <>
            <div className="flex items-center justify-between mb-4">
              <span className="text-sm text-muted-foreground">Total: {supp.total}</span>
              {totalPages > 1 && (
                <div className="flex gap-2">
                  <Button variant="ghost" disabled={page === 0} onClick={() => setPage((p) => p - 1)}>Previous</Button>
                  <span className="py-2 text-sm text-muted-foreground">Page {page + 1} of {totalPages}</span>
                  <Button variant="ghost" disabled={page >= totalPages - 1} onClick={() => setPage((p) => p + 1)}>Next</Button>
                </div>
              )}
            </div>
            {supp.items.length === 0 ? (
              <EmptyState title="No suppression entries" description="Bounces and unsubscribes appear here." />
            ) : (
              <div className="overflow-x-auto table-row-hover">
                <table className="w-full text-sm">
                  <thead><tr className="border-b border-border bg-muted/50"><th className="text-left py-3 px-4 font-medium text-muted-foreground">Email / Lead</th><th className="text-left py-3 px-4 font-medium text-muted-foreground">Reason</th><th className="text-left py-3 px-4 font-medium text-muted-foreground">Added</th></tr></thead>
                  <tbody>
                    {supp.items.map((row, i) => (
                      <tr key={row._id ?? i} className="border-b border-border/50">
                        <td className="py-3 px-4 font-mono text-xs text-foreground">{row.email ?? row.leadId ?? '—'}</td>
                        <td className="py-3 px-4 text-muted-foreground">{row.reason ?? '—'}</td>
                        <td className="py-3 px-4 text-muted-foreground">{row.createdAt ? new Date(row.createdAt).toLocaleString() : '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        ) : null}
      </Card>

      <Sheet
        open={detail !== null}
        onClose={() => setDetail(null)}
        title={detail?.type === 'raw' ? 'Raw post' : 'Qualified lead'}
      >
        {detail && <DetailContent type={detail.type} id={detail.id} />}
      </Sheet>
    </div>
  )
}
