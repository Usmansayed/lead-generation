import { useEffect, useState } from 'react'
import { listLeadsNoEmail, markLeadNoEmailSent, getStats } from '../api'
import type { LeadNoEmail } from '../api'
import { PageHeader, Card, Badge, Button, EmptyState, LoadingState, Alert } from '../components/ui'

type Filter = 'all' | 'pending' | 'sent'

function getMessageForCopy(lead: LeadNoEmail): string {
  const subject = lead.subject ?? ''
  const body = lead.bodyText ?? ''
  if (!subject && !body) return ''
  if (!body) return subject
  return subject ? `${subject}\n\n${body}` : body
}

export default function ManualOutreach() {
  const [items, setItems] = useState<LeadNoEmail[]>([])
  const [, setTotal] = useState(0)
  const [filter, setFilter] = useState<Filter>('pending')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [copyFeedback, setCopyFeedback] = useState<string | null>(null)
  const [markingId, setMarkingId] = useState<string | null>(null)
  const [stats, setStats] = useState<{ leads_no_email?: { pending: number; sent: number } } | null>(null)

  const load = () => {
    const messageSent = filter === 'all' ? undefined : filter === 'sent'
    listLeadsNoEmail({ messageSent, limit: 100, skip: 0 })
      .then((r) => {
        setItems(r.items)
        setTotal(r.total)
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    setLoading(true)
    setError(null)
    getStats().then(setStats).catch(() => {})
    load()
  }, [filter])

  const copyToClipboard = (text: string, label: string) => {
    if (!text) return
    navigator.clipboard.writeText(text).then(
      () => {
        setCopyFeedback(`Copied ${label}`)
        setTimeout(() => setCopyFeedback(null), 2000)
      },
      () => setCopyFeedback(`Failed to copy`)
    )
  }

  const handleMarkSent = (leadId: string) => {
    setMarkingId(leadId)
    markLeadNoEmailSent(leadId)
      .then(() => load())
      .catch((e) => setError(e.message))
      .finally(() => setMarkingId(null))
  }

  const pendingCount = stats?.leads_no_email?.pending ?? 0
  const sentCount = stats?.leads_no_email?.sent ?? 0

  return (
    <div>
      <PageHeader
        title="Leads without email"
        subtitle="Copy username and message to send manually (e.g. DM). Mark as sent when done."
      />

      <div className="mb-6 flex flex-wrap items-center gap-4">
        <div className="flex rounded-xl border border-border bg-muted/20 p-1">
          {(['pending', 'sent', 'all'] as const).map((f) => (
            <button
              key={f}
              type="button"
              onClick={() => setFilter(f)}
              className={`rounded-lg px-4 py-2 text-sm font-medium transition-colors duration-200 cursor-pointer ${
                filter === f ? 'bg-primary text-primary-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground hover:bg-muted/50'
              }`}
            >
              {f === 'pending' ? `Pending (${pendingCount})` : f === 'sent' ? `Sent (${sentCount})` : 'All'}
            </button>
          ))}
        </div>
        {copyFeedback && (
          <span className="text-sm text-muted-foreground animate-pulse">{copyFeedback}</span>
        )}
      </div>

      {error && (
        <div className="mb-4">
          <Alert variant="error">{error}</Alert>
        </div>
      )}

      <Card>
        {loading ? (
          <LoadingState message="Loading leads…" />
        ) : items.length === 0 ? (
          <EmptyState
            title={filter === 'pending' ? 'No pending leads' : filter === 'sent' ? 'No sent yet' : 'No leads'}
            description={
              filter === 'pending'
                ? 'Leads appear here automatically when the pipeline runs (Step 4: after filter). Qualified leads with no email found are added here for manual DM.'
                : undefined
            }
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-muted-foreground">
                  <th className="pb-3 pr-4 font-medium">Username</th>
                  <th className="pb-3 pr-4 font-medium">Platform</th>
                  <th className="pb-3 pr-4 font-medium">Post / Contact</th>
                  <th className="pb-3 pr-4 font-medium">Actions</th>
                  <th className="pb-3 pl-4 font-medium">Message sent</th>
                </tr>
              </thead>
              <tbody>
                {items.map((lead) => {
                  const username = lead.authorHandle || '—'
                  const message = getMessageForCopy(lead)
                  return (
                    <tr key={lead._id} className="border-b border-border/70 last:border-0">
                      <td className="py-3 pr-4 font-mono text-foreground">{username}</td>
                      <td className="py-3 pr-4">
                        <Badge variant="default">{lead.platform || '—'}</Badge>
                      </td>
                      <td className="py-3 pr-4 space-y-1">
                        {lead.postUrl && (
                          <a
                            href={lead.postUrl}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-primary hover:underline block truncate max-w-[200px]"
                          >
                            Post
                          </a>
                        )}
                        {lead.contactValue && (
                          <a
                            href={lead.contactValue.startsWith('http') ? lead.contactValue : `https://${lead.contactValue}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-primary hover:underline block truncate max-w-[200px]"
                          >
                            Profile / Contact
                          </a>
                        )}
                        {!lead.postUrl && !lead.contactValue && '—'}
                      </td>
                      <td className="py-3 pr-4 flex flex-wrap gap-2">
                        <Button variant="ghost" onClick={() => copyToClipboard(username, 'username')} className="text-xs">
                          Copy username
                        </Button>
                        <Button
                          variant="ghost"
                          onClick={() => copyToClipboard(message, 'message')}
                          disabled={!message}
                          className="text-xs"
                        >
                          Copy message
                        </Button>
                      </td>
                      <td className="py-3 pl-4">
                        {lead.messageSent ? (
                          <Badge variant="success">Sent</Badge>
                        ) : (
                          <label className="flex items-center gap-2 cursor-pointer">
                            <input
                              type="checkbox"
                              checked={false}
                              onChange={() => handleMarkSent(lead._id)}
                              disabled={markingId === lead._id}
                              className="rounded border-border"
                            />
                            <span className="text-muted-foreground text-xs">
                              {markingId === lead._id ? 'Updating…' : 'Mark sent'}
                            </span>
                          </label>
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  )
}
