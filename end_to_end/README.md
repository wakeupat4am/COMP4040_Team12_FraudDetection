# End-to-End Fraud Scoring

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

API server:

```bash
uvicorn end_to_end.api:app --reload
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
- FastAPI endpoints for `/health`, `/config`, `/score`, and `/feedback`
- monitoring and feedback persistence

Current limitations:

- the state store is in-memory rather than backed by Redis or a database
- Event-GNN inference uses a local recent-context graph rather than a fully
  maintained online global graph
- monitoring is file-based rather than integrated into a telemetry stack
