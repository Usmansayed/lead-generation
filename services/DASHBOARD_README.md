# Lead Gen Dashboard

Modern dark-theme dashboard (shadcn-style) to view all pipeline data without touching the database.

## What you get

- **Dashboard** — Stats (posts scraped, passed filter, AI qualified, email queue), pipeline last run, status distribution chart.
- **Raw Posts** — All scraped posts with status, score, author, content preview; filter by status/platform; pagination.
- **Filter Results** — Static filter outcome: passed vs rejected with reject reason.
- **AI Qualified** — Leads that passed AI scoring (content, aiScore, intentLabel).
- **Email Queue** — Pending/sent/failed jobs with to, subject, dates, errors.
- **Suppression List** — Do-not-email list.
- **Pipeline State** — Last run time and per-platform cursors.

## Run it

1. **Backend (API)** — From project root or `services/api`:
   ```bash
   cd services/api
   pip install -r requirements.txt
   # Set MONGODB_URI in .env at project root (or export it)
   uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```
   The API reads from the same MongoDB as the pipeline (MONGODB_URI / .env).

2. **Frontend** — From `services/frontend`:
   ```bash
   cd services/frontend
   npm install
   npm run dev
   ```
   Opens at http://localhost:3000. Vite proxies `/api` to http://localhost:8000.

## Tech

- **API:** FastAPI, PyMongo, read-only endpoints.
- **Frontend:** React, Vite, Tailwind (dark theme, HSL variables), Recharts, Lucide icons. No database access from the browser—everything via the API.
