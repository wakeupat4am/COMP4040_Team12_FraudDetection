# End-to-End Fraud Scoring

This folder contains the validated scoring runtime and the contracts that sit
between model development and the production backend.

The current production-candidate ensemble is the S-FFSD pipeline:

- Event-Based GNN
- AdaBoost
- LightGBM

The runtime is responsible for:

- validating a raw transaction request
- building leakage-safe online features from internal state
- scoring the three base models
- applying validation-time calibration
- combining the calibrated scores with a weighted ensemble rule
- producing an analyst-facing explanation payload
- logging monitoring metadata

The production backend in `src/fraud_detection/api/` wraps this runtime with
authentication, persistence, review workflow APIs, and the Gemini advisory
panel.

## From Model Development To Runtime

The project follows one path from offline experimentation to the deployed
workflow:

1. Prepare processed SSFD splits in `data/processed/`.
2. Train and compare candidate models in `models/train_ssfd_*.py`.
3. Build leakage-safe tabular and event-graph features from training history.
4. Calibrate validation predictions for each base model.
5. Select the production-candidate ensemble and store its weights in
   `pipeline_config.json`.
6. Package the runtime artifacts under `end_to_end/artifacts/` and
   `models/ssfd_validated_ensemble/`.
7. Serve the scoring output through the FastAPI backend.
8. Persist scored cases, analyst decisions, feedback, and audit events.
9. Optionally generate Gemini advisory analysis from the saved case snapshot.

## Model Development

The training code lives under `models/` and is shared across the SSFD
experiments.

### Data flow

The model development scripts read the processed SSFD splits:

- `ssfd_lightgbm_train.csv`
- `ssfd_lightgbm_test.csv`
- `ssfd_lightgbm_unlabeled.csv`

These splits are used to build time-ordered history features and graph context
without leaking future information into the online scoring path.

### Base models

The current production-candidate ensemble keeps three complementary models:

- `LightGBM`: stable tabular baseline with categorical handling
- `AdaBoost`: high-recall tabular baseline with engineered history features
- `Event-Based GNN`: sequence-aware graph model over local event context

The heterogeneous GNN and logistic-regression variants remain available in the
training folder, but they are not part of the current production-candidate
ensemble.

### Feature engineering

The shared training utilities build the same family of features that the online
runtime later reproduces:

- source, target, and pair transaction counts
- source, target, and pair time gaps
- source, target, and pair historical mean amounts
- amount deviations from historical means
- seen-before flags for sender/location/type combinations
- sender, receiver, location, and type frequency statistics

For the Event-Based GNN, the training code also assembles a local event graph
containing the recent global window, sender history, receiver history, and the
candidate transaction as the test node.

### Validation and selection

The model code computes validation metrics, selects thresholds, and writes out
artifacts such as:

- trained model files
- calibration models
- feature importance and coefficient exports
- prediction CSVs
- relationship summaries for graph models

The selected ensemble is defined in `pipeline_config.json`:

- operating threshold: `0.6`
- weights:
  - `event_gnn`: `0.50`
  - `adaboost`: `0.30`
  - `lightgbm`: `0.20`

The current risk-bucket thresholds are:

- low: `0.2`
- medium: `0.5`
- high: `0.75`

The current decision thresholds are:

- review: `0.6`
- block: `0.8`

## Runtime Flow

The runtime entry point is `FraudPipeline.score_transaction()` in
`pipeline.py`.

1. Validate the raw request contract from `input_schema.json`.
2. Query the in-memory state store for sender, receiver, pair, and recent
   history.
3. Build deterministic tabular features and a local event-context graph.
4. Score LightGBM and AdaBoost with loaded serialized artifacts.
5. Score the Event-Based GNN with the local event graph.
6. Apply validation-time calibrators to each base-model score.
7. Combine the calibrated scores with the weighted ensemble rule.
8. Derive the final risk bucket and decision.
9. Generate explanation payloads for the case detail UI.
10. Log monitoring metadata, and optionally persist the new event into the
    online state store.

The runtime output is validated against `output_schema.json` before it is
returned.

## Key Files

- `pipeline.py`: orchestration entry point for scoring
- `feature_builder.py`: online feature construction from current state
- `model_loader.py`: artifact loading and runtime bootstrap
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

## Backend And Case Workflow

The production backend now treats `GET /cases/{transaction_id}` as the primary
case-detail payload. It stores:

- the original request
- the latest scoring output
- the explanation payload
- routing metadata
- analyst review history
- confirmed feedback history
- audit logs
- latest Gemini advisory analysis, if available

Gemini analysis is advisory only. It reads the saved case snapshot, returns a
structured recommendation, and does not alter the official analyst decision
workflow.

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

- production-style input schema
- leakage-safe online feature generation
- runtime LightGBM and AdaBoost artifact loading
- Event-Based GNN inference wrapper
- validation-time calibration
- weighted ensemble scoring
- explanation generation
- production FastAPI backend for `/auth/login`, `/score`, `/cases`,
  `/cases/{transaction_id}`, `/cases/{transaction_id}/decision`,
  `/cases/{transaction_id}/rescore`, `/cases/{transaction_id}/feedback`, and
  `/cases/{transaction_id}/gemini-analysis`
- persistence for cases, score runs, analyst reviews, feedback, users, audit
  logs, and Gemini advisory payloads
- monitoring metadata collection

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
