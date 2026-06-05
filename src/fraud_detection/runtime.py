"""Production scoring runtime that wraps the existing end_to_end ensemble."""

from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
from typing import Any

from end_to_end.feedback_store import FeedbackStore
from end_to_end.monitoring import PipelineMonitor
from end_to_end.pipeline import (
    CONFIG_PATH,
    INPUT_SCHEMA_PATH,
    OUTPUT_SCHEMA_PATH,
    FraudPipeline,
    load_json,
)

from .config import get_settings
from .mlflow_tracking import MLflowTracker
from .state import HistoricalStateStore, build_default_state_store


def _review_threshold(config: dict[str, Any]) -> float:
    return float(config["thresholds"]["decision"]["review"])


def _build_model_scores_overview(model_scores: dict[str, float]) -> dict[str, float]:
    return {
        "LightGBM": float(model_scores["lightgbm"]),
        "AdaBoost": float(model_scores["adaboost"]),
        "Event_GNN": float(model_scores["event_gnn"]),
    }


def _build_explanation_summary(model_scores: dict[str, float], review_threshold: float) -> dict[str, str]:
    lightgbm_high = float(model_scores["lightgbm"]) >= review_threshold
    adaboost_high = float(model_scores["adaboost"]) >= review_threshold
    event_gnn_high = float(model_scores["event_gnn"]) >= review_threshold

    tabular_high_count = int(lightgbm_high) + int(adaboost_high)
    if tabular_high_count == 2:
        tabular_signal = "high"
    elif tabular_high_count == 1:
        tabular_signal = "medium"
    else:
        tabular_signal = "low"

    graph_signal = "high" if event_gnn_high else "low"

    if tabular_high_count == 2 and event_gnn_high:
        main_risk_source = "agreement_between_tabular_and_graph_models"
        reason = "All selected models assign elevated risk to this transaction."
    elif tabular_high_count >= 1 and not event_gnn_high:
        main_risk_source = "tabular_models_drive_risk"
        reason = "Risk mainly comes from transaction attributes and history aggregates."
    elif tabular_high_count == 0 and event_gnn_high:
        main_risk_source = "graph_model_drives_risk"
        reason = "Risk mainly comes from relational or event-context behavior."
    else:
        main_risk_source = "mixed_model_signals"
        reason = "Model signals are mixed and the case may require manual review."

    return {
        "main_risk_source": main_risk_source,
        "tabular_signal": tabular_signal,
        "graph_signal": graph_signal,
        "reason": reason,
    }


def _augment_explanations(output: dict[str, Any]) -> dict[str, Any]:
    explanations = deepcopy(output["explanations"])
    state_status = output["required_state_status"]
    warning: str | None = None
    if not state_status["history_available"] and not state_status["graph_context_available"]:
        warning = "Historical and graph context are unavailable for this case."
    elif not state_status["history_available"]:
        warning = "Historical account context is limited for this case."
    elif not state_status["graph_context_available"]:
        warning = "Graph context is limited for this case."

    explanations["state_availability"] = {
        "history_available": state_status["history_available"],
        "graph_context_available": state_status["graph_context_available"],
        "warning": warning,
    }
    return explanations


class ProductionScoringRuntime:
    """Wrapper around the validated v1 fraud ensemble."""

    def __init__(self, state_store: HistoricalStateStore | None = None, bootstrap_history: bool | None = None) -> None:
        settings = get_settings()
        self._settings = settings
        self._mlflow_tracker = MLflowTracker(settings)
        bootstrap = settings.bootstrap_history if bootstrap_history is None else bootstrap_history
        resolved_state_store = state_store or build_default_state_store()
        self.pipeline = FraudPipeline(
            state_store=resolved_state_store,
            monitor=PipelineMonitor(),
            feedback_store=FeedbackStore(),
            bootstrap_history=bootstrap,
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return load_json(INPUT_SCHEMA_PATH)

    @property
    def output_schema(self) -> dict[str, Any]:
        return load_json(OUTPUT_SCHEMA_PATH)

    @property
    def config(self) -> dict[str, Any]:
        return load_json(CONFIG_PATH)

    def align_output(self, output: dict[str, Any]) -> dict[str, Any]:
        aligned = deepcopy(output)
        review_threshold = _review_threshold(self.config)
        model_scores = aligned["model_scores"]

        aligned["fraud_score"] = float(aligned["final_risk_score"])
        aligned["threshold"] = review_threshold
        aligned["model_scores_overview"] = _build_model_scores_overview(model_scores)
        aligned["explanation_summary"] = _build_explanation_summary(model_scores, review_threshold)
        aligned["model_tracking"] = self._mlflow_tracker.current_model_metadata(self.config_snapshot()).as_output_payload()
        return aligned

    def score_transaction(self, payload: dict[str, Any], persist_event: bool = True) -> dict[str, Any]:
        output = self.pipeline.score_transaction(payload, persist_event=persist_event)
        output["explanations"] = _augment_explanations(output)
        return self.align_output(output)

    def config_snapshot(self) -> dict[str, Any]:
        config = self.config
        return {
            "default_pipeline_profile": config["default_pipeline_profile"],
            "selected_ensemble": config["selected_ensemble"],
            "thresholds": config["thresholds"],
        }


@lru_cache
def get_runtime() -> ProductionScoringRuntime:
    return ProductionScoringRuntime()
