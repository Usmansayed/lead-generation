import { useEffect, useState } from 'react'
import { getConfig, updateConfig } from '../api'
import { PageHeader, Card, Button, LoadingState, Alert } from '../components/ui'

const SCRAPING_PLATFORMS = [
  { id: 'reddit', label: 'Reddit' },
  { id: 'twitter', label: 'Twitter' },
  { id: 'instagram', label: 'Instagram' },
  { id: 'facebook', label: 'Facebook' },
  { id: 'linkedin', label: 'LinkedIn' },
]

export default function Settings() {
  const [config, setConfig] = useState<Record<string, unknown> | null>(null)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [local, setLocal] = useState<{ sending_paused?: boolean; send_delay_ms?: number | ''; send_batch_size?: number | ''; default_platforms?: string[]; keywords_override?: string }>({})

  useEffect(() => {
    getConfig()
      .then((c) => {
        setConfig(c)
        const platforms = (c.default_platforms as string[] | undefined) ?? SCRAPING_PLATFORMS.map((p) => p.id)
        const kw = c.keywords_override as string[] | undefined
        setLocal({
          sending_paused: c.sending_paused as boolean,
          send_delay_ms: (c.send_delay_ms as number) ?? '',
          send_batch_size: (c.send_batch_size as number) ?? '',
          default_platforms: Array.isArray(platforms) ? platforms : SCRAPING_PLATFORMS.map((p) => p.id),
          keywords_override: Array.isArray(kw) ? kw.join('\n') : '',
        })
      })
      .catch((e) => setError(e.message))
  }, [])

  const handleSave = (key: string, value: unknown) => {
    setSaving(true)
    setError(null)
    updateConfig({ [key]: value })
      .then((c) => {
        setConfig(c)
        // For keywords_override, store display string (joined) not array
        const displayValue = key === 'keywords_override' && Array.isArray(value)
          ? value.join('\n')
          : value
        setLocal((prev) => ({ ...prev, [key]: displayValue }))
      })
      .catch((e) => setError(e.message))
      .finally(() => setSaving(false))
  }

  const togglePlatform = (id: string) => {
    const current = local.default_platforms ?? SCRAPING_PLATFORMS.map((p) => p.id)
    const next = current.includes(id) ? current.filter((p) => p !== id) : [...current, id]
    setLocal((p) => ({ ...p, default_platforms: next }))
    handleSave('default_platforms', next)
  }

  const selectAllPlatforms = () => {
    const next = SCRAPING_PLATFORMS.map((p) => p.id)
    setLocal((p) => ({ ...p, default_platforms: next }))
    handleSave('default_platforms', next)
  }

  const clearAllPlatforms = () => {
    setLocal((p) => ({ ...p, default_platforms: [] }))
    handleSave('default_platforms', [])
  }

  if (config === null && Object.keys(local).length === 0) return <LoadingState message="Loading settings…" />

  const selectedPlatforms = (local.default_platforms ?? []) as string[]

  return (
    <div className="space-y-8">
      <PageHeader
        title="Settings"
        subtitle="Runtime options. Scraping platforms control which sources the Scrape posts stage uses."
      />
      {error && <Alert variant="error">{error}</Alert>}

      <Card
        title="Scraping platforms"
        subtitle="Choose which platforms to scrape when you run the Scrape posts stage. Turn off one or more to limit sources."
      >
        <div className="space-y-4">
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" onClick={selectAllPlatforms}>All on</Button>
            <Button variant="ghost" onClick={clearAllPlatforms}>All off</Button>
          </div>
          <div className="flex flex-wrap gap-4">
            {SCRAPING_PLATFORMS.map((p) => {
              const checked = selectedPlatforms.includes(p.id)
              return (
                <label key={p.id} className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() => togglePlatform(p.id)}
                    className="rounded border-border bg-background text-primary focus:ring-primary"
                  />
                  <span className="text-sm text-foreground">{p.label}</span>
                </label>
              )
            })}
          </div>
          <p className="text-xs text-muted-foreground">
            Current: {selectedPlatforms.length === 0 ? 'None (run will do nothing)' : selectedPlatforms.join(', ')}
          </p>
        </div>
        {saving && <p className="mt-4 text-sm text-muted-foreground">Saving…</p>}
      </Card>

      <Card title="Sending" subtitle="Control how and when queued emails are sent.">
        <div className="space-y-6 max-w-md">
          <div>
            <label className="block text-sm font-medium text-foreground mb-2">Pause sending</label>
            <p className="text-xs text-muted-foreground mb-2">When on, the Send emails stage will not deliver messages.</p>
            <div className="flex gap-3">
              <button
                type="button"
                onClick={() => handleSave('sending_paused', false)}
                className={`px-4 py-2.5 rounded-lg text-sm font-medium border transition-colors duration-200 cursor-pointer ${
                  local.sending_paused === false ? 'bg-primary text-primary-foreground border-primary' : 'bg-card text-muted-foreground hover:bg-accent border-border'
                }`}
              >
                Off
              </button>
              <button
                type="button"
                onClick={() => handleSave('sending_paused', true)}
                className={`px-4 py-2.5 rounded-lg text-sm font-medium border transition-colors duration-200 cursor-pointer ${
                  local.sending_paused === true ? 'bg-amber-500 text-white border-amber-500' : 'bg-card text-muted-foreground hover:bg-accent border-border'
                }`}
              >
                Paused
              </button>
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-foreground mb-2">Delay between emails (ms)</label>
            <p className="text-xs text-muted-foreground mb-2">Optional. e.g. 30000 = 30 seconds between each send.</p>
            <input
              type="number"
              min={0}
              value={local.send_delay_ms ?? ''}
              onChange={(e) => setLocal((p) => ({ ...p, send_delay_ms: e.target.value ? parseInt(e.target.value, 10) : '' }))}
              onBlur={() => {
                const v = local.send_delay_ms
                if (v !== undefined && v !== '') handleSave('send_delay_ms', v)
              }}
              placeholder="e.g. 30000"
              className="w-full rounded-md border border-border bg-background px-4 py-2.5 text-sm text-foreground placeholder:text-muted-foreground focus:ring-2 focus:ring-ring focus:border-primary"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-foreground mb-2">Send batch size</label>
            <p className="text-xs text-muted-foreground mb-2">Max emails to send per Send emails run.</p>
            <input
              type="number"
              min={1}
              value={local.send_batch_size ?? ''}
              onChange={(e) => setLocal((p) => ({ ...p, send_batch_size: e.target.value ? parseInt(e.target.value, 10) : '' }))}
              onBlur={() => {
                const v = local.send_batch_size
                if (v !== undefined && v !== '') handleSave('send_batch_size', v)
              }}
              placeholder="e.g. 20"
              className="w-full rounded-md border border-border bg-background px-4 py-2.5 text-sm text-foreground placeholder:text-muted-foreground focus:ring-2 focus:ring-ring focus:border-primary"
            />
          </div>
        </div>
        {saving && <p className="mt-4 text-sm text-muted-foreground">Saving…</p>}
      </Card>

      <Card
        title="Keyword overrides"
        subtitle="Extra search keywords merged into Scrape posts. One per line. Applies to all platforms."
      >
        <div className="space-y-2">
          <textarea
            value={local.keywords_override ?? ''}
            onChange={(e) => setLocal((p) => ({ ...p, keywords_override: e.target.value }))}
            onBlur={() => {
              const raw = (local.keywords_override ?? '').trim()
              const list = raw ? raw.split(/[\n,]+/).map((s) => s.trim()).filter(Boolean) : []
              handleSave('keywords_override', list)
            }}
            placeholder={'e.g. looking for developer\nneed a dev\nhiring contractor'}
            rows={4}
            className="w-full rounded-md border border-border bg-background px-4 py-2.5 text-sm text-foreground placeholder:text-muted-foreground focus:ring-2 focus:ring-ring focus:border-primary font-mono"
          />
          <p className="text-xs text-muted-foreground">
            These are merged with YAML keywords. Leave empty to use only YAML config.
          </p>
        </div>
      </Card>
    </div>
  )
}
