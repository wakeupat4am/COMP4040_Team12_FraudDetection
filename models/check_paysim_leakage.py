"""Diagnostics for leakage, shortcut learning, and overfitting risks on PaySim."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier
from sklearn.ensemble import AdaBoostClassifier
from sklearn.metrics import accuracy_score, average_precision_score, f1_score, precision_score, recall_score, roc_auc_score
from sklearn.tree import DecisionTreeClassifier

from train_paysim_four_models import TREE_FEATURES, load_saved_splits


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = PROJECT_ROOT / "models" / "paysim_leakage_diagnostics.json"


def metric_bundle(y_true: np.ndarray, y_score: np.ndarray, threshold: float = 0.5) -> dict[str, float]:
    y_pred = (y_score >= threshold).astype(int)
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
        "roc_auc": float(roc_auc_score(y_true, y_score)),
        "average_precision": float(average_precision_score(y_true, y_score)),
    }


def single_feature_diagnostics(test_df: pd.DataFrame) -> dict[str, dict[str, float]]:
    suspicious_features = [
        "org_balance_error_flag",
        "dest_balance_error_flag",
        "org_delta_minus_amount",
        "dest_delta_minus_amount",
        "type_CASH_OUT",
        "type_TRANSFER",
    ]
    y_true = test_df["isFraud"].to_numpy()
    summary: dict[str, dict[str, float]] = {}
    for feature in suspicious_features:
        values = test_df[feature].to_numpy(dtype=float)
        if np.all(values == values[0]):
            summary[feature] = {"roc_auc": float("nan"), "average_precision": float("nan")}
            continue
        summary[feature] = {
            "roc_auc": float(roc_auc_score(y_true, values)),
            "average_precision": float(average_precision_score(y_true, values)),
        }
    return summary


def run_shuffled_label_checks(train_df: pd.DataFrame, test_df: pd.DataFrame) -> dict[str, dict[str, float]]:
    rng = np.random.default_rng(42)
    X_train = train_df[TREE_FEATURES]
    X_test = test_df[TREE_FEATURES]
    y_train = train_df["isFraud"].to_numpy().copy()
    y_test = test_df["isFraud"].to_numpy()
    rng.shuffle(y_train)

    lightgbm = LGBMClassifier(
        objective="binary",
        n_estimators=200,
        learning_rate=0.05,
        num_leaves=63,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        n_jobs=-1,
    )
    lightgbm.fit(X_train, y_train)
    lgb_score = lightgbm.predict_proba(X_test)[:, 1]

    adaboost = AdaBoostClassifier(
        estimator=DecisionTreeClassifier(max_depth=2, random_state=42),
        n_estimators=100,
        learning_rate=0.5,
        random_state=42,
    )
    adaboost.fit(X_train, y_train)
    ada_score = adaboost.predict_proba(X_test)[:, 1]

    return {
        "lightgbm_shuffled_labels": metric_bundle(y_test, lgb_score),
        "adaboost_shuffled_labels": metric_bundle(y_test, ada_score),
    }


def graph_transductive_diagnostics(train_df: pd.DataFrame, val_df: pd.DataFrame, test_df: pd.DataFrame) -> dict[str, float]:
    train_orig = set(train_df["nameOrig"])
    train_dest = set(train_df["nameDest"])
    train_pairs = set(zip(train_df["nameOrig"], train_df["nameDest"]))

    test_orig_overlap = float(test_df["nameOrig"].isin(train_orig).mean())
    test_dest_overlap = float(test_df["nameDest"].isin(train_dest).mean())
    test_pair_overlap = float(pd.Series(list(zip(test_df["nameOrig"], test_df["nameDest"]))).isin(train_pairs).mean())

    val_orig_overlap = float(val_df["nameOrig"].isin(train_orig).mean())
    val_dest_overlap = float(val_df["nameDest"].isin(train_dest).mean())
    val_pair_overlap = float(pd.Series(list(zip(val_df["nameOrig"], val_df["nameDest"]))).isin(train_pairs).mean())

    return {
        "test_orig_seen_in_train_ratio": test_orig_overlap,
        "test_dest_seen_in_train_ratio": test_dest_overlap,
        "test_pair_seen_in_train_ratio": test_pair_overlap,
        "val_orig_seen_in_train_ratio": val_orig_overlap,
        "val_dest_seen_in_train_ratio": val_dest_overlap,
        "val_pair_seen_in_train_ratio": val_pair_overlap,
    }


def split_summary(train_df: pd.DataFrame, val_df: pd.DataFrame, test_df: pd.DataFrame) -> dict[str, object]:
    frames = {"train": train_df, "val": val_df, "test": test_df}
    summary = {}
    for name, df in frames.items():
        summary[name] = {
            "rows": int(len(df)),
            "fraud_count": int(df["isFraud"].sum()),
            "fraud_ratio": float(df["isFraud"].mean()),
            "step_min": int(df["step"].min()),
            "step_max": int(df["step"].max()),
        }
    return summary


def main() -> None:
    train_df, val_df, test_df = load_saved_splits()
    diagnostics = {
        "split_summary": split_summary(train_df, val_df, test_df),
        "single_feature_separability": single_feature_diagnostics(test_df),
        "shuffled_label_checks": run_shuffled_label_checks(train_df, test_df),
        "graph_transductive_overlap": graph_transductive_diagnostics(train_df, val_df, test_df),
        "notes": {
            "shortcut_signal": "If single-feature ROC-AUC or AP is near 1.0 for balance-error features, PaySim is likely easy because of simulator artifacts.",
            "shuffled_labels": "If shuffled-label models still score far above chance, suspect leakage in preprocessing or split logic.",
            "graph_overlap": "High overlap means the GNN is operating in a transductive setting where test nodes share entities with train nodes.",
        },
    }
    with OUTPUT_PATH.open("w", encoding="utf-8") as fh:
        json.dump(diagnostics, fh, indent=2)

    print("PaySim Leakage Diagnostics")
    print("=" * 25)
    print(json.dumps(diagnostics, indent=2))


if __name__ == "__main__":
    main()
