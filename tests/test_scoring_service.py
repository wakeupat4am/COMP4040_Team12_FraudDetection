import json
from pathlib import Path

import jsonschema
import pytest

from fraud_detection.scoring import (
    combine_scores,
    determine_decision,
    determine_risk_bucket,
    load_pipeline_config,
    score_payload,
    validate_request,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_validate_request_rejects_unknown_fields():
    with pytest.raises(ValueError, match="Unknown input fields"):
        validate_request(
            {
                "event_id": "evt-1",
                "event_time": 1.0,
                "source_id": "u-1",
                "target_id": "m-1",
                "amount": 10.0,
                "location_id": "loc-1",
                "type_id": "purchase",
                "dataset_family": "ssfd",
                "unexpected": True,
            }
        )


def test_combine_scores_uses_weighted_average():
    config = load_pipeline_config()
    score = combine_scores(
        {"event_gnn": 0.8, "adaboost": 0.5, "lightgbm": 0.2},
        config,
    )
    assert score == pytest.approx(0.61)


def test_bucket_and_decision_mapping_follow_thresholds():
    config = load_pipeline_config()
    assert determine_risk_bucket(0.10, config) == "low"
    assert determine_risk_bucket(0.50, config) == "high"
    assert determine_risk_bucket(0.80, config) == "critical"
    assert determine_decision(0.40, config) == "allow"
    assert determine_decision(0.50, config) == "review"
    assert determine_decision(0.85, config) == "block"


def test_score_payload_matches_base_output_schema():
    schema = json.loads((PROJECT_ROOT / "end_to_end" / "output_schema.json").read_text(encoding="utf-8"))
    payload = {
        "event_id": "evt-schema",
        "event_time": 2.0,
        "source_id": "source-a",
        "target_id": "target-a",
        "amount": 245.0,
        "location_id": "loc-7",
        "type_id": "transfer",
        "dataset_family": "ssfd",
        "raw_attributes": {
            "history_available": False,
            "graph_context_available": True,
        },
    }

    result = score_payload(payload)

    jsonschema.validate(instance=result, schema=schema)
    assert result["explanation_stub"]["top_contributors"]
    assert (
        result["explanation_stub"]["state_availability"]["history_summary"]
        == "Historical features missing; score should be treated as lower-confidence."
    )
