import { useState, useEffect } from 'react'
import { dashboardAPI } from '../services/api'
import { Card, CardContent, CardHeader, CardTitle } from '../components/Card'
import { Badge } from '../components/Badge'
import { DataTable } from '../components/DataTable'
import { RefreshCw, ExternalLink, ChevronLeft, ChevronRight } from 'lucide-react'

const PAGE_SIZE = 25

function FilterResults() {
  const [data, setData] = useState({ items: [], total: 0 })
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(0)
  const [status, setStatus] = useState('') // '' = all, filtered, rejected

  const fetchData = async () => {
    setLoading(true)
    try {
      const res = await dashboardAPI.getRawPosts({
        status: status || undefined,
        limit: PAGE_SIZE,
        skip: page * PAGE_SIZE,
      })
      setData(res)
    } catch (e) {
      setData({ items: [], total: 0 })
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
  }, [page, status])

  const columns = [
    { id: 'platform', header: 'Platform', cell: (r) => <Badge variant="outline">{r.platform}</Badge> },
    { id: 'status', header: 'Status', cell: (r) => <Badge variant={r.status === 'filtered' ? 'success' : 'destructive'}>{r.status}</Badge> },
    { id: 'staticScore', header: 'Score', cell: (r) => r.staticScore ?? '—' },
    { id: 'rejectReason', header: 'Reject reason', cell: (r) => <span className="text-muted-foreground max-w-xs block truncate" title={r.rejectReason}>{r.rejectReason || '—'}</span> },
    { id: 'author', header: 'Author', cell: (r) => (r.author?.name || r.author?.handle) || '—' },
    { id: 'postText', header: 'Content', cell: (r) => <span className="line-clamp-2 max-w-md text-muted-foreground">{(r.postText || '').slice(0, 180)}…</span> },
    { id: 'link', header: '', cell: (r) => r.postUrl ? <a href={r.postUrl} target="_blank" rel="noopener noreferrer" className="text-primary hover:underline inline-flex items-center gap-1"><ExternalLink className="h-3 w-3" /> Open</a> : null },
  ]

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold tracking-tight">Filter Results</h2>
      <Card>
        <CardHeader>
          <CardTitle>Static filter outcome</CardTitle>
          <div className="flex flex-wrap gap-3 mt-2">
              <select
                value={status}
                onChange={(e) => { setStatus(e.target.value); setPage(0); }}
                className="rounded-md border border-input bg-background px-3 py-2 text-sm"
              >
                <option value="">All</option>
                <option value="filtered">Passed (filtered)</option>
                <option value="rejected">Rejected</option>
              </select>
              <button onClick={() => fetchData()} className="inline-flex items-center gap-2 rounded-md border border-border px-3 py-2 text-sm hover:bg-accent">
                <RefreshCw className="h-4 w-4" /> Refresh
              </button>
            </div>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex justify-center py-12"><RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" /></div>
          ) : (
            <>
              <DataTable columns={columns} data={data.items} emptyMessage="No filter results." />
              <div className="flex items-center justify-between mt-4">
                <p className="text-sm text-muted-foreground">Total: {data.total}</p>
                <div className="flex gap-2">
                  <button disabled={page === 0} onClick={() => setPage((p) => p - 1)} className="rounded-md border border-border px-3 py-1 text-sm disabled:opacity-50 hover:bg-accent"><ChevronLeft className="h-4 w-4 inline" /></button>
                  <span className="text-sm py-1">Page {page + 1}</span>
                  <button disabled={(page + 1) * PAGE_SIZE >= data.total} onClick={() => setPage((p) => p + 1)} className="rounded-md border border-border px-3 py-1 text-sm disabled:opacity-50 hover:bg-accent"><ChevronRight className="h-4 w-4 inline" /></button>
                </div>
              </div>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

export default FilterResults
