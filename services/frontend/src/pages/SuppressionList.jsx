import { useState, useEffect } from 'react'
import { dashboardAPI } from '../services/api'
import { Card, CardContent, CardHeader, CardTitle } from '../components/Card'
import { DataTable } from '../components/DataTable'
import { RefreshCw, ChevronLeft, ChevronRight } from 'lucide-react'

const PAGE_SIZE = 50

function SuppressionList() {
  const [data, setData] = useState({ items: [], total: 0 })
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(0)

  const fetchData = async () => {
    setLoading(true)
    try {
      const res = await dashboardAPI.getSuppressionList({ limit: PAGE_SIZE, skip: page * PAGE_SIZE })
      setData(res)
    } catch (e) {
      setData({ items: [], total: 0 })
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
  }, [page])

  const columns = [
    { id: 'leadId', header: 'Lead ID', cell: (r) => <span className="font-mono text-xs truncate max-w-[200px] block" title={r.leadId}>{r.leadId || '—'}</span> },
    { id: 'email', header: 'Email', cell: (r) => <span className="font-mono text-sm">{r.email || '—'}</span> },
    { id: 'reason', header: 'Reason', cell: (r) => r.reason || '—' },
    { id: 'createdAt', header: 'Added', cell: (r) => r.createdAt ? new Date(r.createdAt).toLocaleString() : '—' },
  ]

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold tracking-tight">Suppression List</h2>
      <Card>
        <CardHeader>
          <CardTitle>Do-not-email list</CardTitle>
          <p className="text-muted-foreground text-sm mt-1">
            Leads and addresses that bounced, complained, or unsubscribed. They are skipped when queueing and sending.
          </p>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex justify-center py-12"><RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" /></div>
          ) : (
            <>
              <DataTable columns={columns} data={data.items} keyField="_id" emptyMessage="Suppression list is empty." />
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

export default SuppressionList
