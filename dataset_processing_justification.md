# Dataset Processing Justification

This document explains how the two main fraud datasets in this repo, `PaySim` and `S-FFSD`, were processed, why they were processed differently, and how each one was used in the project.

## Summary

The two datasets do not play the same role:

- `PaySim` is a secondary benchmark and diagnostic dataset.
- `S-FFSD` is the primary dataset for final model selection and the current end-to-end fraud scoring runtime.

That difference is intentional. The repo treats `PaySim` as useful for fast experimentation and sanity checks, but not strong enough to justify the final deployment-oriented pipeline. `S-FFSD` is treated as the more realistic basis for the selected ensemble and the current backend behavior.

## Why The Datasets Were Handled Differently

### PaySim

`PaySim` is a simulator. It is easy to work with and large enough for fast benchmarking, but it also contains simulator-driven balance patterns that can make fraud detection look easier than it really is.

The repo explicitly checks for that risk in [models/check_paysim_leakage.py](models/check_paysim_leakage.py). That diagnostic measures:

- single-feature separability for suspicious balance-derived features
- shuffled-label behavior
- graph overlap between train and test entities

The result is stored in [models/paysim_leakage_diagnostics.json](models/paysim_leakage_diagnostics.json) and is also reflected in [fraud_detection_quick_overview.md](fraud_detection_quick_overview.md).

Because of those shortcut risks, `PaySim` was not used as the final production dataset.

### S-FFSD

`S-FFSD` is treated as the main dataset because it creates more meaningful differences between model families and better supports the final design goal:

- raw transaction input
- internal history construction
- temporal / relational fraud modeling
- ensemble scoring

That is why the runtime, calibrated ensemble, and backend-facing artifacts all point to S-FFSD-derived assets.

## How PaySim Was Processed

### Preprocessing goal

The PaySim preprocessing flow was designed to convert the raw simulator data into a chronological transaction table with:

- balance-consistency features
- account-history features
- pair-history features
- type indicators

The main preprocessing work is documented in [notebooks/paysim_preprocess_feature_engineering.ipynb](notebooks/paysim_preprocess_feature_engineering.ipynb).

### Engineered features

The notebook creates features such as:

- raw balance fields:
  - `oldbalanceOrg`
  - `newbalanceOrig`
  - `oldbalanceDest`
  - `newbalanceDest`
- balance-delta features:
  - `org_balance_delta`
  - `dest_balance_delta`
  - `org_delta_minus_amount`
  - `dest_delta_minus_amount`
- balance anomaly flags:
  - `org_balance_error_flag`
  - `dest_balance_error_flag`
- chronological behavior features:
  - `orig_tx_count_so_far`
  - `dest_tx_count_so_far`
  - `orig_dest_pair_count_so_far`
  - `orig_step_gap`
  - `dest_step_gap`
  - `pair_step_gap`
  - `orig_amount_mean_before`
  - `dest_amount_mean_before`
  - `amount_vs_orig_mean`
  - `amount_vs_dest_mean`

The output of that stage is [data/interim/paysim_ready_features.csv](data/interim/paysim_ready_features.csv).

### Split policy

PaySim was evaluated using chronological `step` windows rather than random splits. The main training utility is [models/train_paysim_four_models.py](models/train_paysim_four_models.py).

Two split protocols exist in the repo:

- primary PaySim model split:
  - train: steps `500-649`
  - val: steps `650-699`
  - test: steps `700-743`
- stricter chronological split:
  - train: steps `451-580`
  - val: steps `581-640`
  - test: steps `641-700`
  - implemented in [models/run_paysim_strict_comparison.py](models/run_paysim_strict_comparison.py)

Only transaction types `CASH_OUT` and `TRANSFER` are kept for these model comparisons, because those are the fraud-relevant transaction classes in the PaySim setup.

### Models trained on PaySim

The repo trains and compares:

- Logistic Regression
- LightGBM
- AdaBoost
- Heterogeneous GNN
- Event-Based GNN

Artifacts and comparison outputs are stored under:

- [models/paysim_comparison](models/paysim_comparison)
- [models/paysim_strict_comparison](models/paysim_strict_comparison)
- [models/paysim_lightgbm](models/paysim_lightgbm)
- [models/paysim_adaboost](models/paysim_adaboost)
- [models/paysim_event_gnn](models/paysim_event_gnn)
- [models/paysim_hetero_gnn](models/paysim_hetero_gnn)

### Why this processing is justified

