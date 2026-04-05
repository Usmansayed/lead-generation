import { useState, useEffect } from 'react'
import { dashboardAPI } from '../services/api'
import { Card, CardContent, CardHeader, CardTitle } from '../components/Card'
import { Badge } from '../components/Badge'
import { RefreshCw } from 'lucide-react'

function PipelineState() {
  const [state, setState] = useState(null)
  const [loading, setLoading] = useState(true)

  const fetchData = async () => {
    setLoading(true)
    try {
      const res = await dashboardAPI.getPipelineState()
      setState(res)
    } catch (e) {
      setState(null)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
  }, [])

  if (loading) {
    return (
      <div className="flex justify-center py-12">
        <RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  const lastRun = state?.lastRunAt ? new Date(state.lastRunAt) : null
  const cursors = state?.cursors ?? {}

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold tracking-tight">Pipeline State</h2>
      <Card>
        <CardHeader>
          <CardTitle>Ingestion state</CardTitle>
          <p className="text-muted-foreground text-sm mt-1">
            Used for continuous runs: last run time and per-platform cursors (e.g. Reddit after_utc) for incremental fetch.
          </p>
        </CardHeader>
        <CardContent className="space-y-6">
          <div>
            <p className="text-sm font-medium text-muted-foreground mb-1">Last run</p>
            <p className="text-lg font-medium">
              {lastRun ? lastRun.toLocaleString() : 'Never'}
            </p>
          </div>
          <div>
            <p className="text-sm font-medium text-muted-foreground mb-2">Cursors (per platform)</p>
            {Object.keys(cursors).length === 0 ? (
              <p className="text-muted-foreground text-sm">No cursors stored.</p>
            ) : (
              <div className="flex flex-wrap gap-2">
                {Object.entries(cursors).map(([platform, ts]) => (
                  <Badge key={platform} variant="secondary" className="font-mono">
                    {platform}: {typeof ts === 'number' ? new Date(ts * 1000).toISOString() : String(ts)}
                  </Badge>
                ))}
              </div>
            )}
          </div>
          <button
            onClick={fetchData}
            className="inline-flex items-center gap-2 rounded-md border border-border px-3 py-2 text-sm hover:bg-accent"
          >
            <RefreshCw className="h-4 w-4" /> Refresh
          </button>
        </CardContent>
      </Card>
    </div>
  )
}

export default PipelineState
