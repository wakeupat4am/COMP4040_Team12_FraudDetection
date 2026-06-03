"""Train selected S-FFSD models with an explicit validation split and optimize an ensemble on validation only."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from lightgbm import LGBMClassifier
from scipy.optimize import minimize
from sklearn.ensemble import AdaBoostClassifier
from sklearn.metrics import average_precision_score
from sklearn.tree import DecisionTreeClassifier

from train_ssfd_four_models import (
    BaseHeteroClassifier,
    SSFD_ADABOOST_FEATURES,
    SSFD_LGBM_FEATURES,
    build_event_graph_df,
    build_history_features,
    compute_metrics,
    encode_categorical_statistics,
    load_saved_splits,
    print_result,
    save_metrics,
    save_predictions,
    select_best_threshold,
    train_graph_model,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_ROOT / "models" / "ssfd_validated_ensemble"
MODEL_ORDER = ["event_gnn", "adaboost", "lightgbm"]


def build_split_frames() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    train_all, test_df, unlabeled_df = load_saved_splits()
    train_all = train_all.sort_values("Time").reset_index(drop=True).copy()
    split_index = int(len(train_all) * 0.8)
    train_df = train_all.iloc[:split_index].copy()
    val_df = train_all.iloc[split_index:].copy()
    test_df = test_df.sort_values("Time").reset_index(drop=True).copy()
    unlabeled_df = unlabeled_df.sort_values("Time").reset_index(drop=True).copy()

    train_df["split"] = "train"
    val_df["split"] = "val"
    test_df["split"] = "test"
    unlabeled_df["split"] = "unlabeled"
    return train_df, val_df, test_df, unlabeled_df


def build_summary(train_df: pd.DataFrame, val_df: pd.DataFrame, test_df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for name, df in [("train", train_df), ("val", val_df), ("test", test_df)]:
        rows.append(
            {
                "split": name,
                "rows": len(df),
                "fraud": int(df["Labels"].sum()),
                "fraud_ratio": float(df["Labels"].mean()),
                "time_min": int(df["Time"].min()),
                "time_max": int(df["Time"].max()),
            }
        )
    return pd.DataFrame(rows)


def prepare_tree_splits(
    train_df: pd.DataFrame, val_df: pd.DataFrame, test_df: pd.DataFrame, unlabeled_df: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    combined = pd.concat([unlabeled_df, train_df, val_df, test_df], ignore_index=True)
    combined = build_history_features(combined)
    return (
        combined[combined["split"] == "train"].copy(),
        combined[combined["split"] == "val"].copy(),
        combined[combined["split"] == "test"].copy(),
    )


def evaluate_lightgbm(train_df: pd.DataFrame, val_df: pd.DataFrame, test_df: pd.DataFrame, out_dir: Path) -> tuple[dict[str, object], pd.DataFrame, pd.DataFrame]:
    X_train = train_df[SSFD_LGBM_FEATURES].copy()
    y_train = train_df["Labels"].astype(int)
    X_val = val_df[SSFD_LGBM_FEATURES].copy()
    y_val = val_df["Labels"].astype(int)
    X_test = test_df[SSFD_LGBM_FEATURES].copy()
    y_test = test_df["Labels"].astype(int)
    categorical_columns = ["Source", "Target", "Location", "Type"]
    for col in categorical_columns:
        X_train[col] = X_train[col].astype("category")
        X_val[col] = X_val[col].astype("category")
        X_test[col] = X_test[col].astype("category")

    neg = int((y_train == 0).sum())
    pos = int((y_train == 1).sum())
    model = LGBMClassifier(
        objective="binary",
        n_estimators=300,
        learning_rate=0.05,
        num_leaves=31,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        scale_pos_weight=neg / max(pos, 1),
        n_jobs=-1,
    )
    model.fit(X_train, y_train, categorical_feature=categorical_columns)
    val_scores = model.predict_proba(X_val)[:, 1]
    threshold, _ = select_best_threshold(y_val.to_numpy(), val_scores)
    test_scores = model.predict_proba(X_test)[:, 1]
    metrics, report, matrix = compute_metrics(y_test.to_numpy(), test_scores, threshold)

    out_dir.mkdir(parents=True, exist_ok=True)
    model.booster_.save_model(str(out_dir / "ssfd_lightgbm_model.txt"))
    pd.DataFrame({"feature": SSFD_LGBM_FEATURES, "importance": model.feature_importances_}).sort_values(
        "importance", ascending=False
    ).to_csv(out_dir / "ssfd_lightgbm_feature_importance.csv", index=False)
    val_pred = val_df.copy()
    val_pred["predicted_probability"] = val_scores
    val_pred["predicted_label"] = (val_scores >= threshold).astype(int)
    val_pred.to_csv(out_dir / "ssfd_lightgbm_val_predictions.csv", index=False)
    save_predictions(out_dir / "ssfd_lightgbm_test_predictions.csv", test_df, test_scores, threshold)
    save_metrics(out_dir / "ssfd_lightgbm_metrics.json", metrics, report, matrix, threshold)
    return {"model": "LightGBM", "threshold": threshold, **metrics}, val_pred, pd.read_csv(out_dir / "ssfd_lightgbm_test_predictions.csv")


def evaluate_adaboost(train_df: pd.DataFrame, val_df: pd.DataFrame, test_df: pd.DataFrame, out_dir: Path) -> tuple[dict[str, object], pd.DataFrame, pd.DataFrame]:
    train_encoded, val_encoded = encode_categorical_statistics(train_df, val_df)
    _, test_encoded = encode_categorical_statistics(train_df, test_df)

    X_train = train_encoded[SSFD_ADABOOST_FEATURES]
    y_train = train_encoded["Labels"].astype(int)
    X_val = val_encoded[SSFD_ADABOOST_FEATURES]
    y_val = val_encoded["Labels"].astype(int)
    X_test = test_encoded[SSFD_ADABOOST_FEATURES]
    y_test = test_encoded["Labels"].astype(int)

    neg = int((y_train == 0).sum())
    pos = int((y_train == 1).sum())
    sample_weight = np.where(y_train == 1, neg / max(pos, 1), 1.0)
    model = AdaBoostClassifier(
        estimator=DecisionTreeClassifier(max_depth=2, random_state=42),
        n_estimators=200,
        learning_rate=0.5,
        random_state=42,
    )
    model.fit(X_train, y_train, sample_weight=sample_weight)
    val_scores = model.predict_proba(X_val)[:, 1]
    threshold, _ = select_best_threshold(y_val.to_numpy(), val_scores)
    test_scores = model.predict_proba(X_test)[:, 1]
    metrics, report, matrix = compute_metrics(y_test.to_numpy(), test_scores, threshold)

    out_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"feature": SSFD_ADABOOST_FEATURES, "importance": model.feature_importances_}).sort_values(
        "importance", ascending=False
    ).to_csv(out_dir / "ssfd_adaboost_feature_importance.csv", index=False)
    val_pred = val_encoded.copy()
    val_pred["predicted_probability"] = val_scores
    val_pred["predicted_label"] = (val_scores >= threshold).astype(int)
    val_pred.to_csv(out_dir / "ssfd_adaboost_val_predictions.csv", index=False)
    save_predictions(out_dir / "ssfd_adaboost_test_predictions.csv", test_encoded, test_scores, threshold)
    save_metrics(out_dir / "ssfd_adaboost_metrics.json", metrics, report, matrix, threshold)
    return {"model": "AdaBoost", "threshold": threshold, **metrics}, val_pred, pd.read_csv(out_dir / "ssfd_adaboost_test_predictions.csv")


def evaluate_event_gnn(
    train_df: pd.DataFrame, val_df: pd.DataFrame, test_df: pd.DataFrame, unlabeled_df: pd.DataFrame, out_dir: Path
) -> tuple[dict[str, object], pd.DataFrame, pd.DataFrame]:
    full_df = pd.concat([unlabeled_df, train_df, val_df, test_df], ignore_index=True)
    full_df = full_df.sort_values("Time").reset_index(drop=True)
    full_df["event_id"] = np.arange(len(full_df))

    data, graph_df = build_event_graph_df(full_df)
    in_dims = {node_type: data[node_type].x.size(-1) for node_type in data.node_types}
    model = BaseHeteroClassifier(data.metadata(), in_dims, hidden_dim=96)
    model, summary = train_graph_model(data, model, epochs=60, lr=0.003)

    device = next(model.parameters()).device
    data = data.to(device)
    model.eval()
    with torch.no_grad():
        scores = torch.sigmoid(model(data.x_dict, data.edge_index_dict)).cpu().numpy()

    threshold = float(summary["best_threshold"])
    val_mask = data["event"].val_mask.cpu().numpy()
    test_mask = data["event"].test_mask.cpu().numpy()
    y_test = data["event"].y[data["event"].test_mask].cpu().numpy()
    test_scores = scores[test_mask]
    metrics, report, matrix = compute_metrics(y_test, test_scores, threshold)

    out_dir.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), out_dir / "ssfd_event_gnn_model.pt")
    val_pred = graph_df.loc[val_mask].copy()
    val_pred["predicted_probability"] = scores[val_mask]
    val_pred["predicted_label"] = (scores[val_mask] >= threshold).astype(int)
    val_pred.to_csv(out_dir / "ssfd_event_gnn_val_predictions.csv", index=False)
    save_predictions(out_dir / "ssfd_event_gnn_test_predictions.csv", graph_df.loc[test_mask].copy(), test_scores, threshold)
    save_metrics(out_dir / "ssfd_event_gnn_metrics.json", metrics, report, matrix, threshold, summary)
    return {"model": "Event-Based GNN", "threshold": threshold, **metrics}, val_pred, pd.read_csv(out_dir / "ssfd_event_gnn_test_predictions.csv")


def merge_prediction_frames(prediction_frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    key_cols = KEY_COLUMNS = ["Time", "Source", "Target", "Amount", "Location", "Type", "Labels"]
    merged = None
    for model_name, df in prediction_frames.items():
        use_df = df[key_cols + ["predicted_probability", "predicted_label"]].copy()
        use_df = use_df.rename(
            columns={
                "predicted_probability": f"{model_name}_probability",
                "predicted_label": f"{model_name}_label",
            }
        )
        merged = use_df if merged is None else merged.merge(use_df, on=key_cols, how="inner")
    return merged


def optimize_weights(base: pd.DataFrame) -> np.ndarray:
    y_true = base["Labels"].astype(int).to_numpy()

    def objective(weights: np.ndarray) -> float:
        scores = (
            base["event_gnn_probability"].to_numpy() * weights[0]
            + base["adaboost_probability"].to_numpy() * weights[1]
            + base["lightgbm_probability"].to_numpy() * weights[2]
        )
        return -float(average_precision_score(y_true, scores))

    constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]
    bounds = [(0.0, 1.0), (0.0, 1.0), (0.0, 1.0)]
    result = minimize(
        objective,
        x0=np.array([0.5, 0.3, 0.2], dtype=float),
        method="SLSQP",
        bounds=bounds,
        constraints=constraints,
        options={"maxiter": 500, "ftol": 1e-9},
    )
    if not result.success:
        raise RuntimeError(f"Weight optimization failed: {result.message}")
    return result.x


def combine(base: pd.DataFrame, weights: np.ndarray) -> np.ndarray:
    return (
        base["event_gnn_probability"].to_numpy() * weights[0]
        + base["adaboost_probability"].to_numpy() * weights[1]
        + base["lightgbm_probability"].to_numpy() * weights[2]
    )


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    train_df, val_df, test_df, unlabeled_df = build_split_frames()
    build_summary(train_df, val_df, test_df).to_csv(OUTPUT_DIR / "split_summary.csv", index=False)

    tree_train, tree_val, tree_test = prepare_tree_splits(train_df, val_df, test_df, unlabeled_df)

    lightgbm_result, lightgbm_val, lightgbm_test = evaluate_lightgbm(tree_train, tree_val, tree_test, OUTPUT_DIR / "lightgbm")
    adaboost_result, adaboost_val, adaboost_test = evaluate_adaboost(tree_train, tree_val, tree_test, OUTPUT_DIR / "adaboost")
    event_result, event_val, event_test = evaluate_event_gnn(train_df, val_df, test_df, unlabeled_df, OUTPUT_DIR / "event_gnn")

    val_base = merge_prediction_frames({"lightgbm": lightgbm_val, "adaboost": adaboost_val, "event_gnn": event_val})
    test_base = merge_prediction_frames({"lightgbm": lightgbm_test, "adaboost": adaboost_test, "event_gnn": event_test})

    optimized_weights = optimize_weights(val_base)
    val_scores = combine(val_base, optimized_weights)
    test_scores = combine(test_base, optimized_weights)
    threshold, _ = select_best_threshold(val_base["Labels"].astype(int).to_numpy(), val_scores)
    metrics, report, matrix = compute_metrics(test_base["Labels"].astype(int).to_numpy(), test_scores, threshold)

    weights_map = {
        "event_gnn": float(optimized_weights[0]),
        "adaboost": float(optimized_weights[1]),
        "lightgbm": float(optimized_weights[2]),
    }

    upgraded_pred = test_base.copy()
    upgraded_pred["ensemble_probability"] = test_scores
    upgraded_pred["predicted_label"] = (test_scores >= threshold).astype(int)
    upgraded_pred.to_csv(OUTPUT_DIR / "ssfd_validated_upgraded_ensemble_test_predictions.csv", index=False)

    with (OUTPUT_DIR / "ssfd_validated_upgraded_ensemble_metrics.json").open("w", encoding="utf-8") as fh:
        json.dump(
            {
                "metrics": metrics,
                "confusion_matrix": matrix.tolist(),
                "classification_report": report,
                "threshold_used": threshold,
                "weights": weights_map,
                "optimization_note": "Weights optimized on validation predictions only; final metrics evaluated on test only.",
            },
            fh,
            indent=2,
        )

    comparison_df = pd.DataFrame(
        [
            {"model": "LightGBM", "threshold": lightgbm_result["threshold"], **{k: lightgbm_result[k] for k in ["accuracy", "precision", "recall", "f1", "roc_auc", "average_precision"]}},
            {"model": "AdaBoost", "threshold": adaboost_result["threshold"], **{k: adaboost_result[k] for k in ["accuracy", "precision", "recall", "f1", "roc_auc", "average_precision"]}},
            {"model": "Event-Based GNN", "threshold": event_result["threshold"], **{k: event_result[k] for k in ["accuracy", "precision", "recall", "f1", "roc_auc", "average_precision"]}},
            {"model": "Validated Upgraded Ensemble", "threshold": threshold, **metrics},
        ]
    )
    comparison_df.to_csv(OUTPUT_DIR / "ssfd_validated_model_comparison.csv", index=False)

    print("Validated optimized weights:")
    for name, weight in weights_map.items():
        print(f"  {name}: {weight:.6f}")
    print()
    print_result({"model": "Validated Upgraded Ensemble", "threshold": threshold, **metrics})
    print("Validation-based S-FFSD Comparison Table")
    print(comparison_df.to_string(index=False))


if __name__ == "__main__":
    main()
