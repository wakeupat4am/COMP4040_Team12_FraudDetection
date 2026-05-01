"""Train and evaluate an event-based GNN baseline on S-FFSD."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F
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
from torch import Tensor, nn
from torch_geometric.data import HeteroData
from torch_geometric.nn import HeteroConv, SAGEConv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
MODEL_OUTPUT_DIR = PROJECT_ROOT / "models" / "ssfd_event_gnn"


def load_splits() -> pd.DataFrame:
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


def add_event_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce")
    df["amount_log1p"] = np.log1p(df["Amount"].clip(lower=0))

    df["source_tx_count_so_far"] = df.groupby("Source").cumcount()
    df["target_tx_count_so_far"] = df.groupby("Target").cumcount()
    df["pair_tx_count_so_far"] = df.groupby(["Source", "Target"]).cumcount()

    df["prev_time_by_source"] = df.groupby("Source")["Time"].shift(1)
    df["prev_time_by_target"] = df.groupby("Target")["Time"].shift(1)
    df["prev_time_by_pair"] = df.groupby(["Source", "Target"])["Time"].shift(1)
    df["source_time_gap"] = (df["Time"] - df["prev_time_by_source"]).fillna(0)
    df["target_time_gap"] = (df["Time"] - df["prev_time_by_target"]).fillna(0)
    df["pair_time_gap"] = (df["Time"] - df["prev_time_by_pair"]).fillna(0)

    source_amount_sum_before = df.groupby("Source")["Amount"].cumsum() - df["Amount"]
    target_amount_sum_before = df.groupby("Target")["Amount"].cumsum() - df["Amount"]
    pair_amount_sum_before = df.groupby(["Source", "Target"])["Amount"].cumsum() - df["Amount"]

    df["source_amount_mean_before"] = source_amount_sum_before.div(
        df["source_tx_count_so_far"].replace(0, np.nan)
    ).fillna(0)
    df["target_amount_mean_before"] = target_amount_sum_before.div(
        df["target_tx_count_so_far"].replace(0, np.nan)
    ).fillna(0)
    df["pair_amount_mean_before"] = pair_amount_sum_before.div(
        df["pair_tx_count_so_far"].replace(0, np.nan)
    ).fillna(0)

    df["amount_vs_source_mean"] = df["Amount"] - df["source_amount_mean_before"]
    df["amount_vs_target_mean"] = df["Amount"] - df["target_amount_mean_before"]
    df["amount_vs_pair_mean"] = df["Amount"] - df["pair_amount_mean_before"]
    return df


def build_node_maps(df: pd.DataFrame) -> dict[str, dict[str, int]]:
    return {
        "source": {value: idx for idx, value in enumerate(sorted(df["Source"].astype(str).unique()))},
        "target": {value: idx for idx, value in enumerate(sorted(df["Target"].astype(str).unique()))},
    }


def build_entity_features(df: pd.DataFrame, node_maps: dict[str, dict[str, int]]) -> dict[str, Tensor]:
    source_stats = (
        df.groupby("Source")
        .agg(
            degree=("event_id", "size"),
            mean_amount=("Amount", "mean"),
            std_amount=("Amount", "std"),
            unique_targets=("Target", "nunique"),
        )
        .fillna(0)
    )
    target_stats = (
        df.groupby("Target")
        .agg(
            degree=("event_id", "size"),
            mean_amount=("Amount", "mean"),
            std_amount=("Amount", "std"),
            unique_sources=("Source", "nunique"),
        )
        .fillna(0)
    )
    feature_tables = {"source": source_stats, "target": target_stats}
    outputs: dict[str, Tensor] = {}
    for node_type, mapping in node_maps.items():
        rows = []
        table = feature_tables[node_type]
        for raw_id, idx in sorted(mapping.items(), key=lambda item: item[1]):
            rows.append(table.loc[raw_id].to_numpy(dtype=np.float32))
        outputs[node_type] = torch.tensor(np.vstack(rows), dtype=torch.float32)
    return outputs


def build_sequence_edges(size: int) -> torch.Tensor:
    src = torch.arange(0, size - 1, dtype=torch.long)
    dst = torch.arange(1, size, dtype=torch.long)
    return torch.stack([src, dst], dim=0)


def build_group_sequence_edges(df: pd.DataFrame, col: str) -> torch.Tensor:
    sources: list[int] = []
    targets: list[int] = []
    for _, group in df.groupby(col, sort=False):
        event_ids = group["event_id"].to_numpy()
        if len(event_ids) < 2:
            continue
        sources.extend(event_ids[:-1].tolist())
        targets.extend(event_ids[1:].tolist())
    if not sources:
        return torch.empty((2, 0), dtype=torch.long)
    return torch.tensor([sources, targets], dtype=torch.long)


def build_event_graph(df: pd.DataFrame) -> tuple[HeteroData, pd.DataFrame]:
    df = add_event_features(df)
    node_maps = build_node_maps(df)
    entity_features = build_entity_features(df, node_maps)

    data = HeteroData()
    event_x = torch.tensor(
        df[
            [
                "Amount",
                "amount_log1p",
                "Time",
                "source_tx_count_so_far",
                "target_tx_count_so_far",
                "pair_tx_count_so_far",
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
    for idx in [3, 4, 5, 6, 7, 8]:
        max_value = max(float(event_x[:, idx].max().item()), 1.0)
        event_x[:, idx] = event_x[:, idx] / max_value
    data["event"].x = event_x
    data["event"].y = torch.tensor(df["Labels"].replace(2, -1).to_numpy(), dtype=torch.long)

    train_mask = torch.tensor((df["split"] == "train").to_numpy(), dtype=torch.bool)
    test_mask = torch.tensor((df["split"] == "test").to_numpy(), dtype=torch.bool)
    unlabeled_mask = torch.tensor((df["split"] == "unlabeled").to_numpy(), dtype=torch.bool)
    train_indices = np.flatnonzero(train_mask.numpy())
    val_cut = int(len(train_indices) * 0.8)
    val_mask = torch.zeros_like(train_mask)
    val_mask[train_indices[val_cut:]] = True
    train_mask[train_indices[val_cut:]] = False

    data["event"].train_mask = train_mask
    data["event"].val_mask = val_mask
    data["event"].test_mask = test_mask
    data["event"].unlabeled_mask = unlabeled_mask

    for node_type, feats in entity_features.items():
        data[node_type].x = feats

    source_ids = torch.tensor(df["Source"].astype(str).map(node_maps["source"]).to_numpy(), dtype=torch.long)
    target_ids = torch.tensor(df["Target"].astype(str).map(node_maps["target"]).to_numpy(), dtype=torch.long)
    event_ids = torch.tensor(df["event_id"].to_numpy(), dtype=torch.long)

    relations = {
        ("event", "next_event", "event"): build_sequence_edges(len(df)),
        ("event", "next_same_source", "event"): build_group_sequence_edges(df, "Source"),
        ("event", "next_same_target", "event"): build_group_sequence_edges(df, "Target"),
        ("event", "from_source", "source"): torch.stack([event_ids, source_ids]),
        ("source", "rev_from_source", "event"): torch.stack([source_ids, event_ids]),
        ("event", "to_target", "target"): torch.stack([event_ids, target_ids]),
        ("target", "rev_to_target", "event"): torch.stack([target_ids, event_ids]),
    }
    reverse_global = relations[("event", "next_event", "event")].flip(0)
    reverse_source = relations[("event", "next_same_source", "event")].flip(0)
    reverse_target = relations[("event", "next_same_target", "event")].flip(0)
    relations[("event", "prev_event", "event")] = reverse_global
    relations[("event", "prev_same_source", "event")] = reverse_source
    relations[("event", "prev_same_target", "event")] = reverse_target

    for edge_type, edge_index in relations.items():
        data[edge_type].edge_index = edge_index

    return data, df


class EventFraudGNN(nn.Module):
    def __init__(self, metadata: tuple[list[str], list[tuple[str, str, str]]], in_dims: dict[str, int], hidden_dim: int = 96):
        super().__init__()
        self.node_key = {node_type: f"{node_type}_node" for node_type in in_dims}
        self.proj = nn.ModuleDict(
            {
                self.node_key[node_type]: nn.Linear(in_dim, hidden_dim)
                for node_type, in_dim in in_dims.items()
            }
        )
        self.conv1 = HeteroConv(
            {edge_type: SAGEConv((-1, -1), hidden_dim) for edge_type in metadata[1]},
            aggr="sum",
        )
        self.conv2 = HeteroConv(
            {edge_type: SAGEConv((-1, -1), hidden_dim) for edge_type in metadata[1]},
            aggr="sum",
        )
        self.norm1 = nn.ModuleDict({self.node_key[k]: nn.LayerNorm(hidden_dim) for k in in_dims})
        self.norm2 = nn.ModuleDict({self.node_key[k]: nn.LayerNorm(hidden_dim) for k in in_dims})
        self.classifier = nn.Linear(hidden_dim, 1)

    def forward(self, x_dict: dict[str, Tensor], edge_index_dict: dict[tuple[str, str, str], Tensor]) -> Tensor:
        x_dict = {
            node_type: F.relu(self.proj[self.node_key[node_type]](x))
            for node_type, x in x_dict.items()
        }
        x_dict = self.conv1(x_dict, edge_index_dict)
        x_dict = {
            node_type: F.relu(self.norm1[self.node_key[node_type]](x))
            for node_type, x in x_dict.items()
        }
        x_dict = {k: F.dropout(v, p=0.2, training=self.training) for k, v in x_dict.items()}
        x_dict = self.conv2(x_dict, edge_index_dict)
        x_dict = {
            node_type: F.relu(self.norm2[self.node_key[node_type]](x))
            for node_type, x in x_dict.items()
        }
        return self.classifier(x_dict["event"]).squeeze(-1)


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


def train_model(data: HeteroData, epochs: int = 60, lr: float = 0.003) -> tuple[EventFraudGNN, dict[str, object]]:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    data = data.to(device)
    in_dims = {node_type: data[node_type].x.size(-1) for node_type in data.node_types}
    model = EventFraudGNN(data.metadata(), in_dims).to(device)

    train_mask = data["event"].train_mask
    val_mask = data["event"].val_mask
    y_train = data["event"].y[train_mask]
    neg_count = int((y_train == 0).sum().item())
    pos_count = int((y_train == 1).sum().item())
    pos_weight = torch.tensor([neg_count / max(pos_count, 1)], device=device)

    optimizer = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode="max", factor=0.5, patience=5, min_lr=1e-4
    )

    best_state = None
    best_ap = -1.0
    best_threshold = 0.5
    history: list[dict[str, float]] = []

    for epoch in range(1, epochs + 1):
        model.train()
        optimizer.zero_grad()
        logits = model(data.x_dict, data.edge_index_dict)
        loss = F.binary_cross_entropy_with_logits(
            logits[train_mask],
            data["event"].y[train_mask].float(),
            pos_weight=pos_weight,
        )
        loss.backward()
        optimizer.step()

        model.eval()
        with torch.no_grad():
            val_scores = torch.sigmoid(model(data.x_dict, data.edge_index_dict)[val_mask]).cpu().numpy()
            val_true = data["event"].y[val_mask].cpu().numpy()
            val_ap = float(average_precision_score(val_true, val_scores))
            threshold, threshold_metrics = select_best_threshold(val_true, val_scores)
            history.append(
                {
                    "epoch": epoch,
                    "train_loss": float(loss.item()),
                    "val_average_precision": val_ap,
                    "val_best_threshold": float(threshold),
                    "val_best_f1": float(threshold_metrics["f1"]),
                }
            )
            if val_ap > best_ap:
                best_ap = val_ap
                best_threshold = float(threshold)
                best_state = deepcopy(model.state_dict())
        scheduler.step(val_ap)

    if best_state is not None:
        model.load_state_dict(best_state)

    return model, {"best_val_average_precision": best_ap, "best_threshold": best_threshold, "history": history}


def evaluate_and_save(model: EventFraudGNN, data: HeteroData, df: pd.DataFrame, training_summary: dict[str, object]) -> None:
    device = next(model.parameters()).device
    data = data.to(device)
    model.eval()
    with torch.no_grad():
        scores = torch.sigmoid(model(data.x_dict, data.edge_index_dict)).cpu().numpy()

    threshold = float(training_summary.get("best_threshold", 0.5))
    test_mask = data["event"].test_mask.cpu().numpy()
    y_true = data["event"].y[data["event"].test_mask].cpu().numpy()
    y_score = scores[test_mask]
    metrics, report, matrix = compute_metrics(y_true, y_score, threshold=threshold)

    MODEL_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), MODEL_OUTPUT_DIR / "ssfd_event_gnn_model.pt")

    predictions = df.loc[test_mask, ["Time", "Source", "Target", "Amount", "Location", "Type", "Labels"]].copy()
    predictions["predicted_probability"] = y_score
    predictions["predicted_label"] = (y_score >= threshold).astype(int)
    predictions.to_csv(MODEL_OUTPUT_DIR / "ssfd_event_gnn_test_predictions.csv", index=False)

    relationship_summary = {
        "node_counts": {node_type: int(data[node_type].num_nodes) for node_type in data.node_types},
        "edge_counts": {str(edge_type): int(data[edge_type].edge_index.size(1)) for edge_type in data.edge_types},
        "relationship_method": {
            "event_next_event": "Each transaction connects to the immediately next transaction in global time order.",
            "event_prev_event": "Reverse global temporal edges allow backward message passing.",
            "event_next_same_source": "Each source-specific transaction sequence is linked in time order.",
            "event_prev_same_source": "Reverse same-source temporal edges allow backward message passing.",
            "event_next_same_target": "Each target-specific transaction sequence is linked in time order.",
            "event_prev_same_target": "Reverse same-target temporal edges allow backward message passing.",
            "event_from_source": "Each event connects to its source entity.",
            "event_to_target": "Each event connects to its target entity.",
        },
    }
    with (MODEL_OUTPUT_DIR / "ssfd_event_gnn_relationships.json").open("w", encoding="utf-8") as fh:
        json.dump(relationship_summary, fh, indent=2)

    metrics_payload = {
        "metrics": metrics,
        "confusion_matrix": matrix.tolist(),
        "classification_report": report,
        "training_summary": training_summary,
        "threshold_used": threshold,
    }
    with (MODEL_OUTPUT_DIR / "ssfd_event_gnn_metrics.json").open("w", encoding="utf-8") as fh:
        json.dump(metrics_payload, fh, indent=2)

    print("Event-Based GNN Evaluation Summary")
    print("=" * 35)
    print(f"{'threshold':>18}: {threshold:.4f}")
    for key, value in metrics.items():
        print(f"{key:>18}: {value:.6f}")
    print("\nConfusion Matrix")
    print(matrix)
    print("\nClassification Report")
    print(report)
    print("\nRelationship Summary")
    for key, value in relationship_summary["relationship_method"].items():
        print(f"- {key}: {value}")


def main() -> None:
    df = load_splits()
    data, featured_df = build_event_graph(df)
    model, training_summary = train_model(data)
    evaluate_and_save(model, data, featured_df, training_summary)


if __name__ == "__main__":
    main()
