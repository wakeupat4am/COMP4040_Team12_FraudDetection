# Production Plan: Fraud Scoring Backend to End-to-End Product

## Summary
This plan tracks the path from the validated fraud-scoring runtime to a usable end-to-end fraud operations system.

The repo now includes:
- a packaged FastAPI backend under `src/fraud_detection/api/`
- persisted case workflow state with auth, queue, review actions, rescore, and metrics
- aligned scoring contract fields for the end-to-end overview
- dedicated fraud feedback ingestion
- database-backed monitoring events with latency capture
- a checked-in Next.js analyst dashboard in `web/`
- local frontend-to-backend browser integration via configurable CORS
- local stack orchestration files for api, postgres, and web
- environment templates, demo payloads, and local runbook documentation
- migrations, backend API tests, and frontend verification covering the current milestone set

The immediate next milestone is now durable state and retraining operations:
- replace the in-memory historical-state dependency
- add longer-horizon drift and model lifecycle operations

## Target End-to-End Requirements
The final system should satisfy these product-level requirements from the overview:

1. Accept a raw transaction request without requiring engineered historical or graph features from the caller.
2. Build historical and event-graph context internally.
3. Score the transaction with LightGBM, AdaBoost, and Event-Based GNN.
4. Combine model scores using the selected weighted ensemble.
5. Return a structured fraud response with:
   - fraud score
   - decision
   - threshold
   - per-model scores
   - explanation fields based on model agreement
6. Support analyst workflow around scored cases:
   - queue
   - detail drill-down
   - analyst decision and notes
   - rescore
   - confirmed outcome feedback
7. Be production-capable enough to support:
   - durable persistence
   - monitoring
   - fraud feedback labels
   - future retraining and drift handling

## Current Status Against End-to-End Requirements
### Implemented
- Raw transaction request intake through `POST /score`
- Internal historical-state and feature construction via the existing `end_to_end` runtime
- Multi-model scoring and weighted ensemble
- Request alias support for `timestamp` and `location`
- Aligned scoring fields:
  - `fraud_score`
  - `threshold`
  - `model_scores_overview`
  - `explanation_summary`
- Aligned `latest_output` in case detail responses
- Persisted scored cases, score runs, analyst reviews, users, audit logs, feedback records, and monitoring events
- Authenticated backend APIs for queue, detail, decision, rescore, feedback, metrics, and monitoring summaries
- Database-backed latency and scoring telemetry for score and rescore events
- Browser-based analyst workflow in the Next.js dashboard:
  - login
  - score intake
  - queue
  - case detail
  - decision, rescore, and feedback actions
  - manager metrics and monitoring pages
- Configurable CORS for direct browser calls from the local Next.js app
- Local stack assets:
  - `docker-compose.yml`
  - backend and frontend Dockerfiles
  - root env template
  - demo transaction payload
  - local stack runbook
- Contract and workflow tests for aliases, explanation summaries, feedback, and monitoring

### Partially Implemented
- Historical state is still in-memory rather than durable
- Monitoring summaries exist, but there is not yet a broader drift/retraining analytics layer

### Not Yet Implemented
- Durable historical state beyond the in-memory store
- Retraining and drift-oriented operational hooks

## Architecture Direction
### Backend boundary
- Keep `src/fraud_detection/api/` as the production backend boundary.
- Keep `end_to_end/` as the validated scoring runtime and schema source for now.
- Continue wrapping the runtime instead of rewriting model logic unless the scoring contract itself changes.

### Canonical identifier
- Keep `transaction_id` as the business identifier across backend, DB, and frontend routes.

### Persistence
- Keep `scored_cases` as the queue-facing current state.
- Keep `case_score_runs` as immutable scoring snapshots.
- Keep `analyst_reviews`, `users`, and `audit_logs` as workflow support tables.
- Keep `fraud_feedback` separate from analyst reviews.
- Keep `monitoring_events` as the first-class telemetry table for score and rescore activity.

### Historical state
- Keep the historical state store in-memory for now.
- Defer Redis/Postgres-backed historical state to a later hardening milestone.

### Frontend boundary
- Treat `web/` as a fresh Next.js app.
- Do not use generated `.next` artifacts as a base.

## Milestone Tracker
## Milestone 0: Research and Model Selection
Status: Done

Includes:
- model comparison on PaySim and S-FFSD
- final ensemble selection of LightGBM, AdaBoost, and Event-Based GNN
- calibrated weighted ensemble retained as deployment candidate

Exit criteria:
- validated ensemble and threshold policy selected
- reusable runtime artifacts available

## Milestone 1: Runnable End-to-End Scoring Runtime
Status: Done

Includes:
- `end_to_end/pipeline.py` orchestration
- raw request validation
- internal feature construction from historical state
- model scoring and weighted ensemble decision
- basic structured response
- file-based monitoring and feedback helpers

Exit criteria:
- single transaction can be scored from raw request input
- response contains score, decision, model scores, and explanation payload

## Milestone 2: Backend-First Production Slice
Status: Done

Includes:
- packaged FastAPI app under `src/fraud_detection/api/`
- auth and role separation
- persisted case and analyst workflow state
- queue, detail, decision, rescore, and metrics APIs
- migrations and backend API tests

Exit criteria:
- analysts can log in, score a case, review it, rescore it, and inspect queue/detail state through backend APIs

