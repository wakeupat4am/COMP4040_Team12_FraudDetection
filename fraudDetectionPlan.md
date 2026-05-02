# Multi-Modal Risk Detection System - Overview and Production Plan

## 1. Project Overview

The project is a **Multi-Modal Risk Detection System** designed for online stores. It aims to tackle three major business challenges:

- **Fraud/Abuse Detection**: Identifying suspicious transactions or orders.
- **Return Abuse**: Flagging cases where customers abuse the refund/return policy.
- **Customer Churn Risk**: Predicting the likelihood of a customer leaving.

**Key features include:**

- **Multi-Modal Inputs**: Combining tabular data (transactions), graph data (networks of users, devices, IPs), and text data (support tickets, reviews).
- **Explainability**: Generating human-readable explanations (e.g., SHAP values, subgraph evidence) for why a transaction was flagged, enabling customer support and operations teams to make informed decisions.

---

## 2. Current Progress Analysis

Based on the repository review, the project has established a strong foundation:

- **Project Structure**: Well-organized following data-science best practices (`configs/`, `data/`, `models/`, `src/`, etc.).
- **Model Training**: Significant progress has been made on the modeling front. There are dedicated training scripts for different modalities:
  - Tabular baselines: LightGBM (`train_ssfd_lightgbm.py`) and AdaBoost (`train_ssfd_adaboost.py`).
  - Graph Neural Networks: Event GNN (`train_ssfd_event_gnn.py`) and Heterogeneous GNN (`train_ssfd_hetero_gnn.py`).
- **Exploratory Data Analysis (EDA)**: Present in `notebooks/ssfd_eda_preprocessing.ipynb`.
- **Pipeline Modules**: The `src/fraud_detection/pipelines` directory has module files (`anomaly.py`, `explainability.py`, `ensemble.py`, etc.), but they currently contain placeholder logic.

**What is missing for Production Readiness?**

- **Integration Layer**: A defined contract for how the merchant's platform connects to the risk service and which data channels are established.
- **Inference Pipeline**: Code to load the trained models, process real-time incoming single-event data, and generate predictions and explanations.
- **Backend API**: A serving layer to expose the models to front-end clients.
- **Dashboard/UI**: An interactive interface for analysts to review flagged cases, risk scores, and explanations.
- **Monitoring**: Ongoing observability of model health, system performance, and a feedback loop for retraining.

---

## 3. Production Readiness Plan

To make this system truly production-ready, we will build a four-phase architecture covering integration, inference, serving, and monitoring. All three signal categories — transactional, relational, and textual — are collected passively from existing platform infrastructure, requiring no manual data entry from merchant operations staff at any point in the scoring flow.

---

### Phase 0: Integration Layer

The system connects to the merchant's existing infrastructure through a lightweight, one-time setup. Three signal channels are established passively:

- **Order events** — Transactional data (amounts, timestamps, merchant attributes) dispatched to the risk service via webhook or synchronous API call at the moment each transaction is created.
- **Session & device logs** — Relational signals derived from infrastructure logs already produced by the platform, from which the system continuously constructs a graph of users, devices, and IP addresses.
- **Customer text feed** — Unstructured text from support tickets and product reviews ingested via a feed subscription.

Because all three channels draw from data the merchant already generates, integration overhead is confined to a one-time API setup. After this, the pipeline operates autonomously.

**Deliverables:**
- `src/api/integration/webhook_receiver.py` — Endpoint to accept inbound transaction event payloads.
- `src/api/integration/schemas.py` — Pydantic models defining the event payload contract.
- Documentation: integration guide for merchant engineering teams.

---

### Phase 1: Data Ingestion & Inference

Upon receiving an event, the system assembles the multi-modal signal representation and scores it.

- **Feature Engineering Pipeline**: A unified pipeline normalizes and encodes each channel — producing structured feature vectors from tabular fields, graph embeddings from the relational network, and NLP representations from associated text.
- **Multi-Modal Model Ensemble**: The three representations are routed independently to gradient-boosted trees (LightGBM), graph neural networks (Event GNN / Hetero GNN), and a text classifier. Outputs are fused at the ensemble layer into a single risk representation per event.

