"""Shared training utilities for S-FFSD models."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F
from lightgbm import LGBMClassifier
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
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier
from torch import Tensor, nn
from torch_geometric.data import HeteroData
from torch_geometric.nn import HeteroConv, SAGEConv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"


def print_result(result: dict[str, object]) -> None:
    print(f"{result['model']} Evaluation Summary")
    print("=" * (len(result["model"]) + 19))
    if "threshold" in result:
        print(f"{'threshold':>18}: {result['threshold']:.4f}")
    for key in ["accuracy", "precision", "recall", "f1", "roc_auc", "average_precision"]:
        print(f"{key:>18}: {result[key]:.6f}")
    print()


def compute_metrics(y_true: np.ndarray, y_score: np.ndarray, threshold: float = 0.5) -> tuple[dict[str, float], str, np.ndarray]:
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


def save_metrics(path: Path, metrics: dict[str, float], report: str, matrix: np.ndarray, threshold: float, training_summary: dict[str, object] | None = None) -> None:
    payload = {"metrics": metrics, "confusion_matrix": matrix.tolist(), "classification_report": report, "threshold_used": threshold}
    if training_summary is not None:
        payload["training_summary"] = training_summary
    with path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)


def save_predictions(path: Path, df: pd.DataFrame, scores: np.ndarray, threshold: float) -> None:
    out = df[["Time", "Source", "Target", "Amount", "Location", "Type", "Labels"]].copy()
    out["predicted_probability"] = scores
    out["predicted_label"] = (scores >= threshold).astype(int)
    out.to_csv(path, index=False)


def load_saved_splits() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    train_df = pd.read_csv(PROCESSED_DIR / "ssfd_lightgbm_train.csv")
    test_df = pd.read_csv(PROCESSED_DIR / "ssfd_lightgbm_test.csv")
    unlabeled_df = pd.read_csv(PROCESSED_DIR / "ssfd_lightgbm_unlabeled.csv")
    return train_df, test_df, unlabeled_df


def load_split(path: Path, split_name: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["split"] = split_name
    return df


def load_tree_frames(use_unlabeled_context: bool = False) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame | None]:
    train_df, test_df, unlabeled_df = load_saved_splits()
    train_df["split"] = "train"
    test_df["split"] = "test"
    if use_unlabeled_context:
        unlabeled_df["split"] = "unlabeled"
        return train_df, test_df, unlabeled_df
    return train_df, test_df, None


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

    df["source_amount_mean_before"] = source_amount_sum_before.div(df["source_tx_count_so_far"].replace(0, np.nan))
    df["target_amount_mean_before"] = target_amount_sum_before.div(df["target_tx_count_so_far"].replace(0, np.nan))
    df["pair_amount_mean_before"] = pair_amount_sum_before.div(df["source_target_pair_count_so_far"].replace(0, np.nan))

    df["amount_vs_source_mean"] = df["Amount"] - df["source_amount_mean_before"]
    df["amount_vs_target_mean"] = df["Amount"] - df["target_amount_mean_before"]
    df["amount_vs_pair_mean"] = df["Amount"] - df["pair_amount_mean_before"]

    df["source_seen_target_before"] = df.groupby(["Source", "Target"]).cumcount().gt(0).astype(int)
    df["source_seen_location_before"] = df.groupby(["Source", "Location"]).cumcount().gt(0).astype(int)
    df["source_seen_type_before"] = df.groupby(["Source", "Type"]).cumcount().gt(0).astype(int)

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


def prepare_tree_frames(train_df: pd.DataFrame, test_df: pd.DataFrame, unlabeled_df: pd.DataFrame | None) -> tuple[pd.DataFrame, pd.DataFrame]:
    frames = [train_df, test_df]
    if unlabeled_df is not None:
        frames.insert(0, unlabeled_df)
    combined = pd.concat(frames, ignore_index=True)
    combined = build_history_features(combined)
    return combined[combined["split"] == "train"].copy(), combined[combined["split"] == "test"].copy()


SSFD_LGBM_FEATURES = [
    "Time",
    "Amount",
    "amount_log1p",
    "Source",
    "Target",
    "Location",
    "Type",
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
]


def train_lightgbm(train_df: pd.DataFrame, test_df: pd.DataFrame, out_dir: Path, use_unlabeled_context: bool = False) -> dict[str, object]:
    train_raw, test_raw, unlabeled_raw = load_tree_frames(use_unlabeled_context)
    train_featured, test_featured = prepare_tree_frames(train_raw, test_raw, unlabeled_raw)
    X_train = train_featured[SSFD_LGBM_FEATURES].copy()
    y_train = train_featured["Labels"].astype(int)
    X_test = test_featured[SSFD_LGBM_FEATURES].copy()
    y_test = test_featured["Labels"].astype(int)
    categorical_columns = ["Source", "Target", "Location", "Type"]
    for col in categorical_columns:
        X_train[col] = X_train[col].astype("category")
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
    scores = model.predict_proba(X_test)[:, 1]
    metrics, report, matrix = compute_metrics(y_test.to_numpy(), scores, threshold=0.5)

    out_dir.mkdir(parents=True, exist_ok=True)
    model.booster_.save_model(str(out_dir / "ssfd_lightgbm_model.txt"))
    pd.DataFrame({"feature": SSFD_LGBM_FEATURES, "importance": model.feature_importances_}).sort_values(
        "importance", ascending=False
    ).to_csv(out_dir / "ssfd_lightgbm_feature_importance.csv", index=False)
    save_predictions(out_dir / "ssfd_lightgbm_test_predictions.csv", test_featured, scores, 0.5)
    save_metrics(out_dir / "ssfd_lightgbm_metrics.json", metrics, report, matrix, 0.5)
    return {"model": "LightGBM", "threshold": 0.5, **metrics}


def encode_categorical_statistics(train_df: pd.DataFrame, test_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    encoded_train = train_df.copy()
    encoded_test = test_df.copy()
    for col in ["Source", "Target", "Location", "Type"]:
        freq_map = train_df[col].value_counts(normalize=True).to_dict()
        count_map = train_df[col].value_counts().to_dict()
        encoded_train[f"{col.lower()}_freq"] = train_df[col].map(freq_map).fillna(0.0)
        encoded_test[f"{col.lower()}_freq"] = test_df[col].map(freq_map).fillna(0.0)
        encoded_train[f"{col.lower()}_count"] = train_df[col].map(count_map).fillna(0.0)
        encoded_test[f"{col.lower()}_count"] = test_df[col].map(count_map).fillna(0.0)
    return encoded_train, encoded_test


SSFD_ADABOOST_FEATURES = [
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

SSFD_LOGISTIC_FEATURES = SSFD_ADABOOST_FEATURES


def train_adaboost(train_df: pd.DataFrame, test_df: pd.DataFrame, out_dir: Path, use_unlabeled_context: bool = False) -> dict[str, object]:
    train_raw, test_raw, unlabeled_raw = load_tree_frames(use_unlabeled_context)
    train_featured, test_featured = prepare_tree_frames(train_raw, test_raw, unlabeled_raw)
    train_encoded, test_encoded = encode_categorical_statistics(train_featured, test_featured)
    X_train = train_encoded[SSFD_ADABOOST_FEATURES]
    y_train = train_encoded["Labels"].astype(int)
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
    scores = model.predict_proba(X_test)[:, 1]
    metrics, report, matrix = compute_metrics(y_test.to_numpy(), scores, threshold=0.5)

    out_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"feature": SSFD_ADABOOST_FEATURES, "importance": model.feature_importances_}).sort_values(
        "importance", ascending=False
    ).to_csv(out_dir / "ssfd_adaboost_feature_importance.csv", index=False)
    save_predictions(out_dir / "ssfd_adaboost_test_predictions.csv", test_encoded, scores, 0.5)
    save_metrics(out_dir / "ssfd_adaboost_metrics.json", metrics, report, matrix, 0.5)
    return {"model": "AdaBoost", "threshold": 0.5, **metrics}


def train_logistic_regression(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    out_dir: Path,
    use_unlabeled_context: bool = False,
) -> dict[str, object]:
    train_raw, test_raw, unlabeled_raw = load_tree_frames(use_unlabeled_context)
    train_featured, test_featured = prepare_tree_frames(train_raw, test_raw, unlabeled_raw)
    train_encoded, test_encoded = encode_categorical_statistics(train_featured, test_featured)

    X_train = train_encoded[SSFD_LOGISTIC_FEATURES]
    y_train = train_encoded["Labels"].astype(int)
    X_test = test_encoded[SSFD_LOGISTIC_FEATURES]
    y_test = test_encoded["Labels"].astype(int)

    neg = int((y_train == 0).sum())
    pos = int((y_train == 1).sum())
    class_weight = {0: 1.0, 1: neg / max(pos, 1)}

    model = Pipeline(
        [
            ("scaler", StandardScaler()),
            (
                "classifier",
                LogisticRegression(
                    C=1.0,
                    class_weight=class_weight,
                    max_iter=2000,
                    solver="lbfgs",
                    random_state=42,
                ),
            ),
        ]
    )
    model.fit(X_train, y_train)
    scores = model.predict_proba(X_test)[:, 1]
    metrics, report, matrix = compute_metrics(y_test.to_numpy(), scores, threshold=0.5)

    out_dir.mkdir(parents=True, exist_ok=True)
    classifier = model.named_steps["classifier"]
    pd.DataFrame(
        {
            "feature": SSFD_LOGISTIC_FEATURES,
            "coefficient": classifier.coef_[0],
            "abs_coefficient": np.abs(classifier.coef_[0]),
        }
    ).sort_values("abs_coefficient", ascending=False).to_csv(
        out_dir / "ssfd_logistic_regression_coefficients.csv", index=False
    )
    save_predictions(out_dir / "ssfd_logistic_regression_test_predictions.csv", test_encoded, scores, 0.5)
    save_metrics(out_dir / "ssfd_logistic_regression_metrics.json", metrics, report, matrix, 0.5)
    return {"model": "Logistic Regression", "threshold": 0.5, **metrics}


def load_graph_df() -> pd.DataFrame:
    frames = []
    for filename, split_name in [
        ("ssfd_lightgbm_train.csv", "train"),
        ("ssfd_lightgbm_test.csv", "test"),
        ("ssfd_lightgbm_unlabeled.csv", "unlabeled"),
    ]:
        df = pd.read_csv(PROCESSED_DIR / filename)
        df["split"] = split_name
        frames.append(df)
    full_df = pd.concat(frames, ignore_index=True)
    full_df = full_df.sort_values("Time").reset_index(drop=True)
    full_df["event_id"] = np.arange(len(full_df))
    return full_df


class BaseHeteroClassifier(nn.Module):
    def __init__(self, metadata: tuple[list[str], list[tuple[str, str, str]]], in_dims: dict[str, int], hidden_dim: int = 64):
        super().__init__()
        self.node_key = {node_type: f"{node_type}_node" for node_type in in_dims}
        self.proj = nn.ModuleDict({self.node_key[k]: nn.Linear(v, hidden_dim) for k, v in in_dims.items()})
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


def select_best_threshold(y_true: np.ndarray, y_score: np.ndarray) -> tuple[float, dict[str, float]]:
    best_threshold = 0.5
    best_metrics = {}
    best_f1 = -1.0
    roc_auc = float(roc_auc_score(y_true, y_score))
    ap = float(average_precision_score(y_true, y_score))
    for threshold in np.linspace(0.05, 0.95, 37):
        y_pred = (y_score >= float(threshold)).astype(int)
        metrics = {
            "accuracy": float(accuracy_score(y_true, y_pred)),
            "precision": float(precision_score(y_true, y_pred, zero_division=0)),
            "recall": float(recall_score(y_true, y_pred, zero_division=0)),
            "f1": float(f1_score(y_true, y_pred, zero_division=0)),
            "roc_auc": roc_auc,
            "average_precision": ap,
        }
        if metrics["f1"] > best_f1:
            best_f1 = metrics["f1"]
            best_threshold = float(threshold)
            best_metrics = metrics
    return best_threshold, best_metrics


def train_graph_model(data: HeteroData, model: nn.Module, epochs: int, lr: float) -> tuple[nn.Module, dict[str, object]]:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    data = data.to(device)
    model = model.to(device)
    train_mask = data["event"].train_mask
    val_mask = data["event"].val_mask
    y_train = data["event"].y[train_mask]
    neg = int((y_train == 0).sum().item())
    pos = int((y_train == 1).sum().item())
    pos_weight = torch.tensor([neg / max(pos, 1)], device=device)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode="max", factor=0.5, patience=5, min_lr=1e-4)

    best_state = None
    best_ap = -1.0
    best_threshold = 0.5
    history: list[dict[str, float]] = []
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
            threshold, threshold_metrics = select_best_threshold(val_true, val_scores)
            history.append({"epoch": epoch, "train_loss": float(loss.item()), "val_average_precision": val_ap, "val_best_threshold": threshold, "val_best_f1": float(threshold_metrics["f1"])})
            if val_ap > best_ap:
                best_ap = val_ap
                best_threshold = threshold
                best_state = deepcopy(model.state_dict())
        scheduler.step(val_ap)

    if best_state is not None:
        model.load_state_dict(best_state)
    return model, {"best_val_average_precision": best_ap, "best_threshold": best_threshold, "history": history}


def build_hetero_graph_df(df: pd.DataFrame) -> tuple[HeteroData, pd.DataFrame]:
    df = build_history_features(df)
    node_maps = {
        "source": {value: idx for idx, value in enumerate(sorted(df["Source"].astype(str).unique()))},
        "target": {value: idx for idx, value in enumerate(sorted(df["Target"].astype(str).unique()))},
        "location": {value: idx for idx, value in enumerate(sorted(df["Location"].astype(str).unique()))},
        "type": {value: idx for idx, value in enumerate(sorted(df["Type"].astype(str).unique()))},
    }

    def stats_for(col: str, others: list[str]) -> pd.DataFrame:
        agg = {
            "degree": ("event_id", "size"),
            "mean_amount": ("Amount", "mean"),
            "std_amount": ("Amount", "std"),
        }
        for other in others:
            agg[f"unique_{other.lower()}s"] = (other, "nunique")
        return df.groupby(col).agg(**agg).fillna(0)

    feature_tables = {
        "source": stats_for("Source", ["Target", "Location", "Type"]),
        "target": stats_for("Target", ["Source", "Location", "Type"]),
        "location": stats_for("Location", ["Source", "Target", "Type"]),
        "type": stats_for("Type", ["Source", "Target", "Location"]),
    }

    data = HeteroData()
    event_x = torch.tensor(
        df[
            [
                "Amount",
                "amount_log1p",
                "Time",
                "source_tx_count_so_far",
                "target_tx_count_so_far",
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
            ]
        ].to_numpy(dtype=np.float32),
        dtype=torch.float32,
    )
    max_time = max(float(df["Time"].max()), 1.0)
    event_x[:, 2] = event_x[:, 2] / max_time
    data["event"].x = event_x
    data["event"].y = torch.tensor(df["Labels"].replace(2, -1).to_numpy(), dtype=torch.long)

    train_mask = torch.tensor((df["split"] == "train").to_numpy(), dtype=torch.bool)
    test_mask = torch.tensor((df["split"] == "test").to_numpy(), dtype=torch.bool)
    if "val" in set(df["split"].astype(str).unique()):
        val_mask = torch.tensor((df["split"] == "val").to_numpy(), dtype=torch.bool)
    else:
        train_idx = np.flatnonzero(train_mask.numpy())
        val_cut = int(len(train_idx) * 0.8)
        val_mask = torch.zeros_like(train_mask)
        val_mask[train_idx[val_cut:]] = True
        train_mask[train_idx[val_cut:]] = False
    data["event"].train_mask = train_mask
    data["event"].val_mask = val_mask
    data["event"].test_mask = test_mask

    for node_type, mapping in node_maps.items():
        rows = [
            feature_tables[node_type].loc[raw_id].to_numpy(dtype=np.float32)
            for raw_id, _ in sorted(mapping.items(), key=lambda item: item[1])
        ]
        data[node_type].x = torch.tensor(np.vstack(rows), dtype=torch.float32)

    event_ids = torch.tensor(df["event_id"].to_numpy(), dtype=torch.long)
    source_ids = torch.tensor(df["Source"].astype(str).map(node_maps["source"]).to_numpy(), dtype=torch.long)
    target_ids = torch.tensor(df["Target"].astype(str).map(node_maps["target"]).to_numpy(), dtype=torch.long)
    location_ids = torch.tensor(df["Location"].astype(str).map(node_maps["location"]).to_numpy(), dtype=torch.long)
    type_ids = torch.tensor(df["Type"].astype(str).map(node_maps["type"]).to_numpy(), dtype=torch.long)

    relations = {
        ("event", "from_source", "source"): torch.stack([event_ids, source_ids]),
        ("source", "rev_from_source", "event"): torch.stack([source_ids, event_ids]),
        ("event", "to_target", "target"): torch.stack([event_ids, target_ids]),
        ("target", "rev_to_target", "event"): torch.stack([target_ids, event_ids]),
        ("event", "at_location", "location"): torch.stack([event_ids, location_ids]),
        ("location", "rev_at_location", "event"): torch.stack([location_ids, event_ids]),
        ("event", "has_type", "type"): torch.stack([event_ids, type_ids]),
        ("type", "rev_has_type", "event"): torch.stack([type_ids, event_ids]),
        ("source", "to_target", "target"): torch.stack([source_ids, target_ids]),
        ("target", "rev_to_target_source", "source"): torch.stack([target_ids, source_ids]),
        ("source", "at_location", "location"): torch.stack([source_ids, location_ids]),
        ("location", "rev_at_location_source", "source"): torch.stack([location_ids, source_ids]),
        ("source", "uses_type", "type"): torch.stack([source_ids, type_ids]),
        ("type", "rev_uses_type_source", "source"): torch.stack([type_ids, source_ids]),
        ("target", "at_location", "location"): torch.stack([target_ids, location_ids]),
        ("location", "rev_target_location", "target"): torch.stack([location_ids, target_ids]),
        ("target", "uses_type", "type"): torch.stack([target_ids, type_ids]),
        ("type", "rev_target_type", "target"): torch.stack([type_ids, target_ids]),
    }
    for edge_type, edge_index in relations.items():
        data[edge_type].edge_index = edge_index
    return data, df


def build_event_graph_df(df: pd.DataFrame) -> tuple[HeteroData, pd.DataFrame]:
    df = build_history_features(df)
    node_maps = {
        "source": {value: idx for idx, value in enumerate(sorted(df["Source"].astype(str).unique()))},
        "target": {value: idx for idx, value in enumerate(sorted(df["Target"].astype(str).unique()))},
    }
    source_stats = (
        df.groupby("Source")
        .agg(degree=("event_id", "size"), mean_amount=("Amount", "mean"), std_amount=("Amount", "std"), unique_targets=("Target", "nunique"))
        .fillna(0)
    )
    target_stats = (
        df.groupby("Target")
        .agg(degree=("event_id", "size"), mean_amount=("Amount", "mean"), std_amount=("Amount", "std"), unique_sources=("Source", "nunique"))
        .fillna(0)
    )

    data = HeteroData()
    event_x = torch.tensor(
        df[
            [
                "Amount",
                "amount_log1p",
                "Time",
                "source_tx_count_so_far",
                "target_tx_count_so_far",
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
            ]
        ].to_numpy(dtype=np.float32),
        dtype=torch.float32,
    )
    max_time = max(float(df["Time"].max()), 1.0)
    event_x[:, 2] = event_x[:, 2] / max_time
    data["event"].x = event_x
    data["event"].y = torch.tensor(df["Labels"].replace(2, -1).to_numpy(), dtype=torch.long)
    train_mask = torch.tensor((df["split"] == "train").to_numpy(), dtype=torch.bool)
    test_mask = torch.tensor((df["split"] == "test").to_numpy(), dtype=torch.bool)
    if "val" in set(df["split"].astype(str).unique()):
        val_mask = torch.tensor((df["split"] == "val").to_numpy(), dtype=torch.bool)
    else:
        train_idx = np.flatnonzero(train_mask.numpy())
        val_cut = int(len(train_idx) * 0.8)
        val_mask = torch.zeros_like(train_mask)
        val_mask[train_idx[val_cut:]] = True
        train_mask[train_idx[val_cut:]] = False
    data["event"].train_mask = train_mask
    data["event"].val_mask = val_mask
    data["event"].test_mask = test_mask

    data["source"].x = torch.tensor(
        np.vstack([source_stats.loc[k].to_numpy(dtype=np.float32) for k, _ in sorted(node_maps["source"].items(), key=lambda x: x[1])]),
        dtype=torch.float32,
    )
    data["target"].x = torch.tensor(
        np.vstack([target_stats.loc[k].to_numpy(dtype=np.float32) for k, _ in sorted(node_maps["target"].items(), key=lambda x: x[1])]),
        dtype=torch.float32,
    )

    event_ids = torch.tensor(df["event_id"].to_numpy(), dtype=torch.long)
    source_ids = torch.tensor(df["Source"].astype(str).map(node_maps["source"]).to_numpy(), dtype=torch.long)
    target_ids = torch.tensor(df["Target"].astype(str).map(node_maps["target"]).to_numpy(), dtype=torch.long)

    def group_edges(col: str) -> torch.Tensor:
        src, dst = [], []
        for _, group in df.groupby(col, sort=False):
            ids = group["event_id"].to_numpy()
            if len(ids) < 2:
                continue
            src.extend(ids[:-1].tolist())
            dst.extend(ids[1:].tolist())
        return torch.tensor([src, dst], dtype=torch.long) if src else torch.empty((2, 0), dtype=torch.long)

    global_src = torch.arange(0, len(df) - 1, dtype=torch.long)
    global_dst = torch.arange(1, len(df), dtype=torch.long)
    same_source = group_edges("Source")
    same_target = group_edges("Target")

    relations = {
        ("event", "next_event", "event"): torch.stack([global_src, global_dst]),
        ("event", "prev_event", "event"): torch.stack([global_dst, global_src]),
        ("event", "next_same_source", "event"): same_source,
        ("event", "prev_same_source", "event"): same_source.flip(0),
        ("event", "next_same_target", "event"): same_target,
        ("event", "prev_same_target", "event"): same_target.flip(0),
        ("event", "from_source", "source"): torch.stack([event_ids, source_ids]),
        ("source", "rev_from_source", "event"): torch.stack([source_ids, event_ids]),
        ("event", "to_target", "target"): torch.stack([event_ids, target_ids]),
        ("target", "rev_to_target", "event"): torch.stack([target_ids, event_ids]),
    }
    for edge_type, edge_index in relations.items():
        data[edge_type].edge_index = edge_index
    return data, df


def evaluate_graph_model(model_name: str, model: nn.Module, data: HeteroData, df: pd.DataFrame, training_summary: dict[str, object], out_dir: Path, filename_prefix: str, save_model_name: str) -> dict[str, object]:
    device = next(model.parameters()).device
    data = data.to(device)
    model.eval()
    with torch.no_grad():
        scores = torch.sigmoid(model(data.x_dict, data.edge_index_dict)).cpu().numpy()
    threshold = float(training_summary["best_threshold"])
    test_mask = data["event"].test_mask.cpu().numpy()
    y_true = data["event"].y[data["event"].test_mask].cpu().numpy()
    y_score = scores[test_mask]
    metrics, report, matrix = compute_metrics(y_true, y_score, threshold)

    out_dir.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), out_dir / save_model_name)
    save_predictions(out_dir / f"{filename_prefix}_test_predictions.csv", df.loc[test_mask].copy(), y_score, threshold)
    save_metrics(out_dir / f"{filename_prefix}_metrics.json", metrics, report, matrix, threshold, training_summary)
    return {"model": model_name, "threshold": threshold, **metrics}


def train_hetero_gnn(out_dir: Path) -> dict[str, object]:
    df = load_graph_df()
    data, graph_df = build_hetero_graph_df(df)
    in_dims = {node_type: data[node_type].x.size(-1) for node_type in data.node_types}
    model = BaseHeteroClassifier(data.metadata(), in_dims, hidden_dim=96)
    model, summary = train_graph_model(data, model, epochs=80, lr=0.003)
    relationship_summary = {
        "node_counts": {node_type: int(data[node_type].num_nodes) for node_type in data.node_types},
        "edge_counts": {str(edge_type): int(data[edge_type].edge_index.size(1)) for edge_type in data.edge_types},
    }
    result = evaluate_graph_model("Heterogeneous GNN", model, data, graph_df, summary, out_dir, "ssfd_hetero_gnn", "ssfd_hetero_gnn_model.pt")
    with (out_dir / "ssfd_hetero_gnn_relationships.json").open("w", encoding="utf-8") as fh:
        json.dump(relationship_summary, fh, indent=2)
    return result


def train_event_gnn(out_dir: Path) -> dict[str, object]:
    df = load_graph_df()
    data, graph_df = build_event_graph_df(df)
    in_dims = {node_type: data[node_type].x.size(-1) for node_type in data.node_types}
    model = BaseHeteroClassifier(data.metadata(), in_dims, hidden_dim=96)
    model, summary = train_graph_model(data, model, epochs=60, lr=0.003)
    relationship_summary = {
        "node_counts": {node_type: int(data[node_type].num_nodes) for node_type in data.node_types},
        "edge_counts": {str(edge_type): int(data[edge_type].edge_index.size(1)) for edge_type in data.edge_types},
    }
    result = evaluate_graph_model("Event-Based GNN", model, data, graph_df, summary, out_dir, "ssfd_event_gnn", "ssfd_event_gnn_model.pt")
    with (out_dir / "ssfd_event_gnn_relationships.json").open("w", encoding="utf-8") as fh:
        json.dump(relationship_summary, fh, indent=2)
    return result
