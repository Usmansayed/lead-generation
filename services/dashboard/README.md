# Lead Gen Dashboard

Apple-style UI to control the pipeline and manage data. Requires the API to be running.

## Run

1. **Start the API** (from project root or `services/api`):
   ```bash
   cd services/api
   uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```
   Ensure `MONGODB_URI` is set (e.g. in `.env` at project root).

2. **Start the dashboard**:
   ```bash
   cd services/dashboard
   npm install
   npm run dev
   ```
   Open http://localhost:3000. The dev server proxies `/api` to port 8000.

## Pages

- **Overview** — Stats (raw posts, qualified, queue, suppression) and quick links.
- **Pipeline** — Start/cancel each stage: Scrape posts, Static filter, AI scoring, Research & email queue, Send emails. Job history table.
- **Data** — Browse raw posts, qualified leads, email queue (tabs).
- **Email** — Pause/resume sending, view pending queue.
- **Settings** — Edit safe config (sending paused, send delay, batch size).

## Build

```bash
npm run build
```
Output in `dist/`. Serve with any static host; set API base URL via env if not same origin.
