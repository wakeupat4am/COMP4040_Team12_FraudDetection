# Ensemble Decision

## Current Candidate

The current first production candidate ensemble is:

- `Event-Based GNN`
- `AdaBoost`
- `LightGBM`

## Why These Three

- `Event-Based GNN` is the strongest sequence-aware model on `S-FFSD` and best
  matches the event-stream structure of the data.
- `AdaBoost` is a strong high-recall tabular baseline that aggressively focuses
  on hard fraud cases.
- `LightGBM` is a strong stable tabular model with a different bias from
  AdaBoost and useful for score diversity.

## Why Not Heterogeneous GNN

The current heterogeneous GNN is not included in the first ensemble because it
has not shown stable gains over the selected three models on `S-FFSD`.

## What Still Needs Validation

- probability calibration on validation predictions
- ensemble weights validated across multiple chronological splits
- cost-sensitive threshold selection
- output stability across time windows

## First Ensemble Rule

Use weighted averaging first:

- `event_gnn`: `0.50`
- `adaboost`: `0.30`
- `lightgbm`: `0.20`

This should later be replaced or confirmed by a validation-trained stacking
model if the out-of-fold predictions justify it.
