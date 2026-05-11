"""End-to-end pipeline contract and score orchestration skeleton."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = PROJECT_ROOT / "end_to_end" / "pipeline_config.json"
INPUT_SCHEMA_PATH = PROJECT_ROOT / "end_to_end" / "input_schema.json"
OUTPUT_SCHEMA_PATH = PROJECT_ROOT / "end_to_end" / "output_schema.json"


@dataclass
class TransactionRequest:
    event_id: str
    event_time: float
    source_id: str
    target_id: str
    amount: float
    location_id: str
    type_id: str
    dataset_family: str
    raw_attributes: dict[str, Any] | None = None


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_request(payload: dict[str, Any]) -> TransactionRequest:
    schema = load_json(INPUT_SCHEMA_PATH)
    required = schema["required"]
    missing = [field for field in required if field not in payload]
    if missing:
        raise ValueError(f"Missing required input fields: {missing}")

    if payload["amount"] < 0:
        raise ValueError("amount must be non-negative")
    if payload["dataset_family"] not in {"ssfd", "paysim"}:
        raise ValueError("dataset_family must be either 'ssfd' or 'paysim'")

    return TransactionRequest(**payload)


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


def build_output(
    request: TransactionRequest,
    model_scores: dict[str, float],
    history_available: bool,
    graph_context_available: bool,
) -> dict[str, Any]:
    config = load_json(CONFIG_PATH)
    final_score = combine_scores(model_scores, config)
    output = {
        "event_id": request.event_id,
        "dataset_family": request.dataset_family,
        "final_risk_score": final_score,
        "risk_bucket": determine_risk_bucket(final_score, config),
        "decision": determine_decision(final_score, config),
        "model_scores": {
            "event_gnn": model_scores["event_gnn"],
            "adaboost": model_scores["adaboost"],
            "lightgbm": model_scores["lightgbm"],
            "hetero_gnn_shadow": model_scores.get("hetero_gnn_shadow"),
        },
        "required_state_status": {
            "history_available": history_available,
            "graph_context_available": graph_context_available,
        },
        "routing_metadata": {
            "selected_ensemble": config["selected_ensemble"]["name"],
            "base_models": config["selected_ensemble"]["base_models"],
        },
        "explanation_stub": {
            "tabular_explanation_status": "pending",
            "event_graph_explanation_status": "pending",
            "history_window_status": "pending",
        },
    }

    # Minimal output contract check against required fields.
    output_schema = load_json(OUTPUT_SCHEMA_PATH)
    missing = [field for field in output_schema["required"] if field not in output]
    if missing:
        raise RuntimeError(f"Generated output is missing required fields: {missing}")
    return output


def demo() -> None:
    example = load_json(PROJECT_ROOT / "end_to_end" / "example_input.json")
    request = validate_request(example)

    # Placeholder scores until live calibrated inference is connected.
    output = build_output(
        request=request,
        model_scores={
            "event_gnn": 0.82,
            "adaboost": 0.74,
            "lightgbm": 0.61,
            "hetero_gnn_shadow": None,
        },
        history_available=True,
        graph_context_available=True,
    )
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    demo()
