# Recommended Project Structure

This repository is now organized for a data-science workflow that can evolve
into a production pipeline without large refactors.

## Top-Level Layout

- `configs/`: versioned YAML configs for paths, data contracts, and model defaults
- `data/`: staged datasets (`raw`, `interim`, `processed`, `external`)
- `docs/`: architecture and implementation notes
- `models/`: trained model artifacts and serialized explainers
- `notebooks/`: exploratory analysis only
- `reports/`: generated figures and final outputs
- `scripts/`: one-off or entry-point scripts
- `src/`: reusable Python package code
- `tests/`: automated tests

## Why This Layout

- Separates raw data from transformed datasets to reduce leakage risk.
- Keeps experiment logic in `src/` so notebooks stay thin.
- Leaves space for separate modules that match the proposal's modalities.
- Makes later CI, packaging, and scheduled training jobs easier to add.