**Deliverables:**
- **[MODIFY]** `src/fraud_detection/pipelines/supervised.py` — Load trained models and handle real-time tabular inference.
- **[MODIFY]** `src/fraud_detection/pipelines/ensemble.py` — Implement fusion logic across all three model outputs.
- **[MODIFY]** `src/fraud_detection/pipelines/anomaly.py` — Integrate graph and text scoring into the unified pipeline.

---

### Phase 2: Serving & Explainability

A stateless inference API receives the event payload assembled in Phase 1 and returns a structured risk decision.

- **Inference API**: Exposes endpoints (e.g., `/predict/fraud`, `/predict/churn`) that return risk scores across three dimensions — fraud probability, return-abuse likelihood, and churn risk.
- **Explainability**: Alongside each score, the API returns attribution evidence — SHAP values for tabular outputs and subgraph highlights for graph outputs.
- **Analyst Dashboard**: Risk gauges, a ranked feature-importance view, and a flagged-case queue are surfaced through a web dashboard. The analyst's role is limited to reviewing flagged cases and submitting label corrections where necessary; no manual data entry is required.

**Deliverables:**
- **[NEW]** `src/api/main.py` — FastAPI application with `/predict/fraud` and `/predict/churn` endpoints.
- **[MODIFY]** `src/fraud_detection/pipelines/explainability.py` — Implement SHAP value calculation and subgraph evidence extraction.
- **[NEW]** `frontend/index.html` — Dashboard entry point.
- **[NEW]** `frontend/app.js` — API integration and UI logic.
- **[NEW]** `frontend/index.css` — Styling and design system.

---

### Phase 3: Monitoring & Feedback

Three concurrent monitoring streams govern ongoing system health after deployment.

- **Operational monitoring**: Latency, throughput, and error rates guard service reliability.
- **Model health monitoring**: Score distributions are tracked over time; covariate drift is detected automatically.
- **Human feedback channel**: Analyst label corrections and decision overrides surfaced through the dashboard are logged and aggregated.

When accumulated drift signals or label volume cross a configurable threshold, a **periodic retraining loop** is triggered — updating model weights and redeploying through the same inference pipeline without requiring changes to the integration layer.

**Deliverables:**
- `src/monitoring/health.py` — Score distribution tracking and drift detection logic.
- `src/monitoring/ops.py` — Latency, throughput, and error rate logging.
- `src/feedback/collector.py` — Analyst override and label correction ingestion.
- `src/training/retrain_trigger.py` — Threshold-based retraining trigger.

---

## 4. Verification Plan

The system is considered production-ready when all three of the following conditions are satisfied:

1. **Automated unit tests** confirm endpoint correctness on held-out transaction samples, verifying that predictions and SHAP values match expected outputs from saved model artifacts.
2. **End-to-end integration tests** validate the complete data-to-dashboard flow across all three signal channels — from webhook receipt through scoring to dashboard display.
3. **Analyst sign-off** confirms that generated explanations accurately reflect the factors driving each risk score, assessed on a manually reviewed sample of flagged cases.

---

## 5. Proposed Changes Summary

| Type | File | Purpose |
|------|------|---------|
| NEW | `src/api/integration/webhook_receiver.py` | Inbound event receiver |
| NEW | `src/api/integration/schemas.py` | Payload contract definition |
| NEW | `src/api/main.py` | FastAPI serving layer |
| MODIFY | `src/fraud_detection/pipelines/supervised.py` | Real-time tabular inference |
| MODIFY | `src/fraud_detection/pipelines/ensemble.py` | Multi-modal fusion logic |
| MODIFY | `src/fraud_detection/pipelines/explainability.py` | SHAP + subgraph evidence |
| MODIFY | `src/fraud_detection/pipelines/anomaly.py` | Graph and text scoring |
| NEW | `src/monitoring/health.py` | Drift detection |
| NEW | `src/monitoring/ops.py` | Operational metrics |
| NEW | `src/feedback/collector.py` | Analyst feedback ingestion |
| NEW | `src/training/retrain_trigger.py` | Retraining loop trigger |
| NEW | `frontend/index.html` | Dashboard entry |
| NEW | `frontend/app.js` | UI logic and API integration |
| NEW | `frontend/index.css` | Styling |
