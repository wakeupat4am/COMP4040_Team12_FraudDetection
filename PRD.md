# Product Requirements Document

## Fraud Ops Console: Explainable Ensemble Fraud Detection

## 1. Product Summary

Fraud Ops Console is an end-to-end fraud detection product for online transaction systems. It accepts a raw transaction, builds historical and event-context features internally, scores the transaction with a selected ensemble of fraud models, and returns a structured fraud decision that analysts can review through a browser dashboard.

The product is designed for fraud operations teams that need more than a model score. It provides:

- a fraud risk score
- an allow/review/block decision
- per-model scores
- explanation summaries
- case queue and detail views
- analyst review actions
- confirmed outcome feedback
- operational metrics and monitoring summaries

The current implementation is a local production-style demo stack with FastAPI, Postgres, and Next.js.

## 2. Problem Statement

Online transaction systems need to identify suspicious transactions quickly while avoiding unnecessary false positives. Blocking too many legitimate transactions hurts customer trust and revenue, while missing fraud causes direct financial loss and operational cost.

Fraud patterns are difficult because:

- confirmed fraud labels can arrive late
- fraud is usually rare and imbalanced
- attackers adapt over time
- risk can depend on historical behavior, not only the current transaction
- relational behavior between senders, receivers, devices, locations, and event history can matter
- analysts need explanations, not only scores

This product turns model research into an operational workflow where transactions can be scored, reviewed, rescored, and labeled for future improvement.

## 3. Target Users

### Fraud Analyst

Primary user who reviews scored transactions.

Needs:

- submit or inspect a transaction
- see fraud score and decision
- understand why the case is risky
- review the case and leave a decision/note
- rescore a case if needed
- submit confirmed fraud or legitimate outcome feedback

### Fraud Manager / Admin

Supervisory user who monitors queue health and model-operation summaries.

Needs:

- see case distribution
- see pending review counts
- inspect score/rescore telemetry
- monitor average scoring latency
- eventually manage thresholds and model lifecycle

### Transaction System / API Caller

External system that sends raw transaction facts for scoring.

Needs:

- submit immutable transaction fields
- avoid manually computing historical or graph features
- receive a deterministic structured scoring response

## 4. Goals

The product should:

- score raw transactions using the selected fraud ensemble
- compute historical and event-context features internally
- expose a stable scoring API contract
- persist scored cases and analyst workflow state
- support a complete browser-based analyst workflow
- collect confirmed outcome feedback for future evaluation and retraining
- capture basic operational telemetry for score and rescore events
- run locally in a repeatable way for team demos

## 5. Non-Goals For Current Version

The current version does not yet aim to provide:

- durable historical state beyond the active service process
- full production model retraining pipeline
- automated drift detection and alerting
- online global graph storage
- threshold-management UI
- enterprise-grade user management
- cloud deployment pipeline
- external observability integration

These are future milestones, not current release blockers for the local demo.

## 6. Product Workflow

## 6.1 Transaction Scoring

An analyst or external caller submits a raw transaction payload.

Example fields:

- `transaction_id`
- `transaction_timestamp`
- `sender_id`
- `receiver_id`
- `amount`
- `transaction_location`
- `transaction_type`
- optional `currency`
- optional `channel`
- optional `raw_attributes`

The caller should not send engineered historical features. The product builds those internally to reduce feature skew and future-information leakage.

Expected result:

- transaction is validated
- historical state is queried
- tabular features are built
- event context is built
- LightGBM, AdaBoost, and Event-GNN are scored
- calibrated model scores are combined
- final fraud score and decision are returned
- case is stored in the workflow database

## 6.2 Analyst Queue

Analysts can view stored cases in a queue.

Queue supports filtering by:

- risk bucket
- routing decision
- review status
- creation time window
- page size/page number

Queue rows show:

- transaction ID
- final risk score
- risk bucket
- decision
- review status
- last scored time
- latest analyst note

## 6.3 Case Detail

Analysts can open a case detail page to inspect:

- latest fraud score
- operating threshold
- allow/review/block decision
- per-model score breakdown
- explanation summary
- original request payload
- explanation payload
- routing metadata
- review history
- feedback history
- audit trail

## 6.4 Analyst Decision

Analysts can submit a decision and note for a case.

Supported analyst decisions:

- allow
- review
- block

Submitting a decision updates the case review status and appends review history.

## 6.5 Rescore

Analysts can rescore an existing case using the current pipeline.

Expected behavior:

- original request payload is reused
- a new score run is stored
- current case output is updated
- review status resets to pending
- monitoring event is recorded
- audit log is appended

## 6.6 Confirmed Feedback

Analysts can submit confirmed outcome feedback after real-world investigation.

Supported confirmed labels:

- fraud
- legitimate

Feedback is stored separately from analyst review history because analyst decisions are operational actions, while feedback is ground-truth-oriented labeling for future evaluation.

## 6.7 Manager Metrics

Manager admins can view:

- total cases
- average fraud score
- pending review count
- risk bucket counts
- decision counts
- review status counts
- score/rescore monitoring event counts
- average score/rescore latency
- latest monitoring event timestamp

