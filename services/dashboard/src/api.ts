const API = '/api';

export type QualifiedBreakdown = {
  in_queue_pending: number;
  in_queue_sent: number;
  in_no_email: number;
  to_process: number;
};

export type Stats = {
  raw_posts: {
    total: number;
    pending_filter: number;
    by_status: Record<string, number>;
    by_platform: Record<string, number>;
  };
  qualified_leads_count: number;
  qualified_breakdown?: QualifiedBreakdown;
  qualified_leads_by_platform?: Record<string, number>;
  email_queue: { pending: number; sent: number; failed: number };
  leads_no_email?: { pending: number; sent: number };
  suppression_count: number;
  seen_post_hashes_count?: number;
  stale?: { raw_stale_count: number; qualified_stale_count: number };
  pipeline_state: { lastRunAt: string | null; cursors: Record<string, unknown> };
  job_summary?: { jobType: string; status: string; count: number }[];
};

export type LeadNoEmail = {
  _id: string;
  leadId?: string;
  platform?: string;
  postUrl?: string;
  authorHandle?: string;
  contactValue?: string;
  subject?: string;
  bodyText?: string;
  messageSent?: boolean;
  createdAt?: string;
  updatedAt?: string;
};

export type Job = {
  _id: string;
  jobType: string;
  status: string;
  options?: Record<string, unknown>;
  createdAt?: string;
  startedAt?: string | null;
  finishedAt?: string | null;
  result?: unknown;
  error?: string | null;
};

export async function getHealth(): Promise<{ ok: boolean }> {
  const r = await fetch(`${API}/health`);
  return r.json();
}

export async function getStats(): Promise<Stats> {
  const r = await fetch(`${API}/stats`);
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function listJobs(params?: { jobType?: string; status?: string; limit?: number; skip?: number }) {
  const q = new URLSearchParams();
  if (params?.jobType) q.set('job_type', params.jobType);
  if (params?.status) q.set('status', params.status);
  if (params?.limit) q.set('limit', String(params.limit));
  if (params?.skip) q.set('skip', String(params.skip));
  const r = await fetch(`${API}/jobs?${q}`);
  if (!r.ok) throw new Error(await r.text());
  return r.json() as Promise<{ items: Job[]; total: number; runningIds: string[] }>;
}

export async function getJob(id: string): Promise<Job> {
  const r = await fetch(`${API}/jobs/${id}`);
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function startJob(body: { jobType: string; options?: Record<string, unknown> }): Promise<Job> {
  console.log('[api] DEBUG POST /api/jobs', body);
  const r = await fetch(`${API}/jobs`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const text = await r.text();
  if (!r.ok) {
    console.error('[api] DEBUG POST /api/jobs failed', r.status, text);
    throw new Error(text);
  }
  const job = JSON.parse(text) as Job;
  console.log('[api] DEBUG POST /api/jobs response', { jobId: job._id, status: job.status });
  return job;
}

export async function cancelJob(id: string): Promise<{ cancelled: boolean }> {
  const r = await fetch(`${API}/jobs/${id}/cancel`, { method: 'POST' });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function getConfig(): Promise<Record<string, unknown>> {
  const r = await fetch(`${API}/config`);
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function updateConfig(updates: Record<string, unknown>): Promise<Record<string, unknown>> {
  const r = await fetch(`${API}/config`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(updates),
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function pauseSending(): Promise<{ paused: boolean }> {
  const r = await fetch(`${API}/email/pause`, { method: 'POST' });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function resumeSending(): Promise<{ paused: boolean }> {
  const r = await fetch(`${API}/email/resume`, { method: 'POST' });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function cancelQueuedEmail(itemId: string): Promise<{ cancelled: boolean }> {
  const r = await fetch(`${API}/email/queue/${itemId}/cancel`, { method: 'PUT' });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function listRawPosts(params?: { status?: string; platform?: string; limit?: number; skip?: number }) {
  const q = new URLSearchParams();
  if (params?.status) q.set('status', params.status);
  if (params?.platform) q.set('platform', params.platform);
  if (params?.limit) q.set('limit', String(params.limit));
  if (params?.skip) q.set('skip', String(params.skip));
  const r = await fetch(`${API}/raw_posts?${q}`);
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function getRawPost(id: string): Promise<Record<string, unknown>> {
  const r = await fetch(`${API}/raw_posts/${encodeURIComponent(id)}`);
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function getQualifiedLead(id: string): Promise<Record<string, unknown>> {
  const r = await fetch(`${API}/qualified_leads/${encodeURIComponent(id)}`);
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function listQualifiedLeads(params?: { platform?: string; limit?: number; skip?: number }) {
  const q = new URLSearchParams();
  if (params?.platform) q.set('platform', params.platform);
  if (params?.limit) q.set('limit', String(params.limit));
  if (params?.skip) q.set('skip', String(params.skip));
  const r = await fetch(`${API}/qualified_leads?${q}`);
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function listEmailQueue(params?: { status?: string; limit?: number; skip?: number }) {
  const q = new URLSearchParams();
  if (params?.status) q.set('status', params.status);
  if (params?.limit) q.set('limit', String(params.limit));
  if (params?.skip) q.set('skip', String(params.skip));
  const r = await fetch(`${API}/email_queue?${q}`);
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function listSuppression(params?: { limit?: number; skip?: number }) {
  const q = new URLSearchParams();
  if (params?.limit) q.set('limit', String(params.limit));
  if (params?.skip) q.set('skip', String(params.skip));
  const r = await fetch(`${API}/suppression_list?${q}`);
  if (!r.ok) throw new Error(await r.text());
  return r.json() as Promise<{ items: { _id?: string; leadId?: string; email?: string; reason?: string; createdAt?: string }[]; total: number }>;
}

export async function listLeadsNoEmail(params?: { messageSent?: boolean; limit?: number; skip?: number }) {
  const q = new URLSearchParams();
  if (params?.messageSent !== undefined) q.set('message_sent', String(params.messageSent));
  if (params?.limit) q.set('limit', String(params.limit));
  if (params?.skip) q.set('skip', String(params.skip));
  const r = await fetch(`${API}/leads_no_email?${q}`);
  if (!r.ok) throw new Error(await r.text());
  return r.json() as Promise<{ items: LeadNoEmail[]; total: number; skip: number; limit: number }>;
}

export async function markLeadNoEmailSent(leadId: string): Promise<{ ok: boolean; messageSent: boolean }> {
  const r = await fetch(`${API}/leads_no_email/${encodeURIComponent(leadId)}/mark_sent`, { method: 'PATCH' });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}
