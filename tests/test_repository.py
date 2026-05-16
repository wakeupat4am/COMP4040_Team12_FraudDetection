from fraud_detection.api.repository import SQLAlchemyCaseRepository


def build_repository(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'repo.db'}"
    repository = SQLAlchemyCaseRepository.from_database_url(database_url)
    repository.init_schema()
    return repository


def test_repository_persists_and_fetches_case(tmp_path):
    repository = build_repository(tmp_path)
    payload = {
        "event_id": "evt-1",
        "dataset_family": "ssfd",
        "final_risk_score": 0.77,
        "risk_bucket": "critical",
        "decision": "review",
        "model_scores": {"event_gnn": 0.8, "adaboost": 0.7, "lightgbm": 0.6, "hetero_gnn_shadow": None},
        "required_state_status": {"history_available": True, "graph_context_available": True},
        "routing_metadata": {"selected_ensemble": "test", "base_models": ["event_gnn", "adaboost", "lightgbm"]},
        "explanation_stub": {"summary": "test", "top_contributors": [], "state_availability": {}, "evidence_panels": []},
    }

    repository.save_scored_case({"event_id": "evt-1"}, payload)
    fetched = repository.get_case("evt-1")

    assert fetched is not None
    assert fetched.event_id == "evt-1"
    assert fetched.score_payload["final_risk_score"] == 0.77


def test_repository_updates_decision_and_metrics(tmp_path):
    repository = build_repository(tmp_path)
    payload = {
        "event_id": "evt-2",
        "dataset_family": "ssfd",
        "final_risk_score": 0.55,
        "risk_bucket": "high",
        "decision": "review",
        "model_scores": {"event_gnn": 0.5, "adaboost": 0.6, "lightgbm": 0.55, "hetero_gnn_shadow": None},
        "required_state_status": {"history_available": True, "graph_context_available": True},
        "routing_metadata": {"selected_ensemble": "test", "base_models": ["event_gnn", "adaboost", "lightgbm"]},
        "explanation_stub": {"summary": "test", "top_contributors": [], "state_availability": {}, "evidence_panels": []},
    }

    repository.save_scored_case({"event_id": "evt-2"}, payload)
    updated = repository.update_case_decision("evt-2", "block", "Manual confirmation")

    assert updated is not None
    assert updated.current_analyst_decision == "block"
    assert updated.status == "reviewed"

    metrics = repository.get_metrics_summary()
    assert metrics.total_cases == 1
    assert metrics.reviewed_cases == 1


def test_repository_rescores_existing_case(tmp_path):
    repository = build_repository(tmp_path)
    original_request = {
        "event_id": "evt-3",
        "event_time": 1.0,
        "source_id": "user-1",
        "target_id": "merchant-1",
        "amount": 5.0,
        "location_id": "loc-1",
        "type_id": "purchase",
        "dataset_family": "ssfd",
    }
    first_payload = {
        "event_id": "evt-3",
        "dataset_family": "ssfd",
        "final_risk_score": 0.10,
        "risk_bucket": "low",
        "decision": "allow",
        "model_scores": {"event_gnn": 0.1, "adaboost": 0.1, "lightgbm": 0.1, "hetero_gnn_shadow": None},
        "required_state_status": {"history_available": True, "graph_context_available": True},
        "routing_metadata": {"selected_ensemble": "test", "base_models": ["event_gnn", "adaboost", "lightgbm"]},
        "explanation_stub": {"summary": "first", "top_contributors": [], "state_availability": {}, "evidence_panels": []},
    }
    rescored_payload = {
        **first_payload,
        "final_risk_score": 0.85,
        "risk_bucket": "critical",
        "decision": "block",
    }

    repository.save_scored_case(original_request, first_payload)
    rescored = repository.rescore_case("evt-3", rescored_payload)

    assert rescored is not None
    assert rescored.score_payload["final_risk_score"] == 0.85
    assert repository.get_request_payload("evt-3") == original_request