This processing was useful because it let the project:

- test tabular and graph models on a large chronological transaction stream
- compare baseline families quickly
- inspect whether graph models help under a simulator setting
- detect whether the dataset rewards shortcut learning

The final judgment was that PaySim is informative, but not trustworthy enough to drive the deployed pipeline by itself.

## How S-FFSD Was Processed

### Preprocessing goal

The S-FFSD preprocessing flow was designed to support both:

- tabular fraud models
- temporal / event-graph fraud models

The main exploratory and preprocessing work is documented in [notebooks/ssfd_eda_preprocessing.ipynb](notebooks/ssfd_eda_preprocessing.ipynb).

### Output artifacts

The key processed outputs used by the repo are:

- [data/processed/ssfd_lightgbm_train.csv](data/processed/ssfd_lightgbm_train.csv)
- [data/processed/ssfd_lightgbm_test.csv](data/processed/ssfd_lightgbm_test.csv)
- [data/processed/ssfd_lightgbm_unlabeled.csv](data/processed/ssfd_lightgbm_unlabeled.csv)
- [data/processed/ssfd_lightgbm_split_summary.csv](data/processed/ssfd_lightgbm_split_summary.csv)

The notebook also exports graph-oriented node and edge tables into `data/interim/`, including event, source, target, location, and type relationships.

### Why there is an unlabeled split

The `ssfd_lightgbm_unlabeled.csv` file is intentional. It is used as historical context without being treated as a supervised training label source.

That matters because the project is trying to simulate a deployment scenario where:

- current transactions are scored using information from earlier events
- historical context can exist even when labels are not immediately available

### Training and feature construction

The central S-FFSD training utility is [models/train_ssfd_four_models.py](models/train_ssfd_four_models.py).

It creates:

- chronological history features with `build_history_features()`
- tabular feature sets for LightGBM and AdaBoost
- event-based graph structures for the Event-GNN
- a broader heterogeneous graph baseline for comparison

Important S-FFSD history features include:

- source and target counts so far
- pair counts so far
- time gaps by source, target, and pair
- amount means before the current event
- deviations from historical means
- repeated interaction indicators

This is the core justification for S-FFSD processing in the project: the data is transformed into a form that supports the exact online-scoring logic the backend later expects.

### Validation-based final selection

The repo’s final report freezes the main result set around a validation-based chronological S-FFSD protocol, described in [Final_Report/final_report_sections.md](Final_Report/final_report_sections.md).

That protocol was used to:

- compare final candidate models
- pick ensemble members
- select weights and thresholds without tuning directly on the final test set

This is a cleaner and more defensible setup than a single hold-out decision process.

## How The Processed Datasets Were Used In The Project

### PaySim usage

PaySim was used for:

- early benchmarking
- comparing tabular vs graph models in a simulator setting
- strict chronological split experiments
- leakage and shortcut-signal diagnostics
- report figures such as:
  - [figures/paysim_strict_model_comparison.png](figures/paysim_strict_model_comparison.png)
  - [figures/paysim_shortcut_signal.png](figures/paysim_shortcut_signal.png)

PaySim was not used as the production runtime dataset.

### S-FFSD usage

S-FFSD was used for:

- final model-family comparison
- final ensemble member selection
- validation-time thresholding and calibration
- runtime artifact generation
- historical-state bootstrapping for the scoring pipeline
- current backend scoring behavior

The runtime dependence on S-FFSD is visible in:

- [end_to_end/pipeline_config.json](end_to_end/pipeline_config.json)
  - active profile is `ssfd_production_candidate`
- [end_to_end/model_loader.py](end_to_end/model_loader.py)
  - imports S-FFSD feature definitions and loads S-FFSD ensemble artifacts
- [end_to_end/state_store.py](end_to_end/state_store.py)
  - bootstraps internal history from processed S-FFSD files

In practical terms, the current API and backend are serving an S-FFSD-derived model stack, not a PaySim-derived one.

## Final Justification

The dataset processing decisions are justified by the different roles of the datasets:

- `PaySim` was processed to support broad benchmarking and to test whether simple tabular or graph models appear strong under a simulator. The project then explicitly tested whether that strength was real or artifact-driven.
- `S-FFSD` was processed to support the actual deployment-oriented fraud pipeline: chronological history features, event-graph construction, calibrated ensemble scoring, and backend runtime integration.

This is why the project keeps both datasets in the repo history, but only one of them, `S-FFSD`, drives the current end-to-end fraud scoring system.
