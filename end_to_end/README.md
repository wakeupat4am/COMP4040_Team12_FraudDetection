# End-to-End Fraud Scoring

This folder still contains the validated scoring runtime and schema contracts.
The production backend boundary now lives under `src/fraud_detection/api/`,
which wraps this runtime with persistence, auth, and analyst workflow APIs.

This package now contains the runnable inference path for the selected
`S-FFSD` production-candidate ensemble:

- `Event-Based GNN`
- `AdaBoost`
- `LightGBM`

The package is designed around a single raw transaction request, internal
historical-state lookup, calibrated base-model scoring, weighted score
combination, analyst-facing explanations, and a small HTTP API.

## Runtime Flow

1. Validate the raw request contract from `input_schema.json`.
2. Retrieve sender, receiver, pair, and recent global history from
   `InMemoryStateStore`.
3. Build deterministic tabular features and local graph context.
4. Score `LightGBM` and `AdaBoost` using real serialized artifacts.
5. Score the `Event-Based GNN` using a local event-context graph.
6. Apply validation-time calibrators to all three base scores.
7. Combine calibrated scores using the weighted ensemble rule in
   `pipeline_config.json`.
8. Return the structured response defined in `output_schema.json`.
9. Log monitoring metadata and optionally persist analyst feedback.

## Key Files

- `input_schema.json`: production-oriented raw transaction contract
- `output_schema.json`: structured scoring response contract
- `pipeline_config.json`: selected ensemble weights, thresholds, artifact paths
- `state_store.py`: in-memory historical state manager
- `feature_builder.py`: deterministic online feature and graph-context builder
- `model_loader.py`: runtime artifact creation/loading and calibrator loading
- `tabular_inference.py`: real LightGBM and AdaBoost inference
- `event_gnn_inference.py`: Event-GNN local-context inference wrapper
- `explanations.py`: pragmatic analyst-facing explanations
- `pipeline.py`: local orchestration entrypoint
- `api.py`: FastAPI application

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

## Current Scope

Implemented:

- production-style input schema
- internal stateful feature generation
- runtime LightGBM and AdaBoost artifact creation
- Event-GNN inference wrapper
- validation-time score calibration
- weighted ensemble scoring
- explanation generation
- production FastAPI backend for `/auth/login`, `/score`, `/cases`, `/cases/{transaction_id}`, `/cases/{transaction_id}/decision`, `/cases/{transaction_id}/rescore`, and `/metrics/summary`
- Postgres/ORM-ready persistence model for cases, score runs, analyst reviews, users, and audit logs
- monitoring and audit persistence

Current limitations:

- the state store is in-memory rather than backed by Redis or a database
- Event-GNN inference uses a local recent-context graph rather than a fully
  maintained online global graph
- monitoring is file-based rather than integrated into a telemetry stack

## Web-Facing Payload Example

The later `web/` app can treat `GET /cases/{transaction_id}` as the primary
detail payload. Example shape:

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
    "model_scores": {
      "event_gnn": 0.91,
      "adaboost": 0.72,
      "lightgbm": 0.68
    },
    "required_state_status": {
      "history_available": true,
      "graph_context_available": false
    },
    "routing_metadata": {
      "base_models": ["event_gnn", "adaboost", "lightgbm"],
      "operating_threshold": 0.6
    },
    "explanations": {
      "tabular_risk_factors": [],
      "event_context_summary": [],
      "state_availability": {
        "history_available": true,
        "graph_context_available": false,
        "warning": "Graph context is limited for this case."
      }
    }
  },
  "latest_analyst_decision": null,
  "latest_note": null,
  "review_history": [],
  "audit_trail": []
}
```
