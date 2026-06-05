"""MLflow tracking helpers for production model metadata."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .config import Settings


@dataclass(frozen=True)
class ModelTrackingMetadata:
    run_id: str | None
    artifact_uri: str | None
    metadata: dict[str, Any]

    def as_output_payload(self) -> dict[str, Any]:
        return {
            "mlflow_run_id": self.run_id,
            "model_artifact_uri": self.artifact_uri,
            "model_metadata": self.metadata,
        }


class MLflowTracker:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._configured = False

    @property
    def enabled(self) -> bool:
        return self.settings.mlflow_enabled

    def configure(self) -> bool:
        if not self.enabled:
            return False
        if self._configured:
            return True

        try:
            import mlflow
        except ImportError:
            return False

        mlflow.set_tracking_uri(self.settings.mlflow_tracking_uri)
        mlflow.set_experiment(self.settings.mlflow_experiment_name)
        self._configured = True
        return True

    def current_model_metadata(self, runtime_config: dict[str, Any]) -> ModelTrackingMetadata:
        artifact_uri = None
        if self.configure() and self.settings.mlflow_model_run_id:
            try:
                import mlflow

                run = mlflow.get_run(self.settings.mlflow_model_run_id)
                artifact_uri = run.info.artifact_uri
            except Exception:
                artifact_uri = None

        metadata = {
            "experiment_name": self.settings.mlflow_experiment_name,
            "tracking_uri": self.settings.mlflow_tracking_uri if self.enabled else None,
            "pipeline_profile": runtime_config["default_pipeline_profile"],
            "selected_ensemble": runtime_config["selected_ensemble"],
            "thresholds": runtime_config["thresholds"],
        }
        return ModelTrackingMetadata(
            run_id=self.settings.mlflow_model_run_id if self.enabled else None,
            artifact_uri=artifact_uri,
            metadata=metadata,
        )
