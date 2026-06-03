from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
import torch
from lightgbm import LGBMClassifier
from sklearn.ensemble import AdaBoostClassifier
from sklearn.tree import DecisionTreeClassifier

from models.train_ssfd_four_models import BaseHeteroClassifier, SSFD_ADABOOST_FEATURES, SSFD_LGBM_FEATURES, build_event_graph_df, build_history_features, encode_categorical_statistics, load_saved_splits

from .calibration import fit_isotonic_calibrator, load_calibrator, save_calibrator


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = PROJECT_ROOT / "end_to_end" / "pipeline_config.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def artifact_path(key: str) -> Path:
    config = load_json(CONFIG_PATH)
    return PROJECT_ROOT / config["artifact_paths"][key]


def _validated_split_frames() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
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


def _prepare_tree_splits() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    train_df, val_df, test_df, unlabeled_df = _validated_split_frames()
    combined = pd.concat([unlabeled_df, train_df, val_df, test_df], ignore_index=True)
    combined = build_history_features(combined)
    return (
        combined[combined["split"] == "train"].copy(),
        combined[combined["split"] == "val"].copy(),
        combined[combined["split"] == "test"].copy(),
    )


def _save_metadata(payload: dict[str, Any]) -> None:
    path = artifact_path("metadata")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def ensure_runtime_artifacts() -> None:
    lg_path = artifact_path("lightgbm_model")
    ada_path = artifact_path("adaboost_model")
    if lg_path.exists() and ada_path.exists() and artifact_path("lightgbm_calibrator").exists() and artifact_path("adaboost_calibrator").exists() and artifact_path("event_gnn_calibrator").exists():
        return

    train_df, val_df, _ = _prepare_tree_splits()
    # LightGBM
    X_train = train_df[SSFD_LGBM_FEATURES].copy()
    y_train = train_df["Labels"].astype(int)
    X_val = val_df[SSFD_LGBM_FEATURES].copy()
    y_val = val_df["Labels"].astype(int)
    categorical_columns = ["Source", "Target", "Location", "Type"]
    for col in categorical_columns:
        X_train[col] = X_train[col].astype("category")
        X_val[col] = X_val[col].astype("category")
    neg = int((y_train == 0).sum())
    pos = int((y_train == 1).sum())
    lightgbm_model = LGBMClassifier(
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
    lightgbm_model.fit(X_train, y_train, categorical_feature=categorical_columns)
    lg_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(lightgbm_model, lg_path)
    lightgbm_val_scores = pd.Series(lightgbm_model.predict_proba(X_val)[:, 1])
    save_calibrator(fit_isotonic_calibrator(lightgbm_val_scores, y_val), artifact_path("lightgbm_calibrator"))

    # AdaBoost
    train_encoded, val_encoded = encode_categorical_statistics(train_df, val_df)
    X_train_ada = train_encoded[SSFD_ADABOOST_FEATURES]
    y_train_ada = train_encoded["Labels"].astype(int)
    X_val_ada = val_encoded[SSFD_ADABOOST_FEATURES]
    y_val_ada = val_encoded["Labels"].astype(int)
    neg_ada = int((y_train_ada == 0).sum())
    pos_ada = int((y_train_ada == 1).sum())
    sample_weight = np.where(y_train_ada == 1, neg_ada / max(pos_ada, 1), 1.0)
    adaboost_model = AdaBoostClassifier(
        estimator=DecisionTreeClassifier(max_depth=2, random_state=42),
        n_estimators=200,
        learning_rate=0.5,
        random_state=42,
    )
    adaboost_model.fit(X_train_ada, y_train_ada, sample_weight=sample_weight)
    joblib.dump(adaboost_model, ada_path)
    adaboost_val_scores = pd.Series(adaboost_model.predict_proba(X_val_ada)[:, 1])
    save_calibrator(fit_isotonic_calibrator(adaboost_val_scores, y_val_ada), artifact_path("adaboost_calibrator"))

    # Event-GNN calibrator only; model weights already exist from validated run.
    event_val = pd.read_csv(PROJECT_ROOT / "models" / "ssfd_validated_ensemble" / "event_gnn" / "ssfd_event_gnn_val_predictions.csv")
    save_calibrator(
        fit_isotonic_calibrator(event_val["predicted_probability"], event_val["Labels"].astype(int)),
        artifact_path("event_gnn_calibrator"),
    )

    _save_metadata(
        {
            "categorical_columns": categorical_columns,
            "lightgbm_features": SSFD_LGBM_FEATURES,
            "adaboost_features": SSFD_ADABOOST_FEATURES,
            "event_gnn_hidden_dim": 96,
        }
    )


def load_lightgbm_model() -> Any:
    ensure_runtime_artifacts()
    return joblib.load(artifact_path("lightgbm_model"))


def load_adaboost_model() -> Any:
    ensure_runtime_artifacts()
    return joblib.load(artifact_path("adaboost_model"))


def _dummy_event_context() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "event_id": 0,
                "Time": 1.0,
                "Source": "bootstrap_source",
                "Target": "bootstrap_target",
                "Amount": 1.0,
                "Location": "L0",
                "Type": "TP0",
                "Labels": 2,
                "split": "context",
            },
            {
                "event_id": 1,
                "Time": 2.0,
                "Source": "bootstrap_source",
                "Target": "bootstrap_target",
                "Amount": 1.1,
                "Location": "L0",
                "Type": "TP0",
                "Labels": 2,
                "split": "test",
            },
        ]
    )


def load_event_gnn_model() -> tuple[BaseHeteroClassifier, torch.device]:
    ensure_runtime_artifacts()
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    data, _ = build_event_graph_df(_dummy_event_context())
    in_dims = {node_type: data[node_type].x.size(-1) for node_type in data.node_types}
    model = BaseHeteroClassifier(data.metadata(), in_dims, hidden_dim=96).to(device)
    model.load_state_dict(torch.load(artifact_path("event_gnn_state_dict"), map_location=device))
    model.eval()
    return model, device


def load_runtime_metadata() -> dict[str, Any]:
    ensure_runtime_artifacts()
    return load_json(artifact_path("metadata"))


def load_calibrators() -> dict[str, Any]:
    ensure_runtime_artifacts()
    return {
        "lightgbm": load_calibrator(artifact_path("lightgbm_calibrator")),
        "adaboost": load_calibrator(artifact_path("adaboost_calibrator")),
        "event_gnn": load_calibrator(artifact_path("event_gnn_calibrator")),
    }
