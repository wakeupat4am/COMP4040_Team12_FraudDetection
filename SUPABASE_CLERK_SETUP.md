# Supabase + Clerk Setup Handoff

## Architecture Implemented

This project now uses:

- Clerk for browser authentication and user sessions.
- FastAPI for backend authorization and business logic.
- Supabase as the managed Postgres database behind FastAPI.
- The frontend does not query Supabase tables directly.

The browser signs in with Clerk, asks Clerk for a session token, and sends that token to FastAPI as:

```http
Authorization: Bearer <clerk-session-token>
```

FastAPI verifies the Clerk token, reads the Clerk user ID from the JWT `sub` claim, then looks up the internal user row by `users.clerk_user_id`. Internal roles remain stored in the project database.

## Why This Boundary

Clerk is better for the app's login/session UX.

Supabase is used as Postgres infrastructure, not as the frontend auth provider. That keeps fraud workflow tables private behind the backend instead of exposing them through browser Supabase SDK access.

RLS is still useful in Supabase as defense in depth, especially for tables in exposed schemas, but the current runtime access path is backend-only through SQLAlchemy using `DATABASE_URL`.

## Backend Changes

Implemented:

- Removed the local `/auth/login` password flow.
- Added `GET /me` for authenticated role/session lookup.
- Added Clerk JWT verification using `PyJWT[crypto]`.
- Added `CLERK_JWT_KEY`, `CLERK_JWT_ALGORITHMS`, `CLERK_ISSUER`, and `CLERK_AUDIENCE` settings.
- Added `users.clerk_user_id`.
- Made `users.password_hash` nullable for migration away from local passwords.
- Kept internal roles in the database:
  - `analyst`
  - `manager_admin`
- Bootstrapped the two configured users from:
  - `ANALYST_CLERK_USER_ID`
  - `MANAGER_CLERK_USER_ID`
- Removed the old custom password hashing and local JWT helper.

## Frontend Changes

Implemented:

- Installed `@clerk/nextjs`.
- Wrapped the app with `ClerkProvider`.
- Added Clerk middleware.
- Replaced the old username/password login page with Clerk `<SignIn />`.
- Updated the frontend auth provider to:
  - use Clerk session state,
  - call `getToken()`,
  - call backend `/me`,
  - store the backend role in React state.
- Updated authenticated API requests to send Clerk bearer tokens.
- Removed old sessionStorage-based auth helper.

## Database Changes

Added migrations:

- `migrations/0003_clerk_users.sql`
- `alembic/versions/20260604_0003_clerk_users.py`

Schema change:

```sql
ALTER TABLE users
ADD COLUMN clerk_user_id VARCHAR(255) NULL;

ALTER TABLE users
ALTER COLUMN password_hash DROP NOT NULL;

CREATE UNIQUE INDEX ix_users_clerk_user_id ON users(clerk_user_id);
```

## Required Environment Variables

Backend:

```bash
DATABASE_URL=postgresql+psycopg://...
CLERK_JWT_KEY="-----BEGIN PUBLIC KEY-----\n...\n-----END PUBLIC KEY-----"
CLERK_JWT_ALGORITHMS=RS256
CLERK_ISSUER=
CLERK_AUDIENCE=
ANALYST_USERNAME=analyst
ANALYST_CLERK_USER_ID=user_...
MANAGER_USERNAME=admin
MANAGER_CLERK_USER_ID=user_...
CORS_ALLOWED_ORIGINS=http://localhost:3000
```

Frontend:

```bash
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_...
CLERK_SECRET_KEY=sk_test_...
```

## What You Need To Do Now

1. Create or choose a Clerk application.
2. Get the Clerk publishable key and secret key.
3. Get the Clerk JWT public key or PEM public key for backend verification.
4. Create or identify two Clerk users:
   - one analyst user,
   - one manager/admin user.
5. Copy their Clerk user IDs into:
   - `ANALYST_CLERK_USER_ID`
   - `MANAGER_CLERK_USER_ID`
6. Create or choose a Supabase project.
7. Copy the Supabase Postgres connection string into `DATABASE_URL`.
8. Run the database migration against the Supabase Postgres database.
9. Start the backend and frontend.
10. Sign in through Clerk and confirm `/me` returns the expected backend role.

## Verification Already Completed

The local test suite passed after implementation:

```bash
PYTHONPATH=src pytest -q
```

Result:

```text
15 passed
```

Frontend checks passed:

```bash
npm run typecheck
npm test
```

## Important Notes

- Do not expose Supabase service-role keys to the frontend.
- Do not add browser Supabase SDK table access unless you also design RLS policies for every exposed table.
- Clerk is the identity provider, but backend roles are still controlled by the internal `users` table.
- If a Clerk user can sign in but sees a backend role-mapping error, their Clerk user ID is missing from the `users` table or from the configured bootstrap env vars.
