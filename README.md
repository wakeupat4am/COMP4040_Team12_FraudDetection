# Explainable Ensemble Fraud Detection

This repository contains the full fraud-detection project lifecycle:

- offline data-mining experiments on `S-FFSD` and `PaySim`
- validated ensemble selection and report artifacts
- an online scoring runtime under `end_to_end/`
- a production-style backend under `src/fraud_detection/`
- a web dashboard under `web/`

The current production-candidate stack is built around `S-FFSD` and uses:

- `Event-Based GNN`
- `AdaBoost`
- `LightGBM`

## Current Status

Implemented:

- dataset preprocessing and feature engineering for `S-FFSD` and `PaySim`
- baseline training for Logistic Regression, LightGBM, AdaBoost, Heterogeneous GNN, and Event-Based GNN
- validation-based ensemble optimization for the final `S-FFSD` system
- generated report figures and final comparison tables
- runtime scoring pipeline with calibrated ensemble inference
- FastAPI backend with authentication, case workflow, metrics, monitoring, and Gemini advisory analysis
- web frontend for analyst-facing case review

Current limitations:

- the online scoring state is still in-memory rather than backed by Redis or a database
- the Event-Based GNN uses local recent-context graph construction instead of a persistent global graph
- Gemini analysis is advisory only and does not alter the official fraud decision

## Repository Layout

### Core project folders

- `configs/`
  - versioned YAML configuration files for paths, datasets, and model defaults
- `data/`
  - staged datasets under `data/external/` and `data/interim/`
- `end_to_end/`
  - validated fraud-scoring runtime, schemas, feature builder, calibration, explanations, and local API wrapper
- `figures/`
  - report-ready charts and diagrams
- `Final_Report/`
  - report tables and error-analysis CSV artifacts
- `models/`
  - training scripts, evaluation scripts, and saved model outputs
- `notebooks/`
  - exploratory notebooks and correlation analysis
- `src/fraud_detection/`
  - production-style backend, persistence layer, services, and API
- `tests/`
  - automated tests for runtime and backend behavior
- `web/`
  - Next.js dashboard for analyst workflows

### Key files

- `pyproject.toml`
  - Python project configuration
- `requirements.txt`
  - dependency list
- `docker-compose.yml`
  - local containerized stack
- `server.py`
  - convenience entrypoint for the backend

## Data-Mining Workflow

### Main datasets

- `S-FFSD`
  - primary dataset for final model selection and end-to-end system design
- `PaySim`
  - secondary benchmark used mainly for baseline comparison and shortcut-signal analysis

### Main experiment outputs

- `Final_Report/main_final_comparison_table.csv`
- `Final_Report/wider_baseline_comparison_table.csv`
- `Final_Report/error_analysis_cases.csv`
- `models/ssfd_validated_ensemble/`
- `models/paysim_strict_comparison/`

### Report figures

The `figures/` folder contains the current report visuals, including:

- class distribution and chronological split diagrams
- preprocessing and end-to-end pipeline diagrams
- `S-FFSD` model comparison
- `PaySim` strict comparison and shortcut-signal diagnostics
- model correlation heatmap
- precision-recall, threshold-tradeoff, and score-distribution plots
- case-level explanation example

## Runtime Flow

The runtime entrypoint is `FraudPipeline.score_transaction()` in `end_to_end/pipeline.py`.

For each transaction, the runtime:

1. validates the raw request contract
2. queries the historical state store
3. builds leakage-safe tabular and graph-context features
4. scores LightGBM, AdaBoost, and Event-Based GNN
5. calibrates the base-model probabilities
6. combines them with the weighted ensemble rule
7. assigns the final risk score, bucket, and decision
8. produces explanation fields

## Backend Capabilities

The production-style backend under `src/fraud_detection/` provides:

- authentication
- transaction scoring
- case queue and case detail retrieval
- analyst decisions
- rescoring
- feedback submission
- metrics summary
- monitoring summary
- Gemini advisory analysis per case

Current case workflow routes include:

- `POST /auth/login`
- `POST /score`
- `GET /cases`
- `GET /cases/{transaction_id}`
- `POST /cases/{transaction_id}/decision`
- `POST /cases/{transaction_id}/rescore`
- `POST /cases/{transaction_id}/feedback`
- `POST /cases/{transaction_id}/gemini-analysis`
- `GET /metrics/summary`
- `GET /monitoring/summary`

## Example Inputs

Two example payloads are kept with the runtime assets:

- `end_to_end/example_input.json`
  - minimal scoring example aligned with the current request schema
- `end_to_end/demo_transaction.json`
  - slightly richer demo payload for UI or API walkthroughs

## Run Locally

### Backend only

```bash
python3 server.py
```

or

```bash
uvicorn fraud_detection.api:app --reload
```

### Local runtime demo

```bash
python3 -m end_to_end.pipeline
```

### Web frontend

```bash
cd web
npm install
npm run dev
```

### Containerized stack

```bash
docker compose up --build
```

If you want to use a different database, set `DATABASE_URL` in `.env`.

## Gemini Advisory

Gemini support is implemented as an optional analyst-advisory layer.

- configuration lives in `src/fraud_detection/config.py`
- the advisory service lives in `src/fraud_detection/services/gemini.py`
- the manual smoke script lives in `scripts/gemini_smoke_test.py`

The Gemini layer reads saved case snapshots and returns structured recommendations. It is advisory only and does not replace the official ensemble decision.

## Tests

Primary tests currently include:

- `tests/test_end_to_end_state.py`
- `tests/test_production_api.py`
- `tests/test_project_structure.py`

Run them with:

```bash
pytest -q
```

## Notes

- `Final_Report/` and `figures/` are intentionally kept separate:
  - `Final_Report/` stores tabular report artifacts
  - `figures/` stores rendered visual assets
- `models/` contains both training scripts and generated experiment folders
- the root workspace is intentionally kept thin; top-level files are limited to entrypoints, configs, and project metadata
