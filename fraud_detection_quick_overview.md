# Quick Overview: Explainable Ensemble Fraud Detection for Online Transaction Systems

## 1. Topic Summary

This project builds a fraud detection system for online transactions. The goal is to identify suspicious transactions while controlling false alarms. Instead of relying on one model, the project compares several model families and selects a final ensemble model for deployment-oriented fraud scoring.

The final system uses a weighted ensemble of:

- **LightGBM** for tabular transaction patterns
- **AdaBoost** for better fraud-case coverage
- **Event-Based GNN** for temporal and relational transaction behavior

The system outputs a fraud risk score, a decision label, per-model scores, and explanation fields.

---

## 2. Problem Being Solved

Each transaction contains fields such as:

- sender
- receiver
- amount
- timestamp
- transaction type
- other transaction attributes

The task is to learn a scoring function:

```text
transaction + historical state → fraud risk score
```

The score is then compared with a threshold:

```text
if score ≥ threshold → fraud
if score < threshold → legitimate
```

A key requirement is **time awareness**: the model must only use information available before or at the transaction time. This prevents future-information leakage and better reflects real deployment.

---

## 3. Models Compared

### Logistic Regression

Used as a simple linear baseline. It checks whether fraud can be separated using a simple decision boundary. It is useful for comparison but not strong enough for final deployment.

### LightGBM

A strong tabular boosting model. It works well with structured transaction features and historical aggregates. It provides good ranking quality but has lower recall than some other models.

### AdaBoost

A boosting model that focuses more on difficult examples. In this project, it improves fraud coverage and achieves better recall than LightGBM.

### Heterogeneous GNN

A graph-based baseline that models relationships between different entity types. It is useful for comparison but performs worse than Event-Based GNN.

### Event-Based GNN

The strongest balanced single model. It treats each transaction as a temporal event between sender and receiver and uses previous interaction context. This makes it suitable for fraud patterns that depend on repeated or suspicious relationships.

### Final Ensemble

The final ensemble combines LightGBM, AdaBoost, and Event-Based GNN:

```text
ensemble_score = w1 * LightGBM_score + w2 * AdaBoost_score + w3 * EventGNN_score
```

The weights and threshold are selected on the validation set, while the test set is reserved for final evaluation.

---

## 4. Dataset Choice

The project uses two datasets:

### PaySim

PaySim is treated as a secondary benchmark. Although models achieve very high performance on it, shortcut-signal diagnostics show that some simulator-specific features are too predictive. For example, balance-derived features alone can strongly predict fraud.

This suggests that PaySim may reward shortcut exploitation instead of real fraud understanding.

### S-FFSD

S-FFSD is used as the primary dataset for final model selection. It produces more meaningful differences between model families and better reflects realistic tradeoffs between precision, recall, F1-score, ROC-AUC, and average precision.

---

## 5. Key Results

On S-FFSD:

- **Event-Based GNN** is the strongest balanced single model.
- **The ensemble** achieves the highest precision and ROC-AUC.
- The ensemble is selected for deployment because high precision reduces false alarms, while high ROC-AUC means the system ranks transactions well across different thresholds.

Selected reported results:

| Model | Accuracy | Precision | Recall | F1 | ROC-AUC | AP |
|---|---:|---:|---:|---:|---:|---:|
| LightGBM | 0.6978 | 0.7769 | 0.3434 | 0.4763 | 0.9023 | 0.7574 |
| AdaBoost | 0.8742 | 0.8817 | 0.7918 | 0.8344 | 0.9255 | 0.8635 |
| Event-GNN | 0.8919 | 0.9070 | 0.8133 | 0.8576 | 0.9270 | 0.9097 |
| Ensemble | 0.8781 | 0.9175 | 0.7640 | 0.8338 | 0.9403 | 0.8810 |

---

# 6. End-to-End System Design

This is the most deployment-focused part of the project. The idea is to convert the offline model comparison into a practical fraud scoring workflow.

## 6.1 Main Design Goal

The system should accept a **raw transaction request** and return a structured fraud decision.

The caller should not manually provide historical or graph features. Instead, the system builds those features internally.

---

## 6.2 Input

The input is a raw transaction request containing immutable transaction fields, such as:

```json
{
  "transaction_id": "TX123",
  "timestamp": "2026-06-03T10:30:00Z",
  "sender_id": "U001",
  "receiver_id": "U052",
  "amount": 250.00,
  "location": "Hanoi",
  "transaction_type": "transfer"
}
```

The user or external caller only sends basic transaction information.

---

## 6.3 Historical State Layer

The system maintains an internal historical state layer. This layer stores information from previous transactions, including:

- sender history
- receiver history
- sender–receiver pair history
- recent activity statistics
- previous transaction amounts
- transaction frequency
- local graph/event context