## Milestone 3: End-to-End Contract Alignment
Status: Done

Includes:
- request alias support:
  - `timestamp` -> `transaction_timestamp`
  - `location` -> `transaction_location`
- aligned public scoring fields:
  - `fraud_score`
  - `threshold`
  - `model_scores_overview`
  - `explanation_summary`
- rule-based explanation summaries derived from model-score agreement
- aligned scoring shape applied to both direct scoring and case-detail `latest_output`
- backend tests for alias handling and explanation-summary patterns

Exit criteria:
- the public scoring contract matches the end-to-end overview intent without breaking existing backend workflow state

## Milestone 4: Operational Hardening
Status: Done

Includes:
- dedicated feedback records and API route
- database-backed monitoring events for score and rescore activity
- latency capture for score and rescore
- monitoring summary endpoint for internal operational visibility
- historical state explicitly left in-memory

Delivered backend additions:
- dedicated feedback submission tied to `transaction_id`
- payload support for confirmed label, timestamp, and optional note
- one monitoring record per score and rescore event
- telemetry fields for:
  - `transaction_id`
  - event type
  - latency
  - decision
  - final score
  - state-availability flags
  - actor if applicable
  - created timestamp

Non-goals kept deferred:
- no Redis/Postgres-backed historical state migration yet
- no Next.js implementation in this milestone
- no retraining pipeline implementation yet

Exit criteria:
- the backend can collect confirmed outcome feedback and first-class service telemetry
- the service exposes enough metadata to support later metrics, drift analysis, and retraining workflows

## Milestone 5: Web Analyst Dashboard
Status: Done

Goal:
Build the real web frontend against the stabilized backend contract.

Scope:
- Next.js app in `web/`
- login page
- score intake page
- queue page
- case detail page
- metrics page
- protected routes
- filterable queue, decision forms, rescore actions, feedback submission, error/loading states
- session-storage bearer auth
- manager-only metrics and monitoring views
- configurable backend CORS for the local Next.js origin

Dependencies:
- backend contract is now stable enough to start frontend work

Exit criteria:
- analysts can complete their workflow through the browser instead of API-only usage

## Milestone 6: Local Deployment and Team Run
Status: Done

Goal:
Make the system easy for the team to run locally and demo consistently.

Scope:
- `docker-compose` for:
  - api
  - postgres
  - web
- environment-variable templates
- sample seed data and optional demo users
- startup instructions and troubleshooting notes

Exit criteria:
- one command path to bring up the full local stack

## Milestone 7: Durable State and Retraining Operations
Status: Next

Goal:
Move beyond the in-memory state store and add the operational hooks required for long-term production use.

Scope:
- durable historical-state backend
- drift-oriented reporting
- retraining and evaluation support
- threshold and policy management beyond static config

Exit criteria:
- historical-state lookups are durable
- the service exposes enough operational data to support lifecycle management of the fraud models

## Detailed Next Actions
### Immediate next implementation target
Milestone 7 should be next.

Concrete tasks:
- move historical state out of the in-memory store
- add drift-oriented reporting and retraining support
- add operational controls for threshold and policy management
- validate the longer-lived production lifecycle beyond demo-scale local runs

### After Milestone 7
- harden retraining and operational monitoring based on real usage

## API and Contract Notes
### Current backend contract
- input contract still follows `end_to_end/input_schema.json` plus request aliases for overview compatibility
- output contract still preserves `end_to_end/output_schema.json` fields and adds overview-aligned aliases and summaries

### Current operational contract
- feedback is modeled separately from analyst reviews
- monitoring events are stored separately from audit logs
- `transaction_id` remains canonical everywhere

## Testing Track
### Completed
- backend API smoke flow
- `tests/test_production_api.py` covering:
  - login
  - score
  - queue
  - detail
  - decision
  - rescore
  - manager metrics access
  - request alias handling
  - conflicting alias validation
  - explanation-summary pattern mapping
  - feedback submission and retrieval
  - monitoring summary creation and authorization
- direct backend verification including the CORS acceptance path
- frontend verification:
  - Next.js production build
  - Node-based utility tests for session persistence and queue query construction
- Milestone 6 repo verification:
  - compose, Dockerfiles, env templates, and runbook added
  - demo payload added for repeatable team demos

### Next
- full Docker bring-up verification on a machine with Docker installed
- broader frontend route and interaction tests once local orchestration is exercised end to end

### Acceptance scenarios completed by the backend
- analyst scores a case and a monitoring event is persisted
- analyst submits confirmed fraud or legitimate feedback for a case
- rescore creates a second monitoring event and preserves workflow state correctly
- backend can expose basic operational counts from persisted telemetry

## Done / Next / Later
### Done
- backend packaging
- auth
- persistence
- queue/detail workflow
- rescore
- metrics
- migrations
- request alias support
- aligned scoring contract fields
- explanation-summary rules
- dedicated feedback records
- database-backed monitoring events
- latency telemetry
- Next.js analyst dashboard
- browser score intake
- manager-only metrics UI
- local CORS integration for frontend development
- `docker-compose` local stack scaffolding
- environment templates and team-run docs
- demo transaction payload for local walkthroughs

### Next
- stronger historical state store
- drift and retraining operations

### Later
- production-scale lifecycle hardening beyond the current milestone plan
