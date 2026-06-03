"""Train four baseline models on a PaySim temporal slice and compare results."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F
from lightgbm import LGBMClassifier
from sklearn.ensemble import AdaBoostClassifier
from sklearn.linear_model import LogisticRegression
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
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier
from torch import Tensor, nn
from torch_geometric.data import HeteroData
from torch_geometric.nn import HeteroConv, SAGEConv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INTERIM_PATH = PROJECT_ROOT / "data" / "interim" / "paysim_ready_features.csv"
OUTPUT_DIR = PROJECT_ROOT / "models" / "paysim_comparison"

TRAIN_START, TRAIN_END = 500, 649
VAL_START, VAL_END = 650, 699
TEST_START, TEST_END = 700, 743
VALID_TYPES = {"CASH_OUT", "TRANSFER"}

DEFAULT_SPLIT_CONFIG = {
    "train": (TRAIN_START, TRAIN_END),
    "val": (VAL_START, VAL_END),
    "test": (TEST_START, TEST_END),
    "valid_types": VALID_TYPES,
}


def compute_metrics(y_true: np.ndarray, y_score: np.ndarray, threshold: float) -> tuple[dict[str, float], str, np.ndarray]:
    y_pred = (y_score >= threshold).astype(int)
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
    return metrics, report, matrix


def select_best_threshold(y_true: np.ndarray, y_score: np.ndarray) -> tuple[float, dict[str, float]]:
    best_threshold = 0.5
    best_metrics = {}
    best_f1 = -1.0
    roc_auc = float(roc_auc_score(y_true, y_score))
    average_precision = float(average_precision_score(y_true, y_score))
    for threshold in np.linspace(0.05, 0.95, 37):
        y_pred = (y_score >= float(threshold)).astype(int)
        metrics = {
            "accuracy": float(accuracy_score(y_true, y_pred)),
            "precision": float(precision_score(y_true, y_pred, zero_division=0)),
            "recall": float(recall_score(y_true, y_pred, zero_division=0)),
            "f1": float(f1_score(y_true, y_pred, zero_division=0)),
            "roc_auc": roc_auc,
            "average_precision": average_precision,
        }
        if metrics["f1"] > best_f1:
            best_f1 = metrics["f1"]
            best_threshold = float(threshold)
            best_metrics = metrics
    return best_threshold, best_metrics


def split_bounds(split_config: dict[str, Any] | None = None) -> tuple[tuple[int, int], tuple[int, int], tuple[int, int], set[str]]:
    config = split_config or DEFAULT_SPLIT_CONFIG
    train_bounds = tuple(config["train"])
    val_bounds = tuple(config["val"])
    test_bounds = tuple(config["test"])
    valid_types = set(config.get("valid_types", VALID_TYPES))
    return train_bounds, val_bounds, test_bounds, valid_types


def assign_split_column(df: pd.DataFrame, train_df: pd.DataFrame, val_df: pd.DataFrame, test_df: pd.DataFrame) -> pd.DataFrame:
    frame = pd.concat(
        [
            train_df.assign(split="train"),
            val_df.assign(split="val"),
            test_df.assign(split="test"),
        ],
        ignore_index=True,
    )
    frame = frame.sort_values("step").reset_index(drop=True)
    frame["event_id"] = np.arange(len(frame))
    return frame


def save_split_bundle(train_df: pd.DataFrame, val_df: pd.DataFrame, test_df: pd.DataFrame, prefix: str) -> None:
    processed_dir = PROJECT_ROOT / "data" / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)
    train_df.to_csv(processed_dir / f"{prefix}_train.csv", index=False)
    val_df.to_csv(processed_dir / f"{prefix}_val.csv", index=False)
    test_df.to_csv(processed_dir / f"{prefix}_test.csv", index=False)
    summary = pd.DataFrame(
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
    summary.to_csv(processed_dir / f"{prefix}_split_summary.csv", index=False)


def load_subset(split_config: dict[str, Any] | None = None) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    usecols = [
        "step",
        "type",
        "amount",
        "amount_log1p",
        "nameOrig",
        "nameDest",
        "oldbalanceOrg",
        "newbalanceOrig",
        "oldbalanceDest",
        "newbalanceDest",
        "org_balance_delta",
        "dest_balance_delta",
        "org_delta_minus_amount",
        "dest_delta_minus_amount",
        "org_zero_before",
        "org_zero_after",
        "dest_zero_before",
        "dest_zero_after",
        "org_balance_error_flag",
        "dest_balance_error_flag",
        "orig_tx_count_so_far",
        "dest_tx_count_so_far",
        "orig_dest_pair_count_so_far",
        "orig_step_gap",
        "dest_step_gap",
        "pair_step_gap",
        "orig_amount_mean_before",
        "dest_amount_mean_before",
        "amount_vs_orig_mean",
        "amount_vs_dest_mean",
        "isFraud",
        "type_CASH_IN",
        "type_CASH_OUT",
        "type_DEBIT",
        "type_PAYMENT",
        "type_TRANSFER",
    ]
    train_bounds, val_bounds, test_bounds, valid_types = split_bounds(split_config)
    global_min = min(train_bounds[0], val_bounds[0], test_bounds[0])
    global_max = max(train_bounds[1], val_bounds[1], test_bounds[1])

    df = pd.read_csv(INTERIM_PATH, usecols=usecols)
    df = df[df["type"].isin(valid_types) & df["step"].between(global_min, global_max)].copy()
    df = df.sort_values("step").reset_index(drop=True)
    train_df = df[df["step"].between(*train_bounds)].copy()
    val_df = df[df["step"].between(*val_bounds)].copy()
    test_df = df[df["step"].between(*test_bounds)].copy()
    return train_df, val_df, test_df


def load_saved_splits(prefix: str = "paysim_model") -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    processed_dir = PROJECT_ROOT / "data" / "processed"
    train_df = pd.read_csv(processed_dir / f"{prefix}_train.csv")
    val_df = pd.read_csv(processed_dir / f"{prefix}_val.csv")
    test_df = pd.read_csv(processed_dir / f"{prefix}_test.csv")
    return train_df, val_df, test_df


TREE_FEATURES = [
    "amount",
    "amount_log1p",
    "oldbalanceOrg",
    "newbalanceOrig",
    "oldbalanceDest",
    "newbalanceDest",
    "org_balance_delta",
    "dest_balance_delta",
    "org_delta_minus_amount",
    "dest_delta_minus_amount",
    "org_zero_before",
    "org_zero_after",
    "dest_zero_before",
    "dest_zero_after",
    "org_balance_error_flag",
    "dest_balance_error_flag",
    "orig_tx_count_so_far",
    "dest_tx_count_so_far",
    "orig_dest_pair_count_so_far",
    "orig_step_gap",
    "dest_step_gap",
    "pair_step_gap",
    "orig_amount_mean_before",
    "dest_amount_mean_before",
    "amount_vs_orig_mean",
    "amount_vs_dest_mean",
    "type_CASH_OUT",
    "type_TRANSFER",
]

LOGISTIC_FEATURES = TREE_FEATURES


def train_lightgbm(
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    test_df: pd.DataFrame,
    out_dir: Path,
    fraud_weight_multiplier: float = 1.0,
) -> dict[str, object]:
    X_train = train_df[TREE_FEATURES]
    y_train = train_df["isFraud"].astype(int)
    X_val = val_df[TREE_FEATURES]
    y_val = val_df["isFraud"].astype(int)
    X_test = test_df[TREE_FEATURES]
    y_test = test_df["isFraud"].astype(int)

    neg = int((y_train == 0).sum())
    pos = int((y_train == 1).sum())
    model = LGBMClassifier(
        objective="binary",
        n_estimators=400,
        learning_rate=0.05,
        num_leaves=63,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        scale_pos_weight=(neg / max(pos, 1)) * fraud_weight_multiplier,
        n_jobs=-1,
    )
    model.fit(X_train, y_train)
    val_scores = model.predict_proba(X_val)[:, 1]
    threshold, _ = select_best_threshold(y_val.to_numpy(), val_scores)
    test_scores = model.predict_proba(X_test)[:, 1]
    metrics, report, matrix = compute_metrics(y_test.to_numpy(), test_scores, threshold)

    out_dir.mkdir(parents=True, exist_ok=True)
    model.booster_.save_model(str(out_dir / "model.txt"))
    pd.DataFrame({"feature": TREE_FEATURES, "importance": model.feature_importances_}).sort_values(
        "importance", ascending=False
    ).to_csv(out_dir / "feature_importance.csv", index=False)
    save_predictions(out_dir / "test_predictions.csv", test_df, test_scores, threshold)
    save_metrics(out_dir / "metrics.json", metrics, report, matrix, threshold)
    return {"model": "LightGBM", "threshold": threshold, **metrics}


def train_adaboost(
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    test_df: pd.DataFrame,
    out_dir: Path,
    fraud_weight_multiplier: float = 1.0,
) -> dict[str, object]:
    X_train = train_df[TREE_FEATURES]
    y_train = train_df["isFraud"].astype(int)
    X_val = val_df[TREE_FEATURES]
    y_val = val_df["isFraud"].astype(int)
    X_test = test_df[TREE_FEATURES]
    y_test = test_df["isFraud"].astype(int)

    neg = int((y_train == 0).sum())
    pos = int((y_train == 1).sum())
    sample_weight = np.where(y_train == 1, (neg / max(pos, 1)) * fraud_weight_multiplier, 1.0)

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
    pd.DataFrame({"feature": TREE_FEATURES, "importance": model.feature_importances_}).sort_values(
        "importance", ascending=False
    ).to_csv(out_dir / "feature_importance.csv", index=False)
    save_predictions(out_dir / "test_predictions.csv", test_df, test_scores, threshold)
    save_metrics(out_dir / "metrics.json", metrics, report, matrix, threshold)
    return {"model": "AdaBoost", "threshold": threshold, **metrics}


def train_logistic_regression(
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    test_df: pd.DataFrame,
    out_dir: Path,
    fraud_weight_multiplier: float = 1.0,
) -> dict[str, object]:
    X_train = train_df[LOGISTIC_FEATURES]
    y_train = train_df["isFraud"].astype(int)
    X_val = val_df[LOGISTIC_FEATURES]
    y_val = val_df["isFraud"].astype(int)
    X_test = test_df[LOGISTIC_FEATURES]
    y_test = test_df["isFraud"].astype(int)

    neg = int((y_train == 0).sum())
    pos = int((y_train == 1).sum())
    class_weight = {0: 1.0, 1: (neg / max(pos, 1)) * fraud_weight_multiplier}

    model = Pipeline(
        [
            ("scaler", StandardScaler()),
            (
                "classifier",
                LogisticRegression(
                    C=1.0,
                    class_weight=class_weight,
                    max_iter=3000,
                    solver="lbfgs",
                    random_state=42,
                ),
            ),
        ]
    )
    model.fit(X_train, y_train)
    val_scores = model.predict_proba(X_val)[:, 1]
    threshold, _ = select_best_threshold(y_val.to_numpy(), val_scores)
    test_scores = model.predict_proba(X_test)[:, 1]
    metrics, report, matrix = compute_metrics(y_test.to_numpy(), test_scores, threshold)

    out_dir.mkdir(parents=True, exist_ok=True)
    classifier = model.named_steps["classifier"]
    pd.DataFrame(
        {
            "feature": LOGISTIC_FEATURES,
            "coefficient": classifier.coef_[0],
            "abs_coefficient": np.abs(classifier.coef_[0]),
        }
    ).sort_values("abs_coefficient", ascending=False).to_csv(out_dir / "coefficients.csv", index=False)
    save_predictions(out_dir / "test_predictions.csv", test_df, test_scores, threshold)
    save_metrics(out_dir / "metrics.json", metrics, report, matrix, threshold)
    return {"model": "Logistic Regression", "threshold": threshold, **metrics}


def build_paysim_graph_frames(split_config: dict[str, Any] | None = None) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    usecols = [
        "step",
        "type",
        "amount",
        "amount_log1p",
        "nameOrig",
        "nameDest",
        "oldbalanceOrg",
        "newbalanceOrig",
        "oldbalanceDest",
        "newbalanceDest",
        "org_balance_delta",
        "dest_balance_delta",
        "org_delta_minus_amount",
        "dest_delta_minus_amount",
        "org_zero_before",
        "org_zero_after",
        "dest_zero_before",
        "dest_zero_after",
        "org_balance_error_flag",
        "dest_balance_error_flag",
        "orig_tx_count_so_far",
        "dest_tx_count_so_far",
        "orig_dest_pair_count_so_far",
        "orig_step_gap",
        "dest_step_gap",
        "pair_step_gap",
        "orig_amount_mean_before",
        "dest_amount_mean_before",
        "amount_vs_orig_mean",
        "amount_vs_dest_mean",
        "isFraud",
    ]
    train_df, val_df, test_df = load_subset(split_config)
    df = assign_split_column(pd.DataFrame(), train_df, val_df, test_df)
    return df, df[df["split"] == "train"].copy(), df[df["split"] == "val"].copy(), df[df["split"] == "test"].copy()


def build_graph_df_from_splits(train_df: pd.DataFrame, val_df: pd.DataFrame, test_df: pd.DataFrame) -> pd.DataFrame:
    return assign_split_column(pd.DataFrame(), train_df, val_df, test_df)


class PaySimHeteroGNN(nn.Module):
    def __init__(self, metadata: tuple[list[str], list[tuple[str, str, str]]], in_dims: dict[str, int], hidden_dim: int = 64):
        super().__init__()
        self.node_key = {node_type: f"{node_type}_node" for node_type in in_dims}
        self.proj = nn.ModuleDict(
            {self.node_key[node_type]: nn.Linear(in_dim, hidden_dim) for node_type, in_dim in in_dims.items()}
        )
        self.conv1 = HeteroConv({edge_type: SAGEConv((-1, -1), hidden_dim) for edge_type in metadata[1]}, aggr="sum")
        self.conv2 = HeteroConv({edge_type: SAGEConv((-1, -1), hidden_dim) for edge_type in metadata[1]}, aggr="sum")
        self.norm1 = nn.ModuleDict({self.node_key[k]: nn.LayerNorm(hidden_dim) for k in in_dims})
        self.norm2 = nn.ModuleDict({self.node_key[k]: nn.LayerNorm(hidden_dim) for k in in_dims})
        self.classifier = nn.Linear(hidden_dim, 1)

    def forward(self, x_dict: dict[str, Tensor], edge_index_dict: dict[tuple[str, str, str], Tensor]) -> Tensor:
        x_dict = {k: F.relu(self.proj[self.node_key[k]](x)) for k, x in x_dict.items()}
        x_dict = self.conv1(x_dict, edge_index_dict)
        x_dict = {k: F.relu(self.norm1[self.node_key[k]](x)) for k, x in x_dict.items()}
        x_dict = {k: F.dropout(v, p=0.2, training=self.training) for k, v in x_dict.items()}
        x_dict = self.conv2(x_dict, edge_index_dict)
        x_dict = {k: F.relu(self.norm2[self.node_key[k]](x)) for k, x in x_dict.items()}
        return self.classifier(x_dict["event"]).squeeze(-1)


def build_hetero_data(df: pd.DataFrame) -> HeteroData:
    data = HeteroData()
    event_features = torch.tensor(
        df[
            [
                "amount",
                "amount_log1p",
                "step",
                "oldbalanceOrg",
                "newbalanceOrig",
                "oldbalanceDest",
                "newbalanceDest",
                "org_balance_delta",
                "dest_balance_delta",
                "org_delta_minus_amount",
                "dest_delta_minus_amount",
                "orig_tx_count_so_far",
                "dest_tx_count_so_far",
                "orig_dest_pair_count_so_far",
                "orig_step_gap",
                "dest_step_gap",
                "pair_step_gap",
                "orig_amount_mean_before",
                "dest_amount_mean_before",
                "amount_vs_orig_mean",
                "amount_vs_dest_mean",
            ]
        ].to_numpy(dtype=np.float32),
        dtype=torch.float32,
    )
    step_max = max(float(df["step"].max()), 1.0)
    event_features[:, 2] = event_features[:, 2] / step_max
    data["event"].x = event_features
    data["event"].y = torch.tensor(df["isFraud"].to_numpy(), dtype=torch.long)
    if "split" in df.columns:
        data["event"].train_mask = torch.tensor((df["split"] == "train").to_numpy(), dtype=torch.bool)
        data["event"].val_mask = torch.tensor((df["split"] == "val").to_numpy(), dtype=torch.bool)
        data["event"].test_mask = torch.tensor((df["split"] == "test").to_numpy(), dtype=torch.bool)
    else:
        data["event"].train_mask = torch.tensor(df["step"].between(TRAIN_START, TRAIN_END).to_numpy(), dtype=torch.bool)
        data["event"].val_mask = torch.tensor(df["step"].between(VAL_START, VAL_END).to_numpy(), dtype=torch.bool)
        data["event"].test_mask = torch.tensor(df["step"].between(TEST_START, TEST_END).to_numpy(), dtype=torch.bool)

    orig_map = {v: i for i, v in enumerate(sorted(df["nameOrig"].astype(str).unique()))}
    dest_map = {v: i for i, v in enumerate(sorted(df["nameDest"].astype(str).unique()))}
    type_map = {v: i for i, v in enumerate(sorted(df["type"].astype(str).unique()))}

    def entity_stats(col: str, other: str) -> pd.DataFrame:
        return (
            df.groupby(col)
            .agg(
                degree=("event_id", "size"),
                mean_amount=("amount", "mean"),
                std_amount=("amount", "std"),
                unique_other=(other, "nunique"),
            )
            .fillna(0)
        )

    orig_stats = entity_stats("nameOrig", "nameDest")
    dest_stats = entity_stats("nameDest", "nameOrig")
    type_stats = (
        df.groupby("type")
        .agg(
            degree=("event_id", "size"),
            mean_amount=("amount", "mean"),
            std_amount=("amount", "std"),
            fraud_rate=("isFraud", "mean"),
        )
        .fillna(0)
    )

    data["orig"].x = torch.tensor(
        np.vstack([orig_stats.loc[k].to_numpy(dtype=np.float32) for k, _ in sorted(orig_map.items(), key=lambda x: x[1])]),
        dtype=torch.float32,
    )
    data["dest"].x = torch.tensor(
        np.vstack([dest_stats.loc[k].to_numpy(dtype=np.float32) for k, _ in sorted(dest_map.items(), key=lambda x: x[1])]),
        dtype=torch.float32,
    )
    data["type"].x = torch.tensor(
        np.vstack([type_stats.loc[k].to_numpy(dtype=np.float32) for k, _ in sorted(type_map.items(), key=lambda x: x[1])]),
        dtype=torch.float32,
    )

    event_ids = torch.tensor(df["event_id"].to_numpy(), dtype=torch.long)
    orig_ids = torch.tensor(df["nameOrig"].astype(str).map(orig_map).to_numpy(), dtype=torch.long)
    dest_ids = torch.tensor(df["nameDest"].astype(str).map(dest_map).to_numpy(), dtype=torch.long)
    type_ids = torch.tensor(df["type"].astype(str).map(type_map).to_numpy(), dtype=torch.long)

    relations = {
        ("event", "from_orig", "orig"): torch.stack([event_ids, orig_ids]),
        ("orig", "rev_from_orig", "event"): torch.stack([orig_ids, event_ids]),
        ("event", "to_dest", "dest"): torch.stack([event_ids, dest_ids]),
        ("dest", "rev_to_dest", "event"): torch.stack([dest_ids, event_ids]),
        ("event", "has_type", "type"): torch.stack([event_ids, type_ids]),
        ("type", "rev_has_type", "event"): torch.stack([type_ids, event_ids]),
        ("orig", "to_dest", "dest"): torch.stack([orig_ids, dest_ids]),
        ("dest", "rev_to_dest_orig", "orig"): torch.stack([dest_ids, orig_ids]),
    }
    for edge_type, edge_index in relations.items():
        data[edge_type].edge_index = edge_index
    return data


class PaySimEventGNN(PaySimHeteroGNN):
    pass


def build_event_data(df: pd.DataFrame) -> HeteroData:
    data = HeteroData()
    event_features = torch.tensor(
        df[
            [
                "amount",
                "amount_log1p",
                "step",
                "oldbalanceOrg",
                "newbalanceOrig",
                "oldbalanceDest",
                "newbalanceDest",
                "org_balance_delta",
                "dest_balance_delta",
                "org_delta_minus_amount",
                "dest_delta_minus_amount",
                "orig_tx_count_so_far",
                "dest_tx_count_so_far",
                "orig_dest_pair_count_so_far",
                "orig_step_gap",
                "dest_step_gap",
                "pair_step_gap",
                "orig_amount_mean_before",
                "dest_amount_mean_before",
                "amount_vs_orig_mean",
                "amount_vs_dest_mean",
            ]
        ].to_numpy(dtype=np.float32),
        dtype=torch.float32,
    )
    step_max = max(float(df["step"].max()), 1.0)
    event_features[:, 2] = event_features[:, 2] / step_max
    data["event"].x = event_features
    data["event"].y = torch.tensor(df["isFraud"].to_numpy(), dtype=torch.long)
    if "split" in df.columns:
        data["event"].train_mask = torch.tensor((df["split"] == "train").to_numpy(), dtype=torch.bool)
        data["event"].val_mask = torch.tensor((df["split"] == "val").to_numpy(), dtype=torch.bool)
        data["event"].test_mask = torch.tensor((df["split"] == "test").to_numpy(), dtype=torch.bool)
    else:
        data["event"].train_mask = torch.tensor(df["step"].between(TRAIN_START, TRAIN_END).to_numpy(), dtype=torch.bool)
        data["event"].val_mask = torch.tensor(df["step"].between(VAL_START, VAL_END).to_numpy(), dtype=torch.bool)
        data["event"].test_mask = torch.tensor(df["step"].between(TEST_START, TEST_END).to_numpy(), dtype=torch.bool)

    orig_map = {v: i for i, v in enumerate(sorted(df["nameOrig"].astype(str).unique()))}
    dest_map = {v: i for i, v in enumerate(sorted(df["nameDest"].astype(str).unique()))}
    orig_stats = (
        df.groupby("nameOrig")
        .agg(degree=("event_id", "size"), mean_amount=("amount", "mean"), std_amount=("amount", "std"), unique_dest=("nameDest", "nunique"))
        .fillna(0)
    )
    dest_stats = (
        df.groupby("nameDest")
        .agg(degree=("event_id", "size"), mean_amount=("amount", "mean"), std_amount=("amount", "std"), unique_orig=("nameOrig", "nunique"))
        .fillna(0)
    )
    data["orig"].x = torch.tensor(
        np.vstack([orig_stats.loc[k].to_numpy(dtype=np.float32) for k, _ in sorted(orig_map.items(), key=lambda x: x[1])]),
        dtype=torch.float32,
    )
    data["dest"].x = torch.tensor(
        np.vstack([dest_stats.loc[k].to_numpy(dtype=np.float32) for k, _ in sorted(dest_map.items(), key=lambda x: x[1])]),
        dtype=torch.float32,
    )
    event_ids = torch.tensor(df["event_id"].to_numpy(), dtype=torch.long)
    orig_ids = torch.tensor(df["nameOrig"].astype(str).map(orig_map).to_numpy(), dtype=torch.long)
    dest_ids = torch.tensor(df["nameDest"].astype(str).map(dest_map).to_numpy(), dtype=torch.long)
    seq_src = torch.arange(0, len(df) - 1, dtype=torch.long)
    seq_dst = torch.arange(1, len(df), dtype=torch.long)

    def group_edges(col: str) -> torch.Tensor:
        src, dst = [], []
        for _, g in df.groupby(col, sort=False):
            ids = g["event_id"].to_numpy()
            if len(ids) < 2:
                continue
            src.extend(ids[:-1].tolist())
            dst.extend(ids[1:].tolist())
        return torch.tensor([src, dst], dtype=torch.long) if src else torch.empty((2, 0), dtype=torch.long)

    relations = {
        ("event", "next_event", "event"): torch.stack([seq_src, seq_dst]),
        ("event", "prev_event", "event"): torch.stack([seq_dst, seq_src]),
        ("event", "next_same_orig", "event"): group_edges("nameOrig"),
        ("event", "prev_same_orig", "event"): group_edges("nameOrig").flip(0),
        ("event", "next_same_dest", "event"): group_edges("nameDest"),
        ("event", "prev_same_dest", "event"): group_edges("nameDest").flip(0),
        ("event", "from_orig", "orig"): torch.stack([event_ids, orig_ids]),
        ("orig", "rev_from_orig", "event"): torch.stack([orig_ids, event_ids]),
        ("event", "to_dest", "dest"): torch.stack([event_ids, dest_ids]),
        ("dest", "rev_to_dest", "event"): torch.stack([dest_ids, event_ids]),
    }
    for edge_type, edge_index in relations.items():
        data[edge_type].edge_index = edge_index
    return data


def train_graph_model(
    data: HeteroData,
    model: nn.Module,
    epochs: int = 30,
    lr: float = 0.003,
    fraud_weight_multiplier: float = 1.0,
) -> tuple[nn.Module, dict[str, object]]:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    data = data.to(device)
    model = model.to(device)
    train_mask = data["event"].train_mask
    val_mask = data["event"].val_mask
    y_train = data["event"].y[train_mask]
    neg = int((y_train == 0).sum().item())
    pos = int((y_train == 1).sum().item())
    pos_weight = torch.tensor([(neg / max(pos, 1)) * fraud_weight_multiplier], device=device)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode="max", factor=0.5, patience=4, min_lr=1e-4)

    best_state = None
    best_ap = -1.0
    best_threshold = 0.5
    history = []
    for epoch in range(1, epochs + 1):
        model.train()
        optimizer.zero_grad()
        logits = model(data.x_dict, data.edge_index_dict)
        loss = F.binary_cross_entropy_with_logits(logits[train_mask], data["event"].y[train_mask].float(), pos_weight=pos_weight)
        loss.backward()
        optimizer.step()

        model.eval()
        with torch.no_grad():
            val_scores = torch.sigmoid(model(data.x_dict, data.edge_index_dict)[val_mask]).cpu().numpy()
            val_true = data["event"].y[val_mask].cpu().numpy()
            val_ap = float(average_precision_score(val_true, val_scores))
            threshold, best_metrics = select_best_threshold(val_true, val_scores)
            history.append({"epoch": epoch, "train_loss": float(loss.item()), "val_average_precision": val_ap, "val_best_threshold": threshold, "val_best_f1": float(best_metrics["f1"])})
            if val_ap > best_ap:
                best_ap = val_ap
                best_threshold = threshold
                best_state = deepcopy(model.state_dict())
        scheduler.step(val_ap)
    if best_state is not None:
        model.load_state_dict(best_state)
    return model, {"best_val_average_precision": best_ap, "best_threshold": best_threshold, "history": history}


def evaluate_graph_model(model_name: str, model: nn.Module, data: HeteroData, df: pd.DataFrame, training_summary: dict[str, object], out_dir: Path) -> dict[str, object]:
    device = next(model.parameters()).device
    data = data.to(device)
    model.eval()
    with torch.no_grad():
        scores = torch.sigmoid(model(data.x_dict, data.edge_index_dict)).cpu().numpy()
    test_mask = data["event"].test_mask.cpu().numpy()
    y_true = data["event"].y[data["event"].test_mask].cpu().numpy()
    y_score = scores[test_mask]
    threshold = float(training_summary["best_threshold"])
    metrics, report, matrix = compute_metrics(y_true, y_score, threshold)
    out_dir.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), out_dir / "model.pt")
    save_predictions(out_dir / "test_predictions.csv", df.loc[test_mask].copy(), y_score, threshold, label_col="isFraud")
    save_metrics(out_dir / "metrics.json", metrics, report, matrix, threshold, training_summary)
    return {"model": model_name, "threshold": threshold, **metrics}


def save_predictions(path: Path, df: pd.DataFrame, scores: np.ndarray, threshold: float, label_col: str = "isFraud") -> None:
    cols = [c for c in ["step", "type", "amount", "nameOrig", "nameDest", label_col] if c in df.columns]
    out = df[cols].copy()
    out["predicted_probability"] = scores
    out["predicted_label"] = (scores >= threshold).astype(int)
    out.to_csv(path, index=False)


def save_metrics(path: Path, metrics: dict[str, float], report: str, matrix: np.ndarray, threshold: float, training_summary: dict[str, object] | None = None) -> None:
    payload = {"metrics": metrics, "confusion_matrix": matrix.tolist(), "classification_report": report, "threshold_used": threshold}
    if training_summary is not None:
        payload["training_summary"] = training_summary
    with path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)


def print_result(result: dict[str, object]) -> None:
    print(f"{result['model']} Evaluation Summary")
    print("=" * (len(result["model"]) + 19))
    print(f"{'threshold':>18}: {result['threshold']:.4f}")
    for key in ["accuracy", "precision", "recall", "f1", "roc_auc", "average_precision"]:
        print(f"{key:>18}: {result[key]:.6f}")
    print()


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    train_df, val_df, test_df = load_subset()

    summary = pd.DataFrame(
        [
            {"split": "train", "rows": len(train_df), "fraud": int(train_df["isFraud"].sum()), "fraud_ratio": float(train_df["isFraud"].mean())},
            {"split": "val", "rows": len(val_df), "fraud": int(val_df["isFraud"].sum()), "fraud_ratio": float(val_df["isFraud"].mean())},
            {"split": "test", "rows": len(test_df), "fraud": int(test_df["isFraud"].sum()), "fraud_ratio": float(test_df["isFraud"].mean())},
        ]
    )
    summary.to_csv(OUTPUT_DIR / "subset_summary.csv", index=False)

    results = []
    results.append(train_lightgbm(train_df, val_df, test_df, OUTPUT_DIR / "lightgbm"))
    results.append(train_adaboost(train_df, val_df, test_df, OUTPUT_DIR / "adaboost"))

    graph_df, _, _, _ = build_paysim_graph_frames()
    hetero_data = build_hetero_data(graph_df)
    in_dims = {node_type: hetero_data[node_type].x.size(-1) for node_type in hetero_data.node_types}
    hetero_model = PaySimHeteroGNN(hetero_data.metadata(), in_dims, hidden_dim=64)
    hetero_model, hetero_summary = train_graph_model(hetero_data, hetero_model, epochs=25)
    results.append(evaluate_graph_model("Heterogeneous GNN", hetero_model, hetero_data, graph_df, hetero_summary, OUTPUT_DIR / "heterogeneous_gnn"))

    event_data = build_event_data(graph_df)
    event_in_dims = {node_type: event_data[node_type].x.size(-1) for node_type in event_data.node_types}
    event_model = PaySimEventGNN(event_data.metadata(), event_in_dims, hidden_dim=64)
    event_model, event_summary = train_graph_model(event_data, event_model, epochs=25)
    results.append(evaluate_graph_model("Event-Based GNN", event_model, event_data, graph_df, event_summary, OUTPUT_DIR / "event_based_gnn"))

    results_df = pd.DataFrame(results)
    results_df.to_csv(OUTPUT_DIR / "comparison_metrics.csv", index=False)
    for result in results:
        print_result(result)
    print("Subset Summary")
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
