"""Register the current production model artifacts in MLflow."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import mlflow

from end_to_end.pipeline import CONFIG_PATH, load_json
from end_to_end.model_loader import artifact_path, ensure_runtime_artifacts
from fraud_detection.config import get_settings


def _log_json_artifact(name: str, payload: dict[str, Any]) -> None:
    mlflow.log_dict(payload, name)


def main() -> int:
    settings = get_settings()
    config = load_json(CONFIG_PATH)
    ensure_runtime_artifacts()

    mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
    mlflow.set_experiment(settings.mlflow_experiment_name)

    with mlflow.start_run(run_name=config["default_pipeline_profile"]) as run:
        selected_ensemble = config["selected_ensemble"]
        mlflow.log_param("pipeline_profile", config["default_pipeline_profile"])
        mlflow.log_param("ensemble_name", selected_ensemble["name"])
        mlflow.log_param("dataset_family", selected_ensemble.get("dataset_family", "unknown"))
        mlflow.log_param("review_threshold", config["thresholds"]["decision"]["review"])
        mlflow.log_param("block_threshold", config["thresholds"]["decision"]["block"])
        for model_name, weight in selected_ensemble["weights"].items():
            mlflow.log_param(f"weight_{model_name}", weight)

        mlflow.log_artifact(CONFIG_PATH, artifact_path="config")
        for key, raw_path in config["artifact_paths"].items():
            if key == "runtime_root":
                continue
            path = PROJECT_ROOT / raw_path
            if path.exists():
                mlflow.log_artifact(path, artifact_path=f"runtime/{key}")

        _log_json_artifact(
            "model_metadata.json",
            {
                "pipeline_profile": config["default_pipeline_profile"],
                "selected_ensemble": selected_ensemble,
                "thresholds": config["thresholds"],
                "artifact_paths": config["artifact_paths"],
            },
        )

        print(json.dumps({"mlflow_run_id": run.info.run_id, "artifact_uri": run.info.artifact_uri}))

    return 0


if __name__ == "__main__":
    os.environ.setdefault("MLFLOW_ENABLED", "true")
    raise SystemExit(main())
