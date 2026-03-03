---
title: "Proposal: Explainable Multi-Modal Risk Detection for Online Stores (Fraud/Abuse + Churn)"
---

# Proposal: Explainable Multi-Modal Risk Detection for Online Stores (Fraud/Abuse + Churn)

## Motivation

### Problem
We tackle an applied data-mining problem: building a production-ready system that:

1. flags suspicious transactions/orders (fraud/abuse/return abuse), and  
2. predicts customer churn risk,

while providing human-readable explanations (“why this case is risky”) suitable for operations and customer support.

### Why it matters / impact
- Fraud/abuse directly causes financial loss (chargebacks, refunds, shipping loss) and operational burden.
- Overly aggressive blocking creates false positives, reducing conversion and damaging trust.
- Churn reduces customer lifetime value; early intervention can improve retention.

### Key challenges
- **Rare & delayed labels:** fraud labels are sparse, imbalanced, and sometimes delayed (e.g., chargeback weeks later).
- **Heterogeneous modalities:** tabular + clickstream + text + graph (and optional images) must be aligned to the same entity (order/user/session) without leakage.
- **Adversarial drift:** attackers adapt; patterns shift quickly.
- **Graph scale & complexity:** “fraud rings” hide in large user–device–IP–address–payment networks.
- **Explainability:** explanations must be faithful, actionable, and fast enough for near-real-time triage (SHAP for tabular, subgraph evidence for graph, highlighted snippets for text).

---

## Method
We propose a multi-module risk pipeline that produces a unified, structured output per case (order/user) and a linked evidence store.

### Data ingestion and entity resolution
Join and aggregate data into consistent keys: `user_id`, `order_id`, `session_id`, `ticket_id`.

- Orders/payments/refunds/cancels → tabular facts  
- Clickstream logs → funnel/timing/session features  
- Support tickets/chat/reviews → text features + evidence snippets  
- Relationship graph → user–device–ip–address–payment edges  

### Core data-mining techniques

#### A. Outlier / anomaly detection (weakly supervised or unsupervised)
- Baselines: Isolation Forest (fast, strong baseline)
- Deep option: Autoencoder for mixed tabular/log features
- Graph anomaly option: GNN-based anomaly score on node/edge patterns (useful when rings dominate)

#### B. Graph mining for fraud rings
Build a heterogeneous graph (nodes: users, devices, IPs, addresses, payment instruments; edges: observed relations). Use:

- Community detection for ring discovery
- Node classification / link prediction to score suspicious entities and hidden ties
- Benchmark graph-fraud methodology using known graph fraud datasets such as YelpChi (review spam graph) and FraudAmazon (fraudulent user detection in review graph)

#### C. NLP for complaints & abuse signals
- Topic/intent classification + sentiment/urgency + NER for order/product identifiers (turn text into structured signals)
- Embeddings with Sentence-BERT-style encoders for robust features across paraphrases
- Train a text risk classifier and store highlight spans as evidence

#### D. Supervised prediction for churn / return / fraud outcomes
Gradient-boosted trees (LightGBM/XGBoost) as the primary supervised baseline for tabular + aggregated multi-modal features.

Targets:

- \(p_{\text{fraud\_outcome}}\)
- \(p_{\text{return\_abuse}}\)
- \(p_{\text{churn}}\)

where outcomes include chargeback/confirmed abuse; churn can be defined via an inactivity window or retention label.

#### E. Explainability (multi-channel)
- Tabular explanations via SHAP
- Graph explanations via subgraph-based explainers:
  - GNNExplainer
  - SubgraphX (Shapley + subgraph search)
  - PGExplainer (parameterized explanations for inductive/generalizable settings)
- Text explanations via highlighted snippets (attention/gradient-based or post-hoc rationale extraction)

### Ensemble decisioning (product-friendly)
Create module scores and a meta-model:

- **Score_1:** anomaly score (tabular + log)
- **Score_2:** graph risk score (rings/relations)
- **Score_3:** text risk score (complaint/abuse cues)

A meta-model learns the best combination into a final risk score and risk bucket.

**Final product output:**  
A structured case table (1 row per `order_id` or `user_id`) plus evidence tables for drill-down.

---

## Intended experiments

### Data: what we already have vs. what we will obtain

#### Primary (preferred): internal e-commerce data (production-like)
We will obtain data by instrumenting and exporting from:

- Transactional DB / order management: orders, items, totals, discounts, payment method, shipping, cancellations, refunds
- Payment/chargeback logs (from PSP/gateway): authorization outcomes, chargeback flags, dispute reason codes
- Clickstream / web-app logs: view → add-to-cart → checkout funnels, timestamps, session length, device/browser fingerprints
- Support system (CRM): tickets, chat transcripts, complaint reasons, outcomes (refund approved/denied)
- Identity graph sources: IP logs, device IDs, addresses, payment tokens → build user–device–ip–address–payment network

#### Public datasets (benchmarking and early prototyping)
- Fraud (tabular transactions): IEEE-CIS Fraud Detection (Kaggle; real e-commerce transaction features)
- E-commerce orders + reviews + payments: Olist Brazilian E-Commerce dataset (orders, payments, shipping, reviews)
- Clickstream / sessions: RetailRocket e-commerce behavior dataset and Yoochoose / RecSys Challenge 2015 sessions
- Graph fraud benchmarks: YelpChi review spam graph (Rayana & Akoglu) and FraudAmazon (DGL)
- Graph illicit transactions (optional reference): Elliptic++ / Elliptic labeled transaction graphs (to validate graph methods)

### Experiments we will run (phased)

#### Phase 0 — Data schema & leakage-safe joins
- Define entity tables and time-aware feature windows (e.g., “features available at decision time”).
- Validate label definitions (fraud outcome, churn window) and handle delayed labels.

#### Phase 1 — Baselines by modality (ablation ladder)
- Tabular-only supervised model (LightGBM)
- Clickstream aggregated features (funnel timing, burstiness)
- Text features (topic/sentiment/NER + embeddings)
- Graph features (degree, shared device/IP counts, PageRank, motifs)
- Optional: GNN model for graph risk + GNN explainers

#### Phase 2 — Anomaly module and semi-supervised variants
- Isolation Forest vs. Autoencoder vs. (optional) graph anomaly methods
- Compare usefulness for cold-start and label-scarce settings

#### Phase 3 — Ensemble and calibration
- Train meta-model combining module scores (final risk)
- Calibrate probabilities (important for ops thresholds and expected loss)

#### Phase 4 — Explainability evaluation
- Human-centered: case studies (≥ 20) showing SHAP + subgraph + text spans
- Technical: explanation fidelity/sparsity (graph explainer metrics), stability across retrains

---

## Evaluation plan

### Primary detection metrics (imbalanced)
- PR-AUC / Average Precision
- Recall@K (ops capacity: top-K cases/day)
- False positive cost proxy (blocked legitimate orders)
- Calibration (Brier score / reliability curves)

### Operational metrics
- Latency per case (near-real-time constraints)
- Throughput (events/sec)
- Drift monitoring: performance over time slices (weekly/monthly)

### Churn metrics
- PR-AUC / ROC-AUC, lift in top deciles
- Business-oriented: retention uplift simulation (if interventions exist)
