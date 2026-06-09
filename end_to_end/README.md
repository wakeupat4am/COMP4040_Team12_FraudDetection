# End-to-End Fraud Scoring

This folder contains the validated scoring runtime and the schema contracts
that connect model development to the deployed fraud-operations system.

The current production-candidate ensemble is the S-FFSD pipeline:

- Event-Based GNN
- AdaBoost
- LightGBM

The production backend in `src/fraud_detection/api/` wraps this runtime with
authentication, persistence, analyst workflow APIs, monitoring summaries, audit
logging, and a Gemini advisory panel.

## Techniques Used Across the System

The current system combines several techniques, each with a specific role in
the end-to-end workflow:

- tabular supervised learning with LightGBM and AdaBoost
- graph-based fraud scoring with an Event-Based GNN
- leakage-safe online feature engineering from internal transaction history
- validation-time isotonic calibration for probability correction
- weighted ensemble decisioning across calibrated model scores
- analyst-facing explanation generation from engineered features and graph context
- workflow persistence with versioned score runs, audit logs, and monitoring events
- Gemini-based advisory analysis using prompt constraints, structured output, and backend validation

The boundary is explicit:

- the fraud score, risk bucket, and system decision come from the calibrated ensemble
- Gemini is a manual advisory layer built on top of the saved case snapshot

## From Model Development To Runtime

The project follows one path from offline experimentation to the deployed
workflow:

1. Prepare processed SSFD splits in `data/processed/`.
2. Train and compare candidate models in `models/train_ssfd_*.py`.
3. Build time-ordered history features and event-graph context without using future information.
4. Fit validation-time calibrators for each selected base model.
5. Select the production-candidate ensemble and store its weights and thresholds in `pipeline_config.json`.
6. Package the runtime artifacts under `end_to_end/artifacts/` and `models/ssfd_validated_ensemble/`.
7. Serve the scoring output through the FastAPI backend.
8. Persist scored cases, score runs, analyst review actions, feedback, monitoring events, and audit entries.
9. Optionally generate Gemini advisory analysis from the saved case snapshot.

## Model Development Techniques

The training code lives under `models/` and is shared across the SSFD
experiments.

### Time-ordered data handling

The SSFD training utilities are designed around chronological ordering rather
than random shuffling. The processed split files:

- `ssfd_lightgbm_train.csv`
- `ssfd_lightgbm_test.csv`
- `ssfd_lightgbm_unlabeled.csv`

are used to build history-based features in time order so the runtime can later
reproduce the same feature family online without future leakage.

### Tabular learning with LightGBM and AdaBoost

The tabular branch uses two different supervised learners:

- `LightGBM` handles mixed numeric and categorical transaction features and
  uses `scale_pos_weight` to compensate for class imbalance.
- `AdaBoost` uses engineered sequential features plus frequency/count
  statistics and applies sample weighting so positive fraud cases receive more
  emphasis during training.

These models intentionally have different biases. LightGBM provides a stable
tree-based baseline with native categorical support, while AdaBoost is more
aggressive on hard cases and adds diversity to the ensemble.

### Leakage-safe sequential feature engineering

The training utilities and the online runtime both build the same core feature
family from prior state:

- sender, receiver, location, and transaction-type counts so far
- sender-receiver pair counts so far
- sender, receiver, and pair time gaps
- sender, receiver, and pair historical mean amounts
- amount deviation from historical means
- seen-before indicators for sender-target, sender-location, and sender-type
- sender, receiver, location, and type frequency/count statistics

The online caller does not supply these engineered values. It supplies only raw
transaction facts, and the system computes the features internally to reduce
feature skew and future-leakage errors.

### Graph-based fraud detection with Event-Based GNN

The graph branch uses an Event-Based GNN over a local event context. Both the
training code and the runtime construct an event graph that includes:

- a recent global event window
- recent events for the same sender
- recent events for the same receiver
- the candidate transaction inserted as the `test` event

This local event graph gives the GNN sequence-aware and relationship-aware
signals without requiring a fully materialized online global graph.

### Validation metrics and threshold selection

The training code computes standard supervised metrics such as:

- accuracy
- precision
- recall
- F1
- ROC-AUC
- average precision

For graph training, the code also searches validation thresholds and keeps the
best threshold based on validation performance. The model utilities export
predictions, metrics, and relationship summaries so the selected ensemble can
be justified from saved outputs rather than ad hoc inspection.

## Runtime Techniques

The runtime entry point is `FraudPipeline.score_transaction()` in
`pipeline.py`.

### Validation and schema control

The runtime validates the incoming transaction against `input_schema.json` and
checks that the generated output satisfies `output_schema.json`. This keeps the
runtime contract explicit and stable for the backend and frontend.

