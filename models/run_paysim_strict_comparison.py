"""Run the four PaySim models on a stricter chronological split.

This script preserves the original PaySim baseline outputs and the original
leakage diagnostic file. It creates a broader, less pathological evaluation
window and writes all new artifacts under dedicated strict-split paths.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from train_paysim_four_models import (
    PaySimEventGNN,
    PaySimHeteroGNN,
    build_event_data,
    build_graph_df_from_splits,
    build_hetero_data,
    evaluate_graph_model,
    load_subset,
    print_result,
    save_split_bundle,
    train_adaboost,
    train_graph_model,
    train_lightgbm,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_ROOT / "models" / "paysim_strict_comparison"
STRICT_PREFIX = "paysim_strict_model"
STRICT_SPLIT_CONFIG = {
    "train": (451, 580),
    "val": (581, 640),
    "test": (641, 700),
    "valid_types": {"CASH_OUT", "TRANSFER"},
}


def build_summary(train_df: pd.DataFrame, val_df: pd.DataFrame, test_df: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "split": "train",
                "rows": len(train_df),
                "fraud": int(train_df["isFraud"].sum()),
                "fraud_ratio": float(train_df["isFraud"].mean()),
                "step_min": int(train_df["step"].min()),
                "step_max": int(train_df["step"].max()),
            },
            {
                "split": "val",
                "rows": len(val_df),
                "fraud": int(val_df["isFraud"].sum()),
                "fraud_ratio": float(val_df["isFraud"].mean()),
                "step_min": int(val_df["step"].min()),
                "step_max": int(val_df["step"].max()),
            },
            {
                "split": "test",
                "rows": len(test_df),
                "fraud": int(test_df["isFraud"].sum()),
                "fraud_ratio": float(test_df["isFraud"].mean()),
                "step_min": int(test_df["step"].min()),
                "step_max": int(test_df["step"].max()),
            },
        ]
    )


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    train_df, val_df, test_df = load_subset(STRICT_SPLIT_CONFIG)
    save_split_bundle(train_df, val_df, test_df, STRICT_PREFIX)

    summary = build_summary(train_df, val_df, test_df)
    summary.to_csv(OUTPUT_DIR / "subset_summary.csv", index=False)

    results = []
    results.append(train_lightgbm(train_df, val_df, test_df, OUTPUT_DIR / "lightgbm"))
    results.append(train_adaboost(train_df, val_df, test_df, OUTPUT_DIR / "adaboost"))

    graph_df = build_graph_df_from_splits(train_df, val_df, test_df)

    hetero_data = build_hetero_data(graph_df)
    hetero_in_dims = {node_type: hetero_data[node_type].x.size(-1) for node_type in hetero_data.node_types}
    hetero_model = PaySimHeteroGNN(hetero_data.metadata(), hetero_in_dims, hidden_dim=64)
    hetero_model, hetero_summary = train_graph_model(hetero_data, hetero_model, epochs=25)
    results.append(
        evaluate_graph_model(
            "Heterogeneous GNN",
            hetero_model,
            hetero_data,
            graph_df,
            hetero_summary,
            OUTPUT_DIR / "heterogeneous_gnn",
        )
    )

    event_data = build_event_data(graph_df)
    event_in_dims = {node_type: event_data[node_type].x.size(-1) for node_type in event_data.node_types}
    event_model = PaySimEventGNN(event_data.metadata(), event_in_dims, hidden_dim=64)
    event_model, event_summary = train_graph_model(event_data, event_model, epochs=25)
    results.append(
        evaluate_graph_model(
            "Event-Based GNN",
            event_model,
            event_data,
            graph_df,
            event_summary,
            OUTPUT_DIR / "event_based_gnn",
        )
    )

    results_df = pd.DataFrame(results)
    results_df.to_csv(OUTPUT_DIR / "comparison_metrics.csv", index=False)

    for result in results:
        print_result(result)
    print("Strict Subset Summary")
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
