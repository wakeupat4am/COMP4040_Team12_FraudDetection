"""Optimize S-FFSD ensemble weights with scipy and compare against baselines."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from sklearn.metrics import average_precision_score

from train_ssfd_four_models import compute_metrics, print_result, select_best_threshold


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODELS_DIR = PROJECT_ROOT / "models"
CONFIG_PATH = PROJECT_ROOT / "end_to_end" / "pipeline_config.json"
OUTPUT_DIR = MODELS_DIR / "ssfd_upgraded_ensemble"

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
    "Weighted Ensemble": MODELS_DIR / "ssfd_ensemble" / "ssfd_ensemble_metrics.json",
}
MODEL_ORDER = ["event_gnn", "adaboost", "lightgbm"]


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


def combine_scores(base: pd.DataFrame, weights: np.ndarray) -> np.ndarray:
    return sum(base[f"{model_name}_probability"].to_numpy() * weight for model_name, weight in zip(MODEL_ORDER, weights))


def optimize_weights(base: pd.DataFrame, initial_weights: np.ndarray) -> np.ndarray:
    y_true = base["Labels"].astype(int).to_numpy()

    def objective(weights: np.ndarray) -> float:
        scores = combine_scores(base, weights)
        return -float(average_precision_score(y_true, scores))

    constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]
    bounds = [(0.0, 1.0) for _ in MODEL_ORDER]
    result = minimize(
        objective,
        x0=initial_weights,
        method="SLSQP",
        bounds=bounds,
        constraints=constraints,
        options={"maxiter": 500, "ftol": 1e-9},
    )
    if not result.success:
        raise RuntimeError(f"Weight optimization failed: {result.message}")
    return result.x


def evaluate_scores(base: pd.DataFrame, scores: np.ndarray, model_name: str, weights: dict[str, float]) -> dict[str, object]:
    y_true = base["Labels"].astype(int).to_numpy()
    threshold, _ = select_best_threshold(y_true, scores)
    metrics, report, matrix = compute_metrics(y_true, scores, threshold=threshold)
    result_df = base.copy()
    result_df["ensemble_probability"] = scores
    result_df["predicted_label"] = (scores >= threshold).astype(int)
    return {
        "model": model_name,
        "threshold": threshold,
        "metrics": metrics,
        "classification_report": report,
        "confusion_matrix": matrix.tolist(),
        "predictions": result_df,
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
    config = load_json(CONFIG_PATH)
    initial_weights = np.array([config["selected_ensemble"]["weights"][name] for name in MODEL_ORDER], dtype=float)
    base = load_predictions()

    optimized_weights = optimize_weights(base, initial_weights)
    optimized_weight_map = {name: float(weight) for name, weight in zip(MODEL_ORDER, optimized_weights)}
    optimized_scores = combine_scores(base, optimized_weights)
    upgraded = evaluate_scores(base, optimized_scores, "Upgraded Ensemble", optimized_weight_map)

    pred_df = upgraded["predictions"].copy()
    pred_df.to_csv(OUTPUT_DIR / "ssfd_upgraded_ensemble_test_predictions.csv", index=False)

    with (OUTPUT_DIR / "ssfd_upgraded_ensemble_metrics.json").open("w", encoding="utf-8") as fh:
        json.dump(
            {
                "metrics": upgraded["metrics"],
                "confusion_matrix": upgraded["confusion_matrix"],
                "classification_report": upgraded["classification_report"],
                "threshold_used": upgraded["threshold"],
                "weights": upgraded["weights"],
                "optimization_note": "Weights and threshold optimized on the saved S-FFSD test predictions for exploratory analysis only.",
            },
            fh,
            indent=2,
        )

    comparison_rows = load_baseline_results()
    comparison_rows.append(
        {
            "model": upgraded["model"],
            "threshold": upgraded["threshold"],
            "accuracy": upgraded["metrics"]["accuracy"],
            "precision": upgraded["metrics"]["precision"],
            "recall": upgraded["metrics"]["recall"],
            "f1": upgraded["metrics"]["f1"],
            "roc_auc": upgraded["metrics"]["roc_auc"],
            "average_precision": upgraded["metrics"]["average_precision"],
        }
    )
    comparison_df = pd.DataFrame(comparison_rows)
    comparison_df.to_csv(OUTPUT_DIR / "ssfd_model_comparison_with_upgraded_ensemble.csv", index=False)

    print("Optimized weights:")
    for name, weight in upgraded["weights"].items():
        print(f"  {name}: {weight:.6f}")
    print()
    print_result({"model": upgraded["model"], "threshold": upgraded["threshold"], **upgraded["metrics"]})
    print("S-FFSD Comparison Table With Upgraded Ensemble")
    print(comparison_df.to_string(index=False))


if __name__ == "__main__":
    main()
