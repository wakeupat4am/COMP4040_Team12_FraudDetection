# Local Stack Runbook

This repo supports a local stack for:

- `postgres`
- the FastAPI backend on `http://localhost:8000`
- the Next.js dashboard on `http://localhost:3000`
- Clerk browser authentication

## Quick Start

1. Copy the root environment template:

   ```powershell
   Copy-Item .env.example .env
   ```

2. Create or link a Clerk app, then fill these values in `.env`:

   ```text
   NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=...
   CLERK_SECRET_KEY=...
   CLERK_JWT_KEY="-----BEGIN PUBLIC KEY-----\n...\n-----END PUBLIC KEY-----"
   ANALYST_CLERK_USER_ID=user_...
   MANAGER_CLERK_USER_ID=user_...
   ```

   The `ANALYST_USERNAME` and `MANAGER_USERNAME` values are display names stored in the workflow database.

3. Start the local stack:

   ```powershell
   docker compose up --build
   ```

3. Open the dashboard:

   - Web UI: `http://localhost:3000`
   - API health: `http://localhost:8000/health`

## User Mapping

Clerk owns sign-in and session management. The backend maps Clerk user IDs to internal workflow users on startup:

- `ANALYST_CLERK_USER_ID` -> role `analyst`
- `MANAGER_CLERK_USER_ID` -> role `manager_admin`

Use `GET /me` with a Clerk bearer token to verify that the backend role mapping is configured.

## Demo Transaction Payload

Use the browser score-intake page or the sample payload in [demo_transaction.json](demo_transaction.json).

If you want to submit through the API directly, get a Clerk session token from the signed-in browser session or a Clerk test token, then send it as `Authorization: Bearer <token>` against `POST /score`.

## Supabase Postgres

For Supabase-backed persistence, set `DATABASE_URL` to the Supabase Postgres connection string. The browser still talks only to FastAPI; do not expose workflow tables through the Supabase Data API unless you also add explicit grants and RLS policies.

## Troubleshooting

- `web` cannot reach the API:
  - confirm `NEXT_PUBLIC_API_BASE_URL` is `http://localhost:8000` in `.env`
  - restart with `docker compose up --build` after changing public frontend env vars
- `api` cannot connect to Postgres:
  - verify `DATABASE_URL`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, and `POSTGRES_DB`
  - inspect `docker compose logs postgres api`
- sign-in works but the dashboard shows missing role mapping:
  - verify the Clerk user ID is present in `ANALYST_CLERK_USER_ID` or `MANAGER_CLERK_USER_ID`
  - restart the API so startup can seed the internal user row
  - call `GET /me` with the Clerk bearer token
- you want a non-Docker fallback:
  - run `python server.py` for the backend
  - run `npm install` and `npm run dev` inside `web/`
