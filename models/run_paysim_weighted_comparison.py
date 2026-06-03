"""Run fraud-weighted PaySim models and compare them to the existing baseline runs."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from train_paysim_four_models import (
    OUTPUT_DIR as BASE_COMPARISON_DIR,
    PaySimEventGNN,
    PaySimHeteroGNN,
    build_event_data,
    build_graph_df_from_splits,
    build_hetero_data,
    evaluate_graph_model,
    load_saved_splits,
    train_adaboost,
    train_graph_model,
    train_lightgbm,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WEIGHTED_DIR = PROJECT_ROOT / "models" / "paysim_weighted_comparison"
FRAUD_WEIGHT_MULTIPLIER = 2.0


def load_baseline_metrics() -> dict[str, dict[str, float]]:
    mapping = {
        "LightGBM": PROJECT_ROOT / "models" / "paysim_lightgbm" / "metrics.json",
        "AdaBoost": PROJECT_ROOT / "models" / "paysim_adaboost" / "metrics.json",
        "Heterogeneous GNN": PROJECT_ROOT / "models" / "paysim_hetero_gnn" / "metrics.json",
        "Event-Based GNN": PROJECT_ROOT / "models" / "paysim_event_gnn" / "metrics.json",
    }
    baseline = {}
    for model_name, path in mapping.items():
        payload = json.loads(path.read_text())
        baseline[model_name] = {
            "threshold": float(payload["threshold_used"]),
            **payload["metrics"],
        }
    return baseline


def run_weighted_models() -> dict[str, dict[str, float]]:
    train_df, val_df, test_df = load_saved_splits()
    results: dict[str, dict[str, float]] = {}

    results["LightGBM"] = train_lightgbm(
        train_df,
        val_df,
        test_df,
        WEIGHTED_DIR / "lightgbm",
        fraud_weight_multiplier=FRAUD_WEIGHT_MULTIPLIER,
    )
    results["AdaBoost"] = train_adaboost(
        train_df,
        val_df,
        test_df,
        WEIGHTED_DIR / "adaboost",
        fraud_weight_multiplier=FRAUD_WEIGHT_MULTIPLIER,
    )

    graph_df = build_graph_df_from_splits(train_df, val_df, test_df)

    hetero_data = build_hetero_data(graph_df)
    hetero_dims = {node_type: hetero_data[node_type].x.size(-1) for node_type in hetero_data.node_types}
    hetero_model = PaySimHeteroGNN(hetero_data.metadata(), hetero_dims, hidden_dim=64)
    hetero_model, hetero_summary = train_graph_model(
        hetero_data,
        hetero_model,
        epochs=25,
        fraud_weight_multiplier=FRAUD_WEIGHT_MULTIPLIER,
    )
    results["Heterogeneous GNN"] = evaluate_graph_model(
        "Heterogeneous GNN",
        hetero_model,
        hetero_data,
        graph_df,
        hetero_summary,
        WEIGHTED_DIR / "heterogeneous_gnn",
    )

    event_data = build_event_data(graph_df)
    event_dims = {node_type: event_data[node_type].x.size(-1) for node_type in event_data.node_types}
    event_model = PaySimEventGNN(event_data.metadata(), event_dims, hidden_dim=64)
    event_model, event_summary = train_graph_model(
        event_data,
        event_model,
        epochs=25,
        fraud_weight_multiplier=FRAUD_WEIGHT_MULTIPLIER,
    )
    results["Event-Based GNN"] = evaluate_graph_model(
        "Event-Based GNN",
        event_model,
        event_data,
        graph_df,
        event_summary,
        WEIGHTED_DIR / "event_based_gnn",
    )
    return results


def build_comparison_df(baseline: dict[str, dict[str, float]], weighted: dict[str, dict[str, float]]) -> pd.DataFrame:
    rows = []
    for model_name in ["LightGBM", "AdaBoost", "Heterogeneous GNN", "Event-Based GNN"]:
        base = baseline[model_name]
        new = weighted[model_name]
        row = {
            "model": model_name,
            "fraud_weight_multiplier": FRAUD_WEIGHT_MULTIPLIER,
            "baseline_threshold": base["threshold"],
            "weighted_threshold": new["threshold"],
        }
        for metric in ["accuracy", "precision", "recall", "f1", "roc_auc", "average_precision"]:
            row[f"baseline_{metric}"] = base[metric]
            row[f"weighted_{metric}"] = new[metric]
            row[f"delta_{metric}"] = new[metric] - base[metric]
        rows.append(row)
    return pd.DataFrame(rows)


def main() -> None:
    WEIGHTED_DIR.mkdir(parents=True, exist_ok=True)
    baseline = load_baseline_metrics()
    weighted = run_weighted_models()
    comparison_df = build_comparison_df(baseline, weighted)
    comparison_df.to_csv(WEIGHTED_DIR / "weighted_vs_baseline.csv", index=False)

    print(f"PaySim Fraud-Weighted Comparison (multiplier={FRAUD_WEIGHT_MULTIPLIER})")
    print("=" * 58)
    for _, row in comparison_df.iterrows():
        print(row["model"])
        print(f"  threshold: {row['baseline_threshold']:.4f} -> {row['weighted_threshold']:.4f}")
        for metric in ["accuracy", "precision", "recall", "f1", "roc_auc", "average_precision"]:
            print(
                f"  {metric:>17}: "
                f"{row[f'baseline_{metric}']:.6f} -> {row[f'weighted_{metric}']:.6f} "
                f"(delta {row[f'delta_{metric}']:+.6f})"
            )
        print()


if __name__ == "__main__":
    main()
