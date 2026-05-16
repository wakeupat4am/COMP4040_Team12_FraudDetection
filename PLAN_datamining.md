# Production Fraud Analyst Dashboard with Next.js

## Summary
Build a v1 internal fraud-operations console around the existing `end_to_end` fraud scoring contract, with a separated web architecture:
- `FastAPI` backend for scoring, case queue, analyst actions, auth, and audit APIs
- `Next.js` frontend for the analyst dashboard
- `Postgres` for scored cases, analyst decisions, notes, and audit history
- local-team-run deployment first via `docker-compose`, with clean separation for later internal hosting

The product remains analyst-first and fraud-only in v1. It will support:
- viewing a batch case queue of previously scored events
- drilling into model scores and explanation evidence per case
- re-scoring a selected case on demand
- recording analyst decisions and notes
- internal authenticated access with basic role-based permissions

## Implementation Changes
### 1. Backend service
- Add a `FastAPI` app under `src/fraud_detection/api/` as the production backend boundary.
- Refactor `end_to_end/pipeline.py` into reusable service-layer scoring functions so the API can call the scoring pipeline directly.
- Expose these endpoints:
  - `POST /score`
  - `POST /score/rescore/{event_id}`
  - `GET /cases`
  - `GET /cases/{event_id}`
  - `POST /cases/{event_id}/decision`
  - `GET /metrics/summary`
  - auth/session endpoints for internal login
- Separate backend concerns into:
  - validation and request orchestration
  - scoring/model adapters
  - explanation assembly
  - persistence
  - auth and audit logging

### 2. Frontend web app
- Add a `Next.js` app in a dedicated `web/` workspace.
- Use the App Router and TypeScript.
- Use server-side data fetching for queue/detail pages where possible, with client components only for interactive filters, rescore actions, and decision forms.
- Build these routes:
  - `/login`
  - `/cases`
  - `/cases/[eventId]`
  - `/metrics`
- Build these main UI areas:
  - queue table with filters, pagination, risk/status badges, and quick navigation
  - case detail layout with event metadata, final score/decision summary, model score comparison, explanation panels, and state-availability warnings
  - analyst review panel for `allow/review/block` and notes
  - summary metrics page for aggregate operational visibility
- Use a component library suitable for internal ops tools, such as `shadcn/ui` plus Tailwind, to keep the UI structured but flexible.
- Treat the Next.js app as a real product frontend, not a thin demo shell:
  - route-level loading and error states
  - empty states for no cases / no evidence
  - optimistic or immediate feedback for analyst actions
  - session-aware navigation and protected routes

### 3. Scoring and explanation integration
- Preserve the existing `FraudPipelineOutput` as the base scoring contract.
- Extend API response models with persisted dashboard metadata:
  - `scored_at`
  - `status`
  - `current_analyst_decision`
  - `analyst_note`
  - `decision_updated_at`
- Implement model adapter interfaces for:
  - `event_gnn`
  - `adaboost`
  - `lightgbm`
- Keep weighted averaging from `pipeline_config.json` as the v1 production ensemble.
- Upgrade `explanation_stub` into a structured evidence payload suitable for UI rendering:
  - top tabular contributors
  - event/graph context references
  - required-history / graph-state availability
- Keep advanced graph/text explainers optional; v1 only needs stable evidence objects the frontend can display consistently.

### 4. Data model and persistence
- Add `Postgres` with migrations.
- Create these core tables:
  - `scored_events`
  - `analyst_reviews`
  - `users`
  - `audit_logs`
- Store the original request payload JSON for reproducible rescore behavior.
- Store explanation payload as JSON.
- Use `event_id` as the primary business identifier across API and frontend routes.

### 5. Auth and access model
- Use internal authenticated access with basic role separation:
  - `analyst`: view queue, inspect cases, submit decisions
  - `manager_admin`: view metrics, manage users/config visibility if needed
- Keep auth simple for v1:
  - backend-issued session or JWT-based auth
  - frontend route protection in Next.js
  - audit log entries for login and case actions
- Defer enterprise SSO, but keep auth isolated so SSO can replace it later without changing core case APIs.

### 6. Deployment and runtime
- Add `docker-compose` for local team run with at least:
  - `api`
  - `web`
  - `postgres`
- Keep configuration environment-driven:
  - backend env for DB, model paths, secrets, pipeline config
  - frontend env for backend base URL and session config
- Add bootstrap tooling to seed sample scored cases for local testing and frontend development.

## Public Interfaces and Contracts
- Preserve `end_to_end/input_schema.json` as the scoring request contract.
- Preserve `end_to_end/output_schema.json` as the base scoring output contract.
- Add API response models that wrap or extend the base scoring output with persistence and analyst-workflow metadata.
- Add analyst decision request contract:
  - `event_id`
  - `analyst_decision` in `allow|review|block`
  - `note`
- Add queue/filter query parameters:
  - `risk_bucket`
  - `decision`
  - `status`
  - `dataset_family`
  - `date_from`
  - `date_to`
  - `page`
  - `page_size`

## Test Plan
- Backend unit tests for:
  - request validation
  - ensemble score calculation and threshold mapping
  - analyst decision validation
  - response shaping for queue and detail endpoints
- Backend integration tests for:
  - scoring and persistence
  - queue filtering
  - case detail retrieval
  - rescore flow
  - analyst decision submission and audit creation
- Frontend tests for:
  - queue page render, filtering, and pagination
  - case detail render for full and partial evidence payloads
  - decision form submission and success/error handling
  - protected route behavior for authenticated vs unauthenticated users
- Acceptance scenarios:
  - analyst opens `/cases`, filters high-risk cases, reviews a case, submits a decision, and sees updated state
  - analyst re-scores a case and sees refreshed model outputs
  - a case with missing history/graph context shows clear warnings instead of broken UI
  - manager/admin can access summary metrics without interfering with analyst flow

## Assumptions and Defaults
- Scope is fraud operations only; churn remains out of v1.
- Primary users are fraud analysts.
- Case intake is batch queue plus on-demand rescore, not live streaming.
- The dashboard owns analyst decisions and notes, but not downstream write-back into external order systems yet.
- Delivery stack is `Next.js + FastAPI + Postgres + docker-compose`.
- Deployment target is local team run first.
- Next.js is the primary frontend surface; no Streamlit or Python-rendered dashboard is included.
- Weighted ensemble remains the production decisioning method until a trained meta-model replaces it.
