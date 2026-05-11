# End-to-End Pipeline Package

This folder defines the production-facing contract for the fraud-detection
system built from the current experiments.

## What Is In Scope

- input payload contract for a single transaction event
- required historical state for feature building and graph scoring
- output payload contract for risk scoring and analyst routing
- current model-selection decision for the first ensemble candidate
- a runnable pipeline skeleton that validates payloads and produces the final
  structured output from model scores

## Current Candidate Ensemble

Based on the `S-FFSD` experiments, the first ensemble candidate is:

- `Event-Based GNN`
- `AdaBoost`
- `LightGBM`

The current heterogeneous GNN is excluded from the first ensemble because it is
consistently weaker than the other three models.

## Key Files

- `input_schema.json`: required input fields for inference
- `output_schema.json`: expected output structure from the pipeline
- `pipeline_config.json`: model paths, weights, thresholds, and routing rules
- `feature_requirements.md`: required historical state and online features
- `ensemble_decision.md`: why the current candidate ensemble was selected
- `pipeline.py`: validation and output-orchestration skeleton
- `example_input.json`: minimal example request payload

## Current Status

This folder prepares the interface and orchestration layer. It does not yet
perform live model inference for all three selected models. The main missing
pieces are:

- calibrated probability mappings for each base model
- online feature store or state store implementation
- graph-state loader for event-GNN inference
- trained meta-model for stacking, if weighted averaging is replaced later