This layer is important because fraud risk often depends on past behavior, not only the current transaction row.

Example questions the historical state layer helps answer:

- Has this sender made many recent transactions?
- Has this sender interacted with this receiver before?
- Is the amount unusual for this sender?
- Is this sender–receiver pair newly formed?
- Is there a sudden burst of activity?

---

## 6.4 Feature Construction

After receiving a transaction, the system constructs two types of evidence.

### A. Tabular Features

These are used by LightGBM and AdaBoost.

Examples:

- transaction amount
- transaction type
- sender transaction count
- receiver transaction count
- average sender amount
- average receiver amount
- sender–receiver pair frequency
- recent sender activity
- recent receiver activity

### B. Event-Graph Context

This is used by Event-Based GNN.

The system constructs a local event graph around the transaction. The graph represents recent relationships and interactions between sender, receiver, and other related entities.

This allows the model to detect suspicious relational patterns, such as repeated interactions, abnormal transaction sequences, or risky sender–receiver behavior.

---

## 6.5 Model Scoring

The constructed features are sent to the selected models:

```text
Tabular features → LightGBM → LightGBM score
Tabular features → AdaBoost → AdaBoost score
Event-graph context → Event-GNN → Event-GNN score
```

Each model outputs a fraud probability or risk score.

---

## 6.6 Weighted Ensemble

The model scores are combined into a final ensemble score:

```text
final_score = w1 * LightGBM_score + w2 * AdaBoost_score + w3 * EventGNN_score
```

The final score is compared with a selected threshold:

```text
if final_score ≥ threshold:
    decision = "fraud / review"
else:
    decision = "legitimate"
```

The threshold can be adjusted depending on business needs:

- lower threshold → catch more fraud, but more false alarms
- higher threshold → fewer false alarms, but more missed fraud

---

## 6.7 Output

The system returns a structured response such as:

```json
{
  "transaction_id": "TX123",
  "fraud_score": 0.87,
  "decision": "review",
  "threshold": 0.75,
  "model_scores": {
    "LightGBM": 0.82,
    "AdaBoost": 0.89,
    "Event_GNN": 0.91
  },
  "explanation": {
    "main_risk_source": "agreement_between_tabular_and_graph_models",
    "tabular_signal": "high",
    "graph_signal": "high",
    "reason": "All selected models assign high risk to this transaction."
  }
}
```

The output is designed to support both automatic decision making and manual fraud review.

---

## 6.8 Explanation Fields

The project uses lightweight explanation fields based on model scores and model agreement.

Possible explanation types:

| Pattern | Meaning |
|---|---|
| High LightGBM + High AdaBoost + High Event-GNN | Strong agreement; high-risk transaction |
| High tabular scores + Low Event-GNN | Risk mainly comes from transaction attributes |
| Low tabular scores + High Event-GNN | Risk mainly comes from relational/graph behavior |
| Mixed scores | Uncertain case; may need manual review |

This makes the system more interpretable than returning only a binary fraud/not-fraud label.

---

## 6.9 Full Pipeline

```text
Raw Transaction Request
        ↓
Historical State Layer
        ↓
Tabular Feature Construction + Event-Graph Construction
        ↓
LightGBM / AdaBoost / Event-Based GNN
        ↓
Weighted Ensemble
        ↓
Fraud Risk Score
        ↓
Decision + Explanation Fields
```

---

## 7. Strengths of the System Design

- It starts from raw transaction requests, which makes it realistic.
- It avoids requiring users to manually provide engineered features.
- It uses historical state, which is essential for fraud detection.
- It combines tabular and graph-based evidence.
- It provides per-model scores and explanation fields.
- It supports threshold adjustment based on fraud-risk tolerance or review capacity.

---

## 8. Limitations

The current design is still offline and conceptual. A real deployment would need:

- latency testing
- probability calibration
- live monitoring
- fraud feedback labels
- retraining strategy
- drift detection
- cost-sensitive threshold selection
- stronger explanation methods such as SHAP or graph explanations

---

## 9. Simple Presentation Summary

This project proposes an explainable fraud detection pipeline for online transactions. It compares linear, boosting-based, and graph-based models on PaySim and S-FFSD. PaySim is treated only as a secondary benchmark because shortcut diagnostics show that simulator-specific features are too predictive. S-FFSD is used for final model selection because it produces more realistic model tradeoffs.

The final system uses a weighted ensemble of LightGBM, AdaBoost, and Event-Based GNN. LightGBM captures tabular transaction patterns, AdaBoost improves fraud coverage, and Event-Based GNN captures temporal and relational behavior. The end-to-end system takes a raw transaction request, builds historical and graph-based features internally, scores the transaction using the three models, combines the scores, and returns a fraud decision with explanation fields.
