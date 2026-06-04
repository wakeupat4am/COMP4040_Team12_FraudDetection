# Milestone Status

Generated from the current repository state on 2026-06-04.

## Product Context

This project is an explainable fraud detection system for online transactions. It turns a raw transaction request into a fraud score, routing decision, per-model scores, and analyst-facing explanations.

The selected production-candidate ensemble combines:

- LightGBM for tabular transaction and history features
- AdaBoost for high-recall tabular fraud detection
- Event-Based GNN for temporal and relational event context

The system has moved beyond notebooks into a local product slice with:

- a validated scoring runtime in `end_to_end/`
- a packaged FastAPI backend in `src/fraud_detection/api/`
- persistent workflow tables for cases, reviews, feedback, audit logs, score runs, and monitoring events
- a Next.js analyst dashboard in `web/`
- Docker Compose orchestration for API, Postgres, and web

## Completed

### Milestone 0: Research and Model Selection

Status: Done

Completed work:

- Compared fraud models on PaySim and S-FFSD.
- Identified PaySim shortcut-signal risk and selected S-FFSD as the primary final-selection dataset.
- Selected the production-candidate ensemble of LightGBM, AdaBoost, and Event-Based GNN.
- Documented model rationale and reported final metrics in `fraud_detection_quick_overview.md`.
- Preserved final report artifacts, comparison tables, figures, and notebooks.

Evidence in repo:

- `fraud_detection_quick_overview.md`
- `Final_Report/`
- `figures/`
- `notebooks/`
- `end_to_end/ensemble_decision.md`

### Milestone 1: Runnable End-to-End Scoring Runtime

Status: Done

Completed work:

- Added raw transaction validation through `end_to_end/input_schema.json`.
- Built an end-to-end scoring pipeline in `end_to_end/pipeline.py`.
- Added internal feature construction from historical transaction state.
- Added LightGBM, AdaBoost, and Event-GNN scoring wrappers.
- Added calibration, weighted ensemble scoring, risk bucket assignment, and routing decision logic.
- Added structured output schema in `end_to_end/output_schema.json`.
- Added explanation helpers for tabular factors, event context, and state availability.

Evidence in repo:

- `end_to_end/pipeline.py`
- `end_to_end/feature_builder.py`
- `end_to_end/model_loader.py`
- `end_to_end/tabular_inference.py`
- `end_to_end/event_gnn_inference.py`
- `end_to_end/explanations.py`
- `end_to_end/pipeline_config.json`
- `tests/test_end_to_end_state.py`

### Milestone 2: Backend-First Production Slice

Status: Done

Completed work:

- Created a packaged FastAPI backend under `src/fraud_detection/api/`.
- Added login/auth service and role-based access for analysts and manager admins.
- Added backend routes for scoring, case queue, case detail, analyst decision, rescore, and metrics.
- Added SQLAlchemy models for users, scored cases, score runs, analyst reviews, and audit logs.
- Added migrations and startup support.
- Added backend workflow tests.

Evidence in repo:

- `src/fraud_detection/api/routes.py`
- `src/fraud_detection/services/auth.py`
- `src/fraud_detection/services/cases.py`
- `src/fraud_detection/repositories/workflow.py`
- `src/fraud_detection/models.py`
- `migrations/`
- `alembic/versions/`
- `tests/test_production_api.py`

### Milestone 3: End-to-End Contract Alignment

Status: Done

Completed work:

- Aligned public scoring response fields with the product overview.
- Added `fraud_score`, `threshold`, `model_scores_overview`, and `explanation_summary`.
- Added request alias support for `timestamp` and `location`.
- Added conflict handling when canonical fields and aliases disagree.
- Applied aligned scoring shape to both direct scoring and case-detail `latest_output`.
- Added tests for alias normalization and explanation-summary patterns.

Evidence in repo:

- `src/fraud_detection/runtime.py`
- `src/fraud_detection/api/schemas.py`
- `tests/test_production_api.py`

### Milestone 4: Operational Hardening

Status: Done

Completed work:

- Added dedicated fraud feedback records and API route.
- Added monitoring events for score and rescore operations.
- Captured latency, final score, decision, state availability, event type, actor, and timestamp.
- Added monitoring summary endpoint.
- Added manager-only authorization for metrics and monitoring endpoints.
- Added tests for feedback, monitoring, and role checks.

Evidence in repo:

- `src/fraud_detection/models.py`
- `src/fraud_detection/api/routes.py`
- `src/fraud_detection/repositories/workflow.py`
- `tests/test_production_api.py`