### Internal state and online feature construction

The runtime queries the in-memory state store for:

- sender history
- receiver history
- sender-receiver pair history
- recent global event context

It then builds deterministic tabular features and a local event-context frame
through `feature_builder.py`. This is the online counterpart of the
history-aware feature generation used during training.

### Validation-time isotonic calibration

Before combining model outputs, each selected base model score is calibrated:

- LightGBM calibration is fit from validation predictions
- AdaBoost calibration is fit from validation predictions
- Event-GNN calibration is fit from saved validation predictions from the
  validated ensemble run

The runtime loads these calibrators through `model_loader.py` and applies them
inside `tabular_inference.py` and `event_gnn_inference.py`. This keeps the
ensemble decision closer to calibrated probabilities rather than raw model
scores.

### Weighted ensemble decisioning

The selected ensemble is defined in `pipeline_config.json`:

- operating threshold: `0.6`
- weights:
  - `event_gnn`: `0.50`
  - `adaboost`: `0.30`
  - `lightgbm`: `0.20`

The runtime uses weighted averaging across the calibrated scores, then derives:

- final risk score
- risk bucket
- decision

The current thresholds are:

- risk bucket:
  - low: `0.2`
  - medium: `0.5`
  - high: `0.75`
- decision:
  - review: `0.6`
  - block: `0.8`

### Analyst-facing explanation generation

The runtime generates explanation payloads from internal scoring artifacts
rather than from a separate explanation model.

The current explanation helpers provide:

- top tabular risk-factor summaries from engineered feature values
- event-context summaries such as context size and sender/receiver history size

These explanations are pragmatic and analyst-facing: they are meant to support
triage in the case detail page, not to act as formal post-hoc model proofs.

## Backend Workflow Techniques

The production backend turns the scoring runtime into an analyst workflow
platform.

### Case persistence and latest-state projection

Each scored transaction becomes a stored case containing:

- the original request payload
- the latest output payload
- explanation payload
- routing metadata
- latest score-run reference
- review status and latest analyst decision fields

The case detail API returns a latest-state projection of this data for the case
page, while related histories remain queryable through the same response.

### Versioned score runs

The backend persists score runs separately from the latest case state:

- the initial `/score` request creates a scored case and an initial score run
- `/cases/{transaction_id}/rescore` appends a new score run and refreshes the
  latest case state

This pattern preserves run history while keeping the case detail page centered
on the current score.

### Analyst review and feedback separation

The workflow separates:

- analyst review decisions
- confirmed feedback labels

Analyst review records what the team decided operationally. Feedback records the
observed or confirmed final label later. Keeping these separate prevents the
workflow from conflating operational judgment with ground-truth outcome.

### Audit logging and monitoring events

The backend records audit entries for:

- score creation
- rescore
- analyst decision submission
- feedback submission
- Gemini analysis success
- Gemini analysis failure

It also records monitoring events with:

- event type
- latency
- final risk score
- decision
- state-availability flags

This gives the system both an operational trace and lightweight runtime
observability.

## Gemini Advisory Techniques

Gemini is implemented as a separate advisory subsystem in
`src/fraud_detection/services/gemini.py`. It does not participate in the fraud
score itself and does not replace the official analyst workflow.

### Prompt engineering

The Gemini prompt is deliberately constrained:

- Gemini is framed as a fraud-operations advisory assistant
- it is instructed to return exactly one JSON object
- the allowed enum values are fixed:
  - `recommended_decision`: `allow | review | block`
  - `confidence`: `low | medium | high`
- the response is length-bounded:
  - summary under 35 words
  - at most 3 `key_factors`
  - at most 3 `risk_flags`
  - at most 3 `follow_up_actions`
  - short list items
- it is explicitly told not to return markdown fences or explanatory prose

This is prompt engineering for operational control rather than open-ended
reasoning. The goal is a short, structured recommendation that fits cleanly
into the case detail UI.

### Context shaping and input control

Gemini does not receive the full workflow history. The backend builds a curated
case snapshot from the current case only:

- transaction summary
- score summary
- explanation summary
- routing metadata
- case-level decision and score-run metadata

Before prompt assembly, nested structures are truncated and long strings are
shortened. This limits prompt size, removes noisy payload expansion, and keeps
Gemini focused on the current score snapshot rather than unrelated workflow
history.

### API management and runtime configuration

The integration uses the official `google-genai` SDK. Runtime configuration is
managed through environment variables:

- `GEMINI_API_KEY`
- `GEMINI_MODEL`
- `GEMINI_TIMEOUT_SECONDS`

The request timeout is passed through the SDK client HTTP options. The selected
model name is persisted with the saved advisory payload so the system records
which Gemini variant generated the recommendation.

