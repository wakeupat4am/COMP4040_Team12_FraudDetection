"""Train and evaluate an AdaBoost baseline on the processed S-FFSD splits."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import AdaBoostClassifier
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.tree import DecisionTreeClassifier


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
MODEL_OUTPUT_DIR = PROJECT_ROOT / "models" / "ssfd_adaboost"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--train-path",
        type=Path,
        default=PROCESSED_DIR / "ssfd_lightgbm_train.csv",
        help="Processed labeled training split.",
    )
    parser.add_argument(
        "--test-path",
        type=Path,
        default=PROCESSED_DIR / "ssfd_lightgbm_test.csv",
        help="Processed labeled test split.",
    )
    parser.add_argument(
        "--unlabeled-path",
        type=Path,
        default=PROCESSED_DIR / "ssfd_lightgbm_unlabeled.csv",
        help="Processed unlabeled split used only as optional feature context.",
    )
    parser.add_argument(
        "--use-unlabeled-context",
        action="store_true",
        help="Include unlabeled rows when building history-based features.",
    )
    return parser.parse_args()


def load_split(path: Path, split_name: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["split"] = split_name
    return df


def build_history_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values("Time").reset_index(drop=True).copy()
    df["row_id"] = np.arange(len(df))
    df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce")
    df["amount_log1p"] = np.log1p(df["Amount"].clip(lower=0))

    for col in ["Source", "Target", "Location", "Type"]:
        df[col] = df[col].astype("string")

    df["source_tx_count_so_far"] = df.groupby("Source").cumcount()
    df["target_tx_count_so_far"] = df.groupby("Target").cumcount()
    df["location_tx_count_so_far"] = df.groupby("Location").cumcount()
    df["type_tx_count_so_far"] = df.groupby("Type").cumcount()
    df["source_target_pair_count_so_far"] = df.groupby(["Source", "Target"]).cumcount()

    df["prev_time_by_source"] = df.groupby("Source")["Time"].shift(1)
    df["prev_time_by_target"] = df.groupby("Target")["Time"].shift(1)
    df["prev_time_by_pair"] = df.groupby(["Source", "Target"])["Time"].shift(1)
    df["source_time_gap"] = df["Time"] - df["prev_time_by_source"]
    df["target_time_gap"] = df["Time"] - df["prev_time_by_target"]
    df["pair_time_gap"] = df["Time"] - df["prev_time_by_pair"]

    source_amount_sum_before = df.groupby("Source")["Amount"].cumsum() - df["Amount"]
    target_amount_sum_before = df.groupby("Target")["Amount"].cumsum() - df["Amount"]
    pair_amount_sum_before = df.groupby(["Source", "Target"])["Amount"].cumsum() - df["Amount"]

    df["source_amount_mean_before"] = source_amount_sum_before.div(
        df["source_tx_count_so_far"].replace(0, np.nan)
    )
    df["target_amount_mean_before"] = target_amount_sum_before.div(
        df["target_tx_count_so_far"].replace(0, np.nan)
    )
    df["pair_amount_mean_before"] = pair_amount_sum_before.div(
        df["source_target_pair_count_so_far"].replace(0, np.nan)
    )

    df["amount_vs_source_mean"] = df["Amount"] - df["source_amount_mean_before"]
    df["amount_vs_target_mean"] = df["Amount"] - df["target_amount_mean_before"]
    df["amount_vs_pair_mean"] = df["Amount"] - df["pair_amount_mean_before"]

    df["source_seen_target_before"] = (
        df.groupby(["Source", "Target"]).cumcount().gt(0).astype(int)
    )
    df["source_seen_location_before"] = (
        df.groupby(["Source", "Location"]).cumcount().gt(0).astype(int)
    )
    df["source_seen_type_before"] = (
        df.groupby(["Source", "Type"]).cumcount().gt(0).astype(int)
    )

    fill_zero_cols = [
        "source_time_gap",
        "target_time_gap",
        "pair_time_gap",
        "source_amount_mean_before",
        "target_amount_mean_before",
        "pair_amount_mean_before",
        "amount_vs_source_mean",
        "amount_vs_target_mean",
        "amount_vs_pair_mean",
    ]
    df[fill_zero_cols] = df[fill_zero_cols].fillna(0)
    return df


def prepare_datasets(
    train_df: pd.DataFrame, test_df: pd.DataFrame, unlabeled_df: pd.DataFrame | None
) -> tuple[pd.DataFrame, pd.DataFrame]:
    frames = [train_df, test_df]
    if unlabeled_df is not None:
        frames.insert(0, unlabeled_df)

    combined = pd.concat(frames, ignore_index=True)
    combined = build_history_features(combined)
    train_featured = combined[combined["split"] == "train"].copy()
    test_featured = combined[combined["split"] == "test"].copy()
    return train_featured, test_featured


def encode_categorical_statistics(
    train_df: pd.DataFrame, test_df: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    encoded_train = train_df.copy()
    encoded_test = test_df.copy()

    for col in ["Source", "Target", "Location", "Type"]:
        frequency_map = train_df[col].value_counts(normalize=True).to_dict()
        count_map = train_df[col].value_counts().to_dict()

        encoded_train[f"{col.lower()}_freq"] = train_df[col].map(frequency_map).fillna(0.0)
        encoded_test[f"{col.lower()}_freq"] = test_df[col].map(frequency_map).fillna(0.0)
        encoded_train[f"{col.lower()}_count"] = train_df[col].map(count_map).fillna(0.0)
        encoded_test[f"{col.lower()}_count"] = test_df[col].map(count_map).fillna(0.0)

    return encoded_train, encoded_test


def train_model(train_df: pd.DataFrame) -> tuple[AdaBoostClassifier, list[str]]:
    feature_columns = [
        "Time",
        "Amount",
        "amount_log1p",
        "source_tx_count_so_far",
        "target_tx_count_so_far",
        "location_tx_count_so_far",
        "type_tx_count_so_far",
        "source_target_pair_count_so_far",
        "source_time_gap",
        "target_time_gap",
        "pair_time_gap",
        "source_amount_mean_before",
        "target_amount_mean_before",
        "pair_amount_mean_before",
        "amount_vs_source_mean",
        "amount_vs_target_mean",
        "amount_vs_pair_mean",
        "source_seen_target_before",
        "source_seen_location_before",
        "source_seen_type_before",
        "source_freq",
        "source_count",
        "target_freq",
        "target_count",
        "location_freq",
        "location_count",
        "type_freq",
        "type_count",
    ]

    X_train = train_df[feature_columns].copy()
    y_train = train_df["Labels"].astype(int)

    negative_count = int((y_train == 0).sum())
    positive_count = int((y_train == 1).sum())
    sample_weight = np.where(y_train == 1, negative_count / positive_count, 1.0)

    base_estimator = DecisionTreeClassifier(max_depth=2, random_state=42)
    model = AdaBoostClassifier(
        estimator=base_estimator,
        n_estimators=200,
        learning_rate=0.5,
        random_state=42,
    )
    model.fit(X_train, y_train, sample_weight=sample_weight)
    return model, feature_columns


def evaluate_model(
    model: AdaBoostClassifier, test_df: pd.DataFrame, feature_columns: list[str]
) -> tuple[dict[str, float], pd.DataFrame, str, np.ndarray]:
    X_test = test_df[feature_columns].copy()
    y_true = test_df["Labels"].astype(int)
    y_score = model.predict_proba(X_test)[:, 1]
    y_pred = (y_score >= 0.5).astype(int)

    metrics = {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
        "roc_auc": float(roc_auc_score(y_true, y_score)),
        "average_precision": float(average_precision_score(y_true, y_score)),
    }

    report = classification_report(y_true, y_pred, digits=4)
    matrix = confusion_matrix(y_true, y_pred)

    predictions = test_df[["Time", "Source", "Target", "Amount", "Location", "Type", "Labels"]].copy()
    predictions["predicted_probability"] = y_score
    predictions["predicted_label"] = y_pred
    return metrics, predictions, report, matrix


def save_outputs(
    model: AdaBoostClassifier,
    metrics: dict[str, float],
    predictions: pd.DataFrame,
    report: str,
    matrix: np.ndarray,
    feature_columns: list[str],
) -> None:
    MODEL_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    predictions.to_csv(MODEL_OUTPUT_DIR / "ssfd_adaboost_test_predictions.csv", index=False)

    feature_importance = pd.DataFrame(
        {
            "feature": feature_columns,
            "importance": model.feature_importances_,
        }
    ).sort_values("importance", ascending=False)
    feature_importance.to_csv(MODEL_OUTPUT_DIR / "ssfd_adaboost_feature_importance.csv", index=False)

    metrics_payload = {
        "metrics": metrics,
        "confusion_matrix": matrix.tolist(),
        "classification_report": report,
    }
    with (MODEL_OUTPUT_DIR / "ssfd_adaboost_metrics.json").open("w", encoding="utf-8") as fh:
        json.dump(metrics_payload, fh, indent=2)


def print_summary(metrics: dict[str, float], report: str, matrix: np.ndarray) -> None:
    print("AdaBoost Evaluation Summary")
    print("=" * 31)
    for key, value in metrics.items():
        print(f"{key:>18}: {value:.6f}")
    print("\nConfusion Matrix")
    print(matrix)
    print("\nClassification Report")
    print(report)


def main() -> None:
    args = parse_args()
    train_df = load_split(args.train_path, "train")
    test_df = load_split(args.test_path, "test")
    unlabeled_df = load_split(args.unlabeled_path, "unlabeled") if args.use_unlabeled_context else None

    train_featured, test_featured = prepare_datasets(train_df, test_df, unlabeled_df)
    train_encoded, test_encoded = encode_categorical_statistics(train_featured, test_featured)

    model, feature_columns = train_model(train_encoded)
    metrics, predictions, report, matrix = evaluate_model(model, test_encoded, feature_columns)
    save_outputs(model, metrics, predictions, report, matrix, feature_columns)
    print_summary(metrics, report, matrix)


if __name__ == "__main__":
    main()