Note:

- Backend monitoring is database-backed through `MonitoringEvent`.
- `end_to_end/README.md` still mentions file-based monitoring as a limitation of the standalone runtime, so that doc should be updated or clarified.

### Milestone 5: Web Analyst Dashboard

Status: Done

Completed work:

- Added a Next.js dashboard under `web/`.
- Added browser login using backend bearer auth.
- Added score intake page for canonical transaction payloads.
- Added filterable case queue.
- Added case detail page with score summary, per-model scores, explanations, original payload, routing metadata, review history, feedback history, and audit trail.
- Added analyst decision, rescore, and confirmed feedback forms.
- Added manager-only metrics and monitoring page.
- Added shared API client, auth provider, guarded pages, and UI components.
- Added frontend tests for API utilities and session helpers.

Evidence in repo:

- `web/app/login/page.tsx`
- `web/app/score/page.tsx`
- `web/app/cases/page.tsx`
- `web/app/cases/[transaction_id]/page.tsx`
- `web/app/metrics/page.tsx`
- `web/lib/api.ts`
- `web/lib/session.ts`
- `web/tests/`

### Milestone 6: Local Deployment and Team Run

Status: Done

Completed work:

- Added Docker Compose stack for Postgres, API, and Next.js web.
- Added backend and frontend Dockerfiles.
- Added environment-driven configuration for database, auth, CORS, seeded users, and frontend API URL.
- Added local runbook with demo credentials and troubleshooting.
- Added demo transaction payload.
- Added health checks for Postgres and API.

Evidence in repo:

- `docker-compose.yml`
- `Dockerfile.api`
- `web/Dockerfile`
- `docs/local_stack.md`
- `docs/demo_transaction.json`
- `server.py`

## Partially Done

### Historical State Layer

Current state:

- Feature construction uses an internal historical state abstraction.
- The active production adapter is still `InMemoryHistoricalStateStore`.
- The runtime can bootstrap demo history, but this state is not durable across process restarts.

Remaining gap:

- Move historical state to a durable backend, likely Postgres or Redis.
- Ensure state updates are idempotent and time-aware.
- Add tests proving state survives restart and only prior events are used.

Evidence:

- `src/fraud_detection/state/in_memory.py`
- `end_to_end/state_store.py`
- `tests/test_end_to_end_state.py`

### Event Graph Operations

Current state:

- Event-GNN scoring uses a local recent-context graph built at request time.
- This supports the current inference contract.

Remaining gap:

- Build and maintain a durable online graph/event context instead of relying only on local in-memory recent windows.
- Add graph freshness, graph size, and graph-context coverage monitoring.

### Monitoring and Metrics

Current state:

- Score and rescore telemetry is persisted in the database.
- Summary endpoints expose total events, average latency, event type counts, and latest event time.

Remaining gap:

- Add drift, data-quality, and model-health analytics.
- Add time-windowed monitoring rather than only aggregate summaries.
- Add alert thresholds for latency, missing state, high fraud-rate shifts, and score distribution shifts.

## Not Yet Done

### Supabase + Clerk Platform Integration

Needed work:

- Decide the production ownership boundary between Supabase and the existing SQLAlchemy/Postgres backend.
- Move from local Postgres-only development to a Supabase-backed Postgres environment.
- Map current workflow tables into Supabase-managed Postgres migrations.
- Add Clerk as the external identity provider for browser login and user/session management.
- Replace or bridge the current local username/password auth with Clerk-issued identity.
- Define backend authorization rules for analyst and manager-admin roles.
- Decide whether role membership lives in Clerk metadata, Supabase tables, or both.
- Add RLS/security review before exposing any Supabase tables through client-facing APIs.

Important design note:

- Do not put authorization decisions in user-editable metadata.
- Keep privileged database access on the backend only.
- If Supabase tables are exposed to the browser, enable RLS and write explicit policies.

### Durable Historical State

Needed work:

- Design historical-state tables or Redis keys for sender, receiver, sender-receiver pair, location, type, and recent global events.
- Implement a production `HistoricalStateStore` adapter.
- Make score-time state reads and post-score state writes reliable.
- Add migration(s), repository code, and restart-persistence tests.
- Use Redis as the first low-latency state/cache backend for online scoring context.
- Decide whether Redis is the source of truth or a cache in front of Supabase/Postgres.
- Add cache warmup/rebuild logic from durable transaction history if Redis is not the source of truth.

### Drift and Retraining Operations

Needed work:

