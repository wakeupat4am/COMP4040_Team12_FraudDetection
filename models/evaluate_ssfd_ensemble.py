"""Evaluate the selected S-FFSD ensemble against saved single-model outputs."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from train_ssfd_four_models import compute_metrics, print_result


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODELS_DIR = PROJECT_ROOT / "models"
CONFIG_PATH = PROJECT_ROOT / "end_to_end" / "pipeline_config.json"
OUTPUT_DIR = MODELS_DIR / "ssfd_ensemble"

KEY_COLUMNS = ["Time", "Source", "Target", "Amount", "Location", "Type", "Labels"]
PREDICTION_FILES = {
    "lightgbm": MODELS_DIR / "ssfd_lightgbm" / "ssfd_lightgbm_test_predictions.csv",
    "adaboost": MODELS_DIR / "ssfd_adaboost" / "ssfd_adaboost_test_predictions.csv",
    "event_gnn": MODELS_DIR / "ssfd_event_gnn" / "ssfd_event_gnn_test_predictions.csv",
}
METRIC_FILES = {
    "LightGBM": MODELS_DIR / "ssfd_lightgbm" / "ssfd_lightgbm_metrics.json",
    "AdaBoost": MODELS_DIR / "ssfd_adaboost" / "ssfd_adaboost_metrics.json",
    "Heterogeneous GNN": MODELS_DIR / "ssfd_hetero_gnn" / "ssfd_hetero_gnn_metrics.json",
    "Event-Based GNN": MODELS_DIR / "ssfd_event_gnn" / "ssfd_event_gnn_metrics.json",
    "Logistic Regression": MODELS_DIR / "ssfd_logistic_regression" / "ssfd_logistic_regression_metrics.json",
}


def load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_predictions() -> pd.DataFrame:
    frames: dict[str, pd.DataFrame] = {}
    for model_name, path in PREDICTION_FILES.items():
        df = pd.read_csv(path)
        df = df[KEY_COLUMNS + ["predicted_probability", "predicted_label"]].copy()
        df = df.rename(
            columns={
                "predicted_probability": f"{model_name}_probability",
                "predicted_label": f"{model_name}_label",
            }
        )
        frames[model_name] = df

    merged = frames["lightgbm"].copy()
    for model_name in ["adaboost", "event_gnn"]:
        merged = merged.merge(frames[model_name], on=KEY_COLUMNS, how="inner")
    return merged


def evaluate_weighted_average(base: pd.DataFrame) -> dict[str, object]:
    config = load_json(CONFIG_PATH)
    weights = config["selected_ensemble"]["weights"]
    threshold = 0.5

    base = base.copy()
    base["ensemble_probability"] = (
        base["event_gnn_probability"] * weights["event_gnn"]
        + base["adaboost_probability"] * weights["adaboost"]
        + base["lightgbm_probability"] * weights["lightgbm"]
    ) / sum(weights.values())

    y_true = base["Labels"].astype(int).to_numpy()
    y_score = base["ensemble_probability"].to_numpy()
    metrics, report, matrix = compute_metrics(y_true, y_score, threshold=threshold)
    return {
        "model": "Weighted Ensemble",
        "threshold": threshold,
        "metrics": metrics,
        "classification_report": report,
        "confusion_matrix": matrix.tolist(),
        "predictions": base,
        "weights": weights,
    }


def load_baseline_results() -> list[dict[str, object]]:
    rows = []
    for model_name, path in METRIC_FILES.items():
        payload = load_json(path)
        metrics = payload["metrics"]
        rows.append(
            {
                "model": model_name,
                "threshold": payload.get("threshold_used"),
                "accuracy": metrics["accuracy"],
                "precision": metrics["precision"],
                "recall": metrics["recall"],
                "f1": metrics["f1"],
                "roc_auc": metrics["roc_auc"],
                "average_precision": metrics["average_precision"],
            }
        )
    return rows


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    merged = load_predictions()
    ensemble = evaluate_weighted_average(merged)

    pred_df = ensemble["predictions"].copy()
    pred_df["predicted_label"] = (pred_df["ensemble_probability"] >= ensemble["threshold"]).astype(int)
    pred_df.to_csv(OUTPUT_DIR / "ssfd_ensemble_test_predictions.csv", index=False)

    with (OUTPUT_DIR / "ssfd_ensemble_metrics.json").open("w", encoding="utf-8") as fh:
        json.dump(
            {
                "metrics": ensemble["metrics"],
                "confusion_matrix": ensemble["confusion_matrix"],
                "classification_report": ensemble["classification_report"],
                "threshold_used": ensemble["threshold"],
                "weights": ensemble["weights"],
            },
            fh,
            indent=2,
        )

    comparison_rows = load_baseline_results()
    comparison_rows.append(
        {
            "model": ensemble["model"],
            "threshold": ensemble["threshold"],
            "accuracy": ensemble["metrics"]["accuracy"],
            "precision": ensemble["metrics"]["precision"],
            "recall": ensemble["metrics"]["recall"],
            "f1": ensemble["metrics"]["f1"],
            "roc_auc": ensemble["metrics"]["roc_auc"],
            "average_precision": ensemble["metrics"]["average_precision"],
        }
    )
    comparison_df = pd.DataFrame(comparison_rows)
    comparison_df.to_csv(OUTPUT_DIR / "ssfd_model_comparison_with_ensemble.csv", index=False)

    print_result({"model": ensemble["model"], "threshold": ensemble["threshold"], **ensemble["metrics"]})
    print("S-FFSD Comparison Table")
    print(comparison_df.to_string(index=False))


if __name__ == "__main__":
    main()
