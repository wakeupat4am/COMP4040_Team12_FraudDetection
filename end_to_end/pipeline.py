"""End-to-end fraud scoring pipeline with real SSFD ensemble inference."""

from __future__ import annotations

import json
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .event_gnn_inference import EventGNNInferenceEngine
from .explanations import build_event_context_explanation, build_tabular_explanations
from .feature_builder import build_features
from .feedback_store import FeedbackStore
from .monitoring import PipelineMonitor
from .state_store import InMemoryStateStore, TransactionEvent
from .tabular_inference import TabularInferenceEngine


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = PROJECT_ROOT / "end_to_end" / "pipeline_config.json"
INPUT_SCHEMA_PATH = PROJECT_ROOT / "end_to_end" / "input_schema.json"
OUTPUT_SCHEMA_PATH = PROJECT_ROOT / "end_to_end" / "output_schema.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_request(payload: dict[str, Any]) -> TransactionEvent:
    schema = load_json(INPUT_SCHEMA_PATH)
    required = schema["required"]
    missing = [field for field in required if field not in payload]
    if missing:
        raise ValueError(f"Missing required input fields: {missing}")
    if payload["amount"] < 0:
        raise ValueError("amount must be non-negative")
    return TransactionEvent(**payload)


def determine_risk_bucket(score: float, config: dict[str, Any]) -> str:
    thresholds = config["thresholds"]["risk_bucket"]
    if score >= thresholds["high"]:
        return "critical"
    if score >= thresholds["medium"]:
        return "high"
    if score >= thresholds["low"]:
        return "medium"
    return "low"


def determine_decision(score: float, config: dict[str, Any]) -> str:
    thresholds = config["thresholds"]["decision"]
    if score >= thresholds["block"]:
        return "block"
    if score >= thresholds["review"]:
        return "review"
    return "allow"


def combine_scores(model_scores: dict[str, float], config: dict[str, Any]) -> float:
    weights = config["selected_ensemble"]["weights"]
    weighted_sum = 0.0
    total = 0.0
    for model_name, weight in weights.items():
        weighted_sum += model_scores[model_name] * weight
        total += weight
    return weighted_sum / total if total else 0.0


class FraudPipeline:
    def __init__(
        self,
        state_store: InMemoryStateStore | None = None,
        monitor: PipelineMonitor | None = None,
        feedback_store: FeedbackStore | None = None,
        bootstrap_history: bool = True,
    ) -> None:
        self.config = load_json(CONFIG_PATH)
        self.state_store = state_store or InMemoryStateStore()
        if bootstrap_history and self.state_store.total_events == 0:
            self.state_store.bootstrap_from_ssfd_history()
        self.monitor = monitor or PipelineMonitor()
        self.feedback_store = feedback_store or FeedbackStore()
        self.tabular_engine = TabularInferenceEngine()
        self.event_engine = EventGNNInferenceEngine()

    def score_transaction(self, payload: dict[str, Any], persist_event: bool = True) -> dict[str, Any]:
        start = time.perf_counter()
        request = validate_request(payload)
        built = build_features(request, self.state_store)
        tabular_scores = self.tabular_engine.score(built.tabular_features)
        event_scores = self.event_engine.score(built.event_context_frame)

        calibrated_scores = {
            "event_gnn": event_scores["event_gnn"],
            "adaboost": tabular_scores["adaboost"],
            "lightgbm": tabular_scores["lightgbm"],
        }
        final_score = combine_scores(calibrated_scores, self.config)
        output = {
            "transaction_id": request.transaction_id,
            "pipeline_profile": self.config["selected_ensemble"]["name"],
            "final_risk_score": final_score,
            "risk_bucket": determine_risk_bucket(final_score, self.config),
            "decision": determine_decision(final_score, self.config),
            "model_scores": calibrated_scores,
            "required_state_status": built.state_status,
            "routing_metadata": {
                "base_models": self.config["selected_ensemble"]["base_models"],
                "operating_threshold": self.config["selected_ensemble"]["operating_threshold"],
                "raw_model_scores": {
                    "event_gnn": event_scores["event_gnn_raw"],
                    "adaboost": tabular_scores["adaboost_raw"],
                    "lightgbm": tabular_scores["lightgbm_raw"],
                },
            },
            "explanations": {
                "tabular_risk_factors": build_tabular_explanations(built.tabular_features),
                "event_context_summary": build_event_context_explanation(
                    context_rows=event_scores["context_graph_rows"],
                    sender_history_size=len(self.state_store.get_sender_history(request.sender_id)),
                    receiver_history_size=len(self.state_store.get_receiver_history(request.receiver_id)),
                ),
            },
        }
        missing = [field for field in load_json(OUTPUT_SCHEMA_PATH)["required"] if field not in output]
        if missing:
            raise RuntimeError(f"Generated output is missing required fields: {missing}")

        if persist_event:
            self.state_store.add_transaction(request)

        latency_ms = (time.perf_counter() - start) * 1000.0
        self.monitor.log(
            {
                "transaction_id": request.transaction_id,
                "latency_ms": latency_ms,
                "decision": output["decision"],
                "final_risk_score": output["final_risk_score"],
                "history_available": built.state_status["history_available"],
                "graph_context_available": built.state_status["graph_context_available"],
            }
        )
        return output

    def record_feedback(self, transaction_id: str, analyst_override: str, confirmed_label: int | None, reviewed_timestamp: str) -> None:
        self.feedback_store.append(
            {
                "transaction_id": transaction_id,
                "analyst_override": analyst_override,
                "confirmed_label": confirmed_label,
                "reviewed_timestamp": reviewed_timestamp,
            }
        )


def build_default_pipeline() -> FraudPipeline:
    return FraudPipeline()


def demo() -> None:
    example = load_json(PROJECT_ROOT / "end_to_end" / "example_input.json")
    pipeline = build_default_pipeline()
    output = pipeline.score_transaction(example, persist_event=False)
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    demo()
