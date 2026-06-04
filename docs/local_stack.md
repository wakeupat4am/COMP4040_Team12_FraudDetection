# Local Stack Runbook

This repo now supports a Milestone 6 local stack for:

- `postgres`
- the FastAPI backend on `http://localhost:8000`
- the Next.js dashboard on `http://localhost:3000`

## Quick Start

1. Copy the root environment template:

   ```powershell
   Copy-Item .env.example .env
   ```

2. Start the local stack:

   ```powershell
   docker compose up --build
   ```

3. Open the dashboard:

   - Web UI: `http://localhost:3000`
   - API health: `http://localhost:8000/health`

## Seeded Demo Users

The backend bootstraps two users automatically on startup from environment variables:

- Analyst:
  - username: `analyst`
  - password: `changeme-analyst`
- Manager admin:
  - username: `admin`
  - password: `changeme-admin`

You can override those credentials in `.env` before the first run.

## Demo Transaction Payload

Use the browser score-intake page or the sample payload in [demo_transaction.json](demo_transaction.json).

If you want to submit through the API directly:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://localhost:8000/auth/login `
  -ContentType 'application/json' `
  -Body '{"username":"analyst","password":"changeme-analyst"}'
```

Then use the returned bearer token against `POST /score`.

## Troubleshooting

- `web` cannot reach the API:
  - confirm `NEXT_PUBLIC_API_BASE_URL` is `http://localhost:8000` in `.env`
  - restart with `docker compose up --build` after changing public frontend env vars
- `api` cannot connect to Postgres:
  - verify `DATABASE_URL`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, and `POSTGRES_DB`
  - inspect `docker compose logs postgres api`
- credentials do not work:
  - check whether the container was started with different env vars
  - inspect `docker compose logs api` for bootstrap failures
- you want a non-Docker fallback:
  - run `python server.py` for the backend
  - run `npm install` and `npm run dev` inside `web/`