## 7. Core Features

## 7.1 Ensemble Fraud Scoring

The current selected ensemble combines:

- LightGBM
- AdaBoost
- Event-Based GNN

The product computes:

```text
final_score = 0.20 * LightGBM + 0.30 * AdaBoost + 0.50 * Event_GNN
```

The final score is compared with configured thresholds to produce a routing decision.

## 7.2 Explanation Summary

The product produces analyst-facing explanation summaries based on model agreement.

Main risk source can be:

- agreement between tabular and graph models
- tabular models drive risk
- graph model drives risk
- mixed model signals

The output also describes:

- tabular signal level
- graph signal level
- human-readable reason
- state availability warning if historical or graph context is limited

## 7.3 Persistent Case Workflow

The backend stores:

- users
- scored cases
- immutable score runs
- analyst reviews
- confirmed feedback
- audit logs
- monitoring events

This makes the system usable as a workflow product rather than only a scoring script.

## 7.4 Browser Dashboard

The web dashboard supports:

- login
- score intake
- case queue
- case detail
- analyst decision
- rescore
- confirmed feedback
- manager metrics
- monitoring summary

## 7.5 Local Stack

The product can run locally with:

- Postgres
- FastAPI backend
- Next.js frontend

Primary local run path:

```bash
docker compose up --build
```

## 8. API Requirements

## 8.1 Authentication

The backend requires bearer-token authentication for workflow APIs.

Roles:

- `analyst`
- `manager_admin`

Manager-only endpoints:

- `/metrics/summary`
- `/monitoring/summary`

## 8.2 Scoring Endpoint

Endpoint:

```text
POST /score
```

Requirements:

- must accept canonical transaction fields
- must accept aliases `timestamp` and `location`
- must reject conflicting canonical and alias values
- must return stored case detail with aligned `latest_output`

## 8.3 Case Workflow Endpoints

Required endpoints:

- `GET /cases`
- `GET /cases/{transaction_id}`
- `POST /cases/{transaction_id}/decision`
- `POST /cases/{transaction_id}/rescore`
- `POST /cases/{transaction_id}/feedback`

## 8.4 Metrics and Monitoring Endpoints

Required endpoints:

- `GET /metrics/summary`
- `GET /monitoring/summary`

These require manager admin access.

## 9. Data Requirements

## 9.1 Raw Transaction Data

Minimum fields:

- transaction identifier
- timestamp
- sender
- receiver
- amount
- location
- transaction type

Optional fields:

- currency
- channel
- raw attributes such as device, IP, or metadata

## 9.2 Internal Historical State

The system needs historical context for:

- sender activity
- receiver activity
- sender-receiver pair history
- amount patterns
- location/type frequency
- recent global events

Current limitation:

- this state exists in memory and is not durable.

Future requirement:

- persist historical state in Postgres, Redis, or another durable store.

## 9.3 Feedback Data

Feedback records should preserve:

- transaction ID
- confirmed label
- feedback timestamp
- reviewer
- optional note

Future use:

- model evaluation
- retraining datasets
- threshold analysis

## 10. Success Metrics

## 10.1 Product Success

- Analyst can score a transaction from the browser.
- Analyst can find the case in the queue.
- Analyst can review, rescore, and submit feedback.
- Manager can inspect metrics and monitoring summaries.
- Team can run the full stack locally with one Docker Compose command.

## 10.2 Model Success

Tracked from research and future production monitoring:

- precision
- recall
- F1
- ROC-AUC
- average precision
- calibration quality
- false-positive rate
- recall at analyst review capacity

## 10.3 Operational Success

- scoring API returns structured responses consistently
- score and rescore latency is captured
- workflow state is persisted
- audit trail exists for major case actions
- confirmed feedback can be exported for future evaluation

## 11. Current Implementation Status

Implemented:

- model research and selected ensemble
- end-to-end scoring runtime
- FastAPI backend
- auth and role checks
- persisted case workflow
- score runs, reviews, feedback, audit logs, and monitoring events
- scoring contract alignment
- Next.js analyst dashboard
- Docker Compose local stack
- backend and frontend tests for current workflow

Partially implemented:

- historical state abstraction
- Event-GNN local context construction
- monitoring summaries

Not yet implemented:

- durable historical state
- durable online graph context
- drift analytics
- retraining operations
- model/version registry
- threshold management
- production CI/CD and deployment workflow
- external observability integration

## 12. Recommended Next Product Milestone

## Milestone 7: Durable State and Model Lifecycle

Objective:

Make the product reliable beyond a local demo by replacing in-memory scoring context and adding lifecycle hooks for future model operations.

Scope:

- implement durable historical-state storage
- add restart-persistence tests
- keep leakage-safe feature construction
- add time-windowed monitoring summaries
- export feedback labels for evaluation/retraining
- record model, calibrator, threshold, and pipeline versions per score run
- update stale runtime documentation around monitoring limitations

Exit criteria:

- historical context survives backend restarts
- score-time features still use only prior history
- feedback can be used as labeled evaluation data
- monitoring can be filtered by time range
- score runs are traceable to model and policy versions