- Define drift metrics for transaction amount, type, location, sender/receiver behavior, model scores, and decisions.
- Build time-windowed reporting APIs.
- Connect confirmed feedback labels to evaluation datasets.
- Add retraining/evaluation scripts or jobs.
- Track model versions, calibration versions, threshold versions, and deployment metadata.
- Add MLflow for experiment tracking, model registry, model version metadata, metrics, artifacts, and promotion stages.
- Record the MLflow model version or run ID on every score run.
- Store evaluation outputs, calibration artifacts, and threshold-selection evidence in MLflow.

### Threshold and Policy Management

Needed work:

- Move thresholds and routing policy out of static config into versioned operational configuration.
- Support auditability for threshold changes.
- Add manager/admin UI or API for policy inspection and controlled updates.

### Production Security Hardening

Needed work:

- Replace default demo credentials in real deployments.
- Add stronger password policy and operational user management.
- Add token rotation/session invalidation if required.
- Review CORS and secret handling for non-local environments.

### Production Observability

Needed work:

- Integrate logs, traces, and metrics with an external telemetry stack.
- Add structured error tracking.
- Add API latency and failure-rate dashboards.
- Add model scoring failure alerts.

### CI/CD and Deployment

Needed work:

- Add automated backend tests, frontend tests, lint/typecheck, and build verification in CI.
- Add deployment documentation for the target environment.
- Add database migration workflow for shared environments.

## Updated Future Milestone Roadmap

### Milestone 7: Supabase, Clerk, and Redis Platform Foundation

Goal:

Move the product from a local-only demo stack toward a production platform foundation with managed persistence, external auth, and durable low-latency scoring context.

Suggested scope:

- Provision Supabase Postgres for workflow persistence.
- Port existing database schema and migrations to the Supabase-backed environment.
- Add Clerk for user authentication and browser session management.
- Replace or bridge current local bearer-token login with Clerk identity.
- Define analyst and manager-admin authorization mapping.
- Add Redis for historical scoring state, recent event windows, and optional cache acceleration.
- Implement a Redis-backed `HistoricalStateStore`.
- Decide the source-of-truth model between Supabase/Postgres and Redis.
- Add state rebuild or cache warmup from durable transaction/case history.
- Add security review for Supabase table exposure, RLS, service keys, and Clerk role claims.
- Update local and team runbook documentation for the new services.

Exit criteria:

- The web app authenticates through Clerk.
- Backend APIs authorize users based on the new identity/role model.
- Workflow data persists in Supabase Postgres.
- Historical scoring context survives backend restarts through Redis or Redis plus Supabase/Postgres rebuild.
- Existing score, queue, detail, decision, rescore, feedback, metrics, and monitoring tests are updated for the new infrastructure boundary.

### Milestone 8: MLflow Model Registry and Lifecycle Operations

Goal:

Add model lifecycle tracking so every score can be traced to model, calibrator, threshold, and evaluation artifacts.

Suggested scope:

- Add MLflow experiment tracking for training and evaluation runs.
- Register LightGBM, AdaBoost, Event-GNN, calibrators, and ensemble policy artifacts.
- Store model version, run ID, artifact URI, calibration version, and threshold version with each score run.
- Add model metadata to `case_score_runs` or a related model-version table.
- Add feedback export for evaluation/retraining datasets.
- Add evaluation scripts that log metrics and artifacts to MLflow.
- Add promotion workflow for candidate, staging, and production model versions.
- Update backend runtime to load configured production model versions.

Exit criteria:

- Every score run is auditable back to MLflow model/run metadata.
- Confirmed feedback can be exported as labeled evaluation data.
- Evaluation metrics and artifacts are logged in MLflow.
- Production runtime can identify which model versions are active.

### Milestone 9: Drift, Threshold, and Policy Operations

Goal:

Move from basic aggregate monitoring to operational model governance.

Suggested scope:

- Add time-windowed monitoring summary.
- Add score distribution, feature distribution, state-availability, and latency drift reports.
- Add threshold and routing-policy versioning.
- Add manager/admin API or UI for policy inspection.
- Add alerts or report flags for abnormal fraud-rate shifts, missing state, and latency spikes.
- Add comparison reports between current and candidate MLflow model versions.
- Add regression tests for drift summaries, policy-version auditability, and candidate-model comparison reports.
- Update stale runtime documentation around monitoring limitations.

Exit criteria:

- Monitoring can be filtered by time window.
- Drift and data-quality summaries are available to manager admins.
- Threshold and policy versions are auditable.
- Candidate model versions can be evaluated against feedback and historical cases before promotion.
