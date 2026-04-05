# Production & Dashboard Plan

One personal-user lead generation app: reliable, scalable, and fully controllable from a single dashboard.

---

## 1. Reliability & ease to scale/modify

### 1.1 Pipeline as discrete jobs
- **Stages** are separate runnable jobs: `ingest` → `static_filter` → `ai_score` → `after_filter` → `send_email`.
- Each job has a **DB record** (`pipeline_jobs`): status (pending | running | completed | failed | cancelled), options (platforms, limits), result (counts/error), timestamps.
- **Start/stop/cancel** from the API: start a job (runs in background), cancel sets a flag and stops the process so you can interrupt long runs.
- **Modify**: Add a new stage = add a new job type and a runner function; no change to existing stages.

### 1.2 Configuration in one place
- **Runtime options** (platforms, batch limits, send delay) live in DB (`app_config` collection) or env; dashboard can read/write safe keys so you can change behavior without code deploy.
- **Secrets** (API keys) stay in env only; dashboard never writes secrets.

### 1.3 Scaling (future)
- For single-user, one API process + one runner thread (or subprocess) per job is enough.
- To scale: run the job runner as a separate worker (or use Celery/Redis); API only enqueues jobs. Same DB, same job schema.

---

## 2. Dashboard: Apple-style, full control

### 2.1 Design
- **Apple-style**: Clean, generous whitespace, system font (SF Pro / Inter), rounded corners (12–16px), subtle shadows, light gray backgrounds (#f5f5f7), dark text. Cards with soft borders. Buttons: filled primary (blue) and ghost secondary.
- **Responsive**: Usable on desktop and tablet; mobile as a bonus.
- **Dark mode** (optional): Toggle; respect system preference.

### 2.2 Pages & capabilities

| Page | Purpose |
|------|--------|
| **Overview** | Stats at a glance (raw posts, qualified, queue pending/sent/failed, suppression). Quick actions: Start ingest, Run filters, etc. Last job status per stage. |
| **Pipeline** | Full control: Start / Stop / Cancel each stage (Ingest, Static filter, AI score, After-filter, Send). Job history table (last N jobs with status, duration, result). Options: platforms, batch size, send delay. |
| **Data** | Browse DB: Raw posts, Qualified leads, Email queue, Suppression list. Tables with filters (status, platform), pagination, and optional row actions (e.g. add to suppression, cancel queued email). |
| **Settings** | View/edit safe config (platforms to scrape, limits, send batch size, delay between sends). Link to env docs for secrets. |
| **Email control** | Dedicated controls: Pause sending (global flag), Resume, Send next N now, Set delay between emails. Queue stats and recent sent/failed. |

### 2.3 Full flexibility
- **DB**: Read all main collections; write where it makes sense (e.g. suppression list, cancel pending email, update config).
- **Process**: Start any stage from the UI; stop/cancel running job; no need to SSH or run CLI for normal ops.
- **Send**: Start/stop/pause sending; set delay; cap batch size from the UI.

---

## 3. Production-grade workflow (single user)

### 3.1 Stage flow (what you can start/stop)
1. **Ingest** — Scrape posts (Apify). Options: platforms, limit. Can cancel mid-run.
2. **Static filter** — Score raw_posts, set status filtered/rejected. No options; fast.
3. **AI score** — LLM scores filtered leads; qualified → qualified_leads. Options: limit.
4. **After-filter** — For each qualified: fetch post, profile, web research, contact, generate email, add to queue. Options: limit.
5. **Send** — Send queued emails via SES. Options: limit, delay (ms) between sends. Can pause/cancel.

### 3.2 Control from dashboard
- **Start** a stage: clicks “Run Ingest” (or other stage) → API creates job, runs in background, UI shows “Running” and can “Cancel”.
- **Stop**: Cancel button sets cancel and kills the running process (or signals worker to stop after current item if we add that later).
- **Delay**: For send stage, “Delay between emails” (e.g. 30s) is an option when starting send job; or a global config the sender reads.
- **Pause sending**: Global flag in `app_config`: `sending_paused: true`. Sender checks before each email and skips if paused.

### 3.3 What is stored
- **pipeline_jobs**: Every run of each stage (who started it, when, status, result).
- **app_config**: `sending_paused`, `send_delay_ms`, `send_batch_size`, `default_platforms`, etc.
- Existing collections unchanged: raw_posts, qualified_leads, email_queue, suppression_list, enriched_*, pipeline_state.

---

## 4. Implementation summary

| Component | Description |
|-----------|-------------|
| **API (FastAPI)** | Already has read-only stats, raw_posts, qualified_leads, email_queue, suppression. Add: `POST/GET /api/jobs`, `POST /api/jobs/{id}/cancel`, `GET/PUT /api/config`, `POST /api/email/pause`, `POST /api/email/resume`, `PUT /api/email_queue/{id}/cancel`. |
| **Job runner** | Lives in API process (or separate worker). On “start job”: create job doc, run pipeline step in subprocess (or thread that runs CLI). On “cancel”: kill subprocess and set job status cancelled. |
| **Dashboard (React + Vite + Tailwind)** | New app under `services/dashboard/`. Pages: Overview, Pipeline, Data, Settings, Email. Apple-style Tailwind theme. Calls API for all data and actions. |
| **Pipeline** | Minimal change: ensure `run_pipeline` can be invoked with `--ingest-only`, `--filter-only`, `--ai-only`, `--no-email`, `--send-only`, `--platforms`. Already does. Optional: read `send_delay` and `sending_paused` from DB in ses_sender. |

---

## 5. File layout (after implementation)

```
lead-generation/
  docs/
    PRODUCTION_DASHBOARD_PLAN.md   # this file
  pipeline/
    run_pipeline.py               # unchanged CLI; invoked by job runner
    ...
  services/
    api/
      main.py                     # existing + jobs, config, email control routes
      db.py
      serialize.py
      job_runner.py               # NEW: start/cancel jobs, subprocess management
      routers/
        jobs.py
        config.py
        email_control.py
    dashboard/
      package.json
      vite.config.ts
      index.html
      src/
        App.tsx
        pages/
          Overview.tsx
          Pipeline.tsx
          Data.tsx
          Settings.tsx
          EmailControl.tsx
        components/
          ...
        api.ts                    # fetch wrappers for API
```

---

## 6. Security (single user)

- No auth in v1 (localhost / single user). For exposure later: add API key or simple login and use CORS + auth on API.
- Config edits: only allowlisted keys (no writing MONGODB_URI, APIFY_TOKEN, etc. from UI).
