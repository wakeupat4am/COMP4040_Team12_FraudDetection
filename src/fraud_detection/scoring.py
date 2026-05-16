"""Reusable scoring service for the fraud-operations backend."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
END_TO_END_DIR = PROJECT_ROOT / "end_to_end"
CONFIG_PATH = END_TO_END_DIR / "pipeline_config.json"
INPUT_SCHEMA_PATH = END_TO_END_DIR / "input_schema.json"
OUTPUT_SCHEMA_PATH = END_TO_END_DIR / "output_schema.json"

VALID_DATASET_FAMILIES = {"ssfd", "paysim"}


@dataclass(slots=True)
class TransactionRequest:
    """Validated input payload for fraud scoring."""

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


def load_input_schema() -> dict[str, Any]:
    return load_json(INPUT_SCHEMA_PATH)


def load_output_schema() -> dict[str, Any]:
    return load_json(OUTPUT_SCHEMA_PATH)


def load_pipeline_config() -> dict[str, Any]:
    return load_json(CONFIG_PATH)


def validate_request(payload: dict[str, Any]) -> TransactionRequest:
    """Validate the inbound payload against the shared scoring contract."""
    schema = load_input_schema()
    required = schema["required"]
    properties = schema["properties"]

    missing = [field for field in required if field not in payload]
    if missing:
        raise ValueError(f"Missing required input fields: {missing}")

    unknown = sorted(set(payload) - set(properties))
    if unknown:
        raise ValueError(f"Unknown input fields: {unknown}")

    if not isinstance(payload["event_id"], str) or not payload["event_id"].strip():
        raise ValueError("event_id must be a non-empty string")
    if not isinstance(payload["dataset_family"], str):
        raise ValueError("dataset_family must be a string")
    if payload["dataset_family"] not in VALID_DATASET_FAMILIES:
        raise ValueError("dataset_family must be either 'ssfd' or 'paysim'")
    if payload["amount"] < 0:
        raise ValueError("amount must be non-negative")

    raw_attributes = payload.get("raw_attributes")
    if raw_attributes is not None and not isinstance(raw_attributes, dict):
        raise ValueError("raw_attributes must be an object when provided")

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


def _stable_unit_interval(*values: object) -> float:
    seed = "|".join(str(value) for value in values)
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) / 0xFFFFFFFF


def generate_placeholder_model_scores(request: TransactionRequest) -> dict[str, float]:
    """Return deterministic placeholder scores until model serving is connected."""
    amount_signal = min(request.amount / 1000.0, 1.0)
    graph_signal = _stable_unit_interval(
        request.source_id,
        request.target_id,
        request.location_id,
    )
    type_signal = _stable_unit_interval(request.type_id, request.dataset_family)
    time_signal = _stable_unit_interval(request.event_id, request.event_time)

    event_gnn = min(max(0.35 * amount_signal + 0.45 * graph_signal + 0.20 * time_signal, 0.0), 1.0)
    adaboost = min(max(0.45 * amount_signal + 0.35 * type_signal + 0.20 * time_signal, 0.0), 1.0)
    lightgbm = min(max(0.40 * amount_signal + 0.25 * graph_signal + 0.35 * type_signal, 0.0), 1.0)

    return {
        "event_gnn": round(event_gnn, 6),
        "adaboost": round(adaboost, 6),
        "lightgbm": round(lightgbm, 6),
        "hetero_gnn_shadow": None,
    }


def resolve_state_availability(request: TransactionRequest) -> dict[str, bool]:
    raw_attributes = request.raw_attributes or {}
    return {
        "history_available": bool(raw_attributes.get("history_available", True)),
        "graph_context_available": bool(raw_attributes.get("graph_context_available", True)),
    }


def build_explanation_payload(
    request: TransactionRequest,
    model_scores: dict[str, float],
    final_score: float,
    state_status: dict[str, bool],
) -> dict[str, Any]:
    amount_contribution = min(request.amount / 5000.0, 1.0)
    type_contribution = _stable_unit_interval(request.type_id)
    graph_contribution = model_scores["event_gnn"]

    contributors = [
        {
            "feature": "amount",
            "direction": "increase",
            "magnitude": round(amount_contribution, 4),
            "summary": f"Transaction amount {request.amount:.2f} materially affects the risk score.",
        },
        {
            "feature": "transaction_type",
            "direction": "increase",
            "magnitude": round(type_contribution, 4),
            "summary": f"Transaction type '{request.type_id}' maps to a higher-risk pattern bucket.",
        },
        {
            "feature": "graph_relationships",
            "direction": "increase",
            "magnitude": round(graph_contribution, 4),
            "summary": "Graph-model placeholder indicates suspicious source-target relationship structure.",
        },
    ]

    return {
        "summary": (
            f"Final risk score {final_score:.3f} assembled from weighted placeholder model outputs "
            "until live model inference is connected."
        ),
        "top_contributors": contributors,
        "state_availability": {
            "history_available": state_status["history_available"],
            "graph_context_available": state_status["graph_context_available"],
            "history_summary": (
                "Historical features available for scoring."
                if state_status["history_available"]
                else "Historical features missing; score should be treated as lower-confidence."
            ),
            "graph_summary": (
                "Graph context available for relationship scoring."
                if state_status["graph_context_available"]
                else "Graph context missing; graph evidence is incomplete."
            ),
        },
        "evidence_panels": [
            {
                "panel": "tabular",
                "title": "Top tabular contributors",
                "items": [item["summary"] for item in contributors[:2]],
            },
            {
                "panel": "graph",
                "title": "Relationship context",
                "items": [
                    contributors[2]["summary"],
                    "Detailed subgraph evidence will replace this placeholder in a later phase.",
                ],
            },
        ],
    }


def build_output(
    request: TransactionRequest,
    model_scores: dict[str, float],
    history_available: bool,
    graph_context_available: bool,
) -> dict[str, Any]:
    config = load_pipeline_config()
    final_score = round(combine_scores(model_scores, config), 6)
    state_status = {
        "history_available": history_available,
        "graph_context_available": graph_context_available,
    }
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
        "required_state_status": state_status,
        "routing_metadata": {
            "selected_ensemble": config["selected_ensemble"]["name"],
            "base_models": config["selected_ensemble"]["base_models"],
        },
        "explanation_stub": build_explanation_payload(
            request=request,
            model_scores=model_scores,
            final_score=final_score,
            state_status=state_status,
        ),
    }

    output_schema = load_output_schema()
    missing = [field for field in output_schema["required"] if field not in output]
    if missing:
        raise RuntimeError(f"Generated output is missing required fields: {missing}")
    return output


def score_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate and score a single fraud event payload."""
    request = validate_request(payload)
    model_scores = generate_placeholder_model_scores(request)
    state_status = resolve_state_availability(request)
    return build_output(
        request=request,
        model_scores=model_scores,
        history_available=state_status["history_available"],
        graph_context_available=state_status["graph_context_available"],
    )


def request_to_dict(request: TransactionRequest) -> dict[str, Any]:
    """Return a serializable version of the validated request."""
    return asdict(request)