### Structured output enforcement

The Gemini request uses:

- `response_mime_type="application/json"`
- `response_json_schema=GeminiAdvisoryResult.model_json_schema()`

The backend then validates the response against the `GeminiAdvisoryResult`
Pydantic model. This means Gemini output is treated as typed application data,
not as trusted free text.

### Resilience and failure handling

The integration uses several defensive techniques:

- if the first Gemini response fails structural validation, the backend sends a
  repair prompt
- the repair prompt includes the previous bad response and restates the format
  constraints
- the parser can recover JSON from code fences or surrounding prose by
  extracting the JSON object when possible
- empty, malformed, or otherwise unusable responses become backend errors
  instead of silently accepted advisory data

This keeps the advisory layer operationally safer, especially when model output
format drifts.

### Workflow and persistence behavior

Gemini is manual and advisory:

- it is triggered through `/cases/{transaction_id}/gemini-analysis`
- it does not modify the fraud score, system decision, review status, or
  analyst-review history
- only the latest Gemini advisory payload is stored on the case
- both success and failure create audit entries
- rescoring clears the saved Gemini payload so stale advice does not survive to
  a new score run

The result is a bounded AI assistant on top of the operational case workflow,
not a second scoring pipeline.

## Key Files

- `pipeline.py`: orchestration entry point for scoring
- `feature_builder.py`: online feature construction from current state
- `model_loader.py`: artifact loading, runtime bootstrap, and calibrator loading
- `tabular_inference.py`: LightGBM and AdaBoost inference
- `event_gnn_inference.py`: Event-Based GNN inference wrapper
- `explanations.py`: analyst-facing explanation helpers
- `state_store.py`: in-memory historical state manager
- `monitoring.py`: runtime monitoring sink
- `feedback_store.py`: lightweight feedback persistence
- `pipeline_config.json`: ensemble weights, thresholds, and artifact paths
- `input_schema.json`: raw transaction request contract
- `output_schema.json`: structured scoring response contract
- `api.py`: local FastAPI wrapper for the runtime

## Run Locally

Local demo:

```bash
python3 -m end_to_end.pipeline
```

Production API server:

```bash
uvicorn fraud_detection.api:app --reload
```

Convenience entrypoint:

```bash
python3 server.py
```

The backend also supports a simple local development setup:

- backend: `python server.py`
- frontend: `npm install` and `npm run dev` inside `web/`

## Current Scope

Implemented:

- production-style input schema and output schema validation
- leakage-safe online feature generation
- runtime LightGBM and AdaBoost artifact loading
- Event-Based GNN inference wrapper
- validation-time isotonic calibration
- weighted ensemble scoring
- analyst-facing explanation generation
- production FastAPI backend for `/auth/login`, `/score`, `/cases`,
  `/cases/{transaction_id}`, `/cases/{transaction_id}/decision`,
  `/cases/{transaction_id}/rescore`, `/cases/{transaction_id}/feedback`, and
  `/cases/{transaction_id}/gemini-analysis`
- persistence for cases, score runs, analyst reviews, feedback, users, audit
  logs, monitoring events, and Gemini advisory payloads

Current limitations:

- the online state store is still in-memory rather than backed by Redis or a
  database
- Event-Based GNN scoring uses a local recent-context graph rather than a
  fully maintained online global graph
- monitoring is file-based rather than integrated into a telemetry stack
- Gemini analysis is generated manually per case and is advisory only

## Web-Facing Payload Example

The web app consumes `GET /cases/{transaction_id}` as the main case-detail
payload. The shape below is representative:

```json
{
  "transaction_id": "tx_000001",
  "final_risk_score": 0.83,
  "risk_bucket": "critical",
  "decision": "block",
  "review_status": "pending",
  "latest_output": {
    "transaction_id": "tx_000001",
    "pipeline_profile": "ssfd_production_candidate",
    "final_risk_score": 0.83,
    "risk_bucket": "critical",
    "decision": "block",
    "model_scores_overview": {
      "Event_GNN": 0.91,
      "AdaBoost": 0.72,
      "LightGBM": 0.68
    },
    "required_state_status": {
      "history_available": true,
      "graph_context_available": false
    },
    "routing_metadata": {
      "base_models": ["event_gnn", "adaboost", "lightgbm"],
      "operating_threshold": 0.6
    },
    "explanation_summary": {
      "main_risk_source": "graph",
      "tabular_signal": "high",
      "graph_signal": "low",
      "reason": "Graph context is limited for this case."
    }
  },
  "latest_analyst_decision": null,
  "latest_note": null,
  "latest_gemini_analysis": null,
  "review_history": [],
  "feedback_history": [],
  "audit_trail": []
}
```
