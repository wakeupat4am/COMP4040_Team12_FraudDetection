# Project Architecture

## Goal

Organize the repository so the team can move from early experimentation to a
repeatable ML pipeline without restructuring the project later.

## Suggested Flow

1. Put original source extracts and benchmark datasets in `data/raw/`.
2. Build leakage-safe cleaned joins in `data/interim/`.
3. Save training-ready feature sets in `data/processed/`.
4. Implement reusable pipeline logic in `src/fraud_detection/`.
5. Keep ad hoc exploration in `notebooks/`, then promote stable logic into `src/`.
6. Save trained models in `models/` and figures in `reports/figures/`.

## Source Package Map

- `pipelines/ingestion.py`: loading and entity-resolution workflows
- `pipelines/features.py`: feature generation and time-window logic
- `pipelines/anomaly.py`: anomaly-scoring module
- `pipelines/graph.py`: graph feature and graph-risk logic
- `pipelines/text.py`: NLP feature and evidence extraction
- `pipelines/supervised.py`: tabular supervised models
- `pipelines/ensemble.py`: module score fusion
- `pipelines/explainability.py`: SHAP, graph, and text explanations
- `utils/io.py`: shared path and file helpers
