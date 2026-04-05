import { useState, useEffect } from 'react'
import { dashboardAPI } from '../services/api'
import { Card, CardContent, CardHeader, CardTitle } from '../components/Card'
import { Badge } from '../components/Badge'
import { DataTable } from '../components/DataTable'
import { RefreshCw, ChevronLeft, ChevronRight } from 'lucide-react'

const PAGE_SIZE = 25

function EmailQueue() {
  const [data, setData] = useState({ items: [], total: 0 })
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(0)
  const [status, setStatus] = useState('')

  const fetchData = async () => {
    setLoading(true)
    try {
      const res = await dashboardAPI.getEmailQueue({
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
    { id: 'status', header: 'Status', cell: (r) => <Badge variant={r.status === 'sent' ? 'success' : r.status === 'failed' ? 'destructive' : 'warning'}>{r.status}</Badge> },
    { id: 'toEmail', header: 'To', cell: (r) => <span className="font-mono text-sm">{r.toEmail || '—'}</span> },
    { id: 'subject', header: 'Subject', cell: (r) => <span className="line-clamp-1 max-w-sm text-muted-foreground">{r.subject || '—'}</span> },
    { id: 'leadId', header: 'Lead ID', cell: (r) => <span className="font-mono text-xs text-muted-foreground truncate max-w-[120px] block" title={r.leadId}>{r.leadId}</span> },
    { id: 'createdAt', header: 'Queued', cell: (r) => r.createdAt ? new Date(r.createdAt).toLocaleString() : '—' },
    { id: 'sentAt', header: 'Sent', cell: (r) => r.sentAt ? new Date(r.sentAt).toLocaleString() : '—' },
    { id: 'error', header: 'Error', cell: (r) => <span className="text-destructive text-xs max-w-[160px] block truncate" title={r.error}>{r.error || '—'}</span> },
  ]

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold tracking-tight">Email Queue</h2>
      <Card>
        <CardHeader>
          <CardTitle>Outbound email jobs</CardTitle>
          <div className="flex flex-wrap gap-3 mt-2">
              <select
                value={status}
                onChange={(e) => { setStatus(e.target.value); setPage(0); }}
                className="rounded-md border border-input bg-background px-3 py-2 text-sm"
              >
                <option value="">All</option>
                <option value="pending">pending</option>
                <option value="sent">sent</option>
                <option value="failed">failed</option>
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
              <DataTable columns={columns} data={data.items} emptyMessage="No email queue items." />
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

export default EmailQueue
