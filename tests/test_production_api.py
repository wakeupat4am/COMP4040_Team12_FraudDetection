from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from fraud_detection.api import create_app
from fraud_detection.config import Settings


class FakeScoringRuntime:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def _align_output(self, output: dict[str, object]) -> dict[str, object]:
        review_threshold = 0.6
        model_scores = output["model_scores"]
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

        output["fraud_score"] = output["final_risk_score"]
        output["threshold"] = review_threshold
        output["model_scores_overview"] = {
            "LightGBM": float(model_scores["lightgbm"]),
            "AdaBoost": float(model_scores["adaboost"]),
            "Event_GNN": float(model_scores["event_gnn"]),
        }
        output["explanation_summary"] = {
            "main_risk_source": main_risk_source,
            "tabular_signal": tabular_signal,
            "graph_signal": graph_signal,
            "reason": reason,
        }
        return output

    def align_output(self, output: dict[str, object]) -> dict[str, object]:
        return self._align_output(dict(output))

    def score_transaction(self, payload: dict[str, object], persist_event: bool = True) -> dict[str, object]:
        self.calls.append({"payload": dict(payload), "persist_event": persist_event})
        amount = float(payload["amount"])
        override_scores = None
        raw_attributes = payload.get("raw_attributes")
        if isinstance(raw_attributes, dict):
            candidate = raw_attributes.get("override_model_scores")
            if isinstance(candidate, dict):
                override_scores = {
                    "event_gnn": float(candidate["event_gnn"]),
                    "adaboost": float(candidate["adaboost"]),
                    "lightgbm": float(candidate["lightgbm"]),
                }

        if override_scores is None:
            if persist_event:
                final_score = 0.85 if amount >= 100 else 0.55
            else:
                final_score = 0.42
            model_scores = {"event_gnn": final_score, "adaboost": 0.4, "lightgbm": 0.3}
        else:
            model_scores = override_scores
            final_score = 0.5 * model_scores["event_gnn"] + 0.3 * model_scores["adaboost"] + 0.2 * model_scores["lightgbm"]

        risk_bucket = "critical" if final_score >= 0.75 else "high" if final_score >= 0.5 else "low"
        decision = "block" if final_score >= 0.8 else "review" if final_score >= 0.6 else "allow"
        output = {
            "transaction_id": str(payload["transaction_id"]),
            "pipeline_profile": "test_profile",
            "final_risk_score": final_score,
            "risk_bucket": risk_bucket,
            "decision": decision,
            "model_scores": model_scores,
            "required_state_status": {"history_available": False, "graph_context_available": False},
            "routing_metadata": {"base_models": ["event_gnn", "adaboost", "lightgbm"], "operating_threshold": 0.6},
            "explanations": {
                "tabular_risk_factors": [{"feature": "amount_vs_source_mean", "value": amount, "direction": "higher_risk"}],
                "event_context_summary": [{"signal": "recent_event_context_size", "value": 0}],
                "state_availability": {
                    "history_available": False,
                    "graph_context_available": False,
                    "warning": "Historical and graph context are unavailable for this case.",
                },
            },
        }
        return self._align_output(output)

    def config_snapshot(self) -> dict[str, object]:
        return {
            "default_pipeline_profile": "test_profile",
            "selected_ensemble": {"name": "test_profile", "base_models": ["event_gnn", "adaboost", "lightgbm"]},
            "thresholds": {"decision": {"review": 0.6, "block": 0.8}},
        }


def build_client(tmp_path: Path) -> tuple[TestClient, FakeScoringRuntime, Settings]:
    runtime = FakeScoringRuntime()
    settings = Settings(
        database_url=f"sqlite:///{(tmp_path / 'fraud_ops.db').as_posix()}",
        auth_secret="test-secret",
        auth_token_ttl_seconds=3600,
        bootstrap_history=False,
        cors_allowed_origins=("http://localhost:3000",),
        analyst_username="analyst",
        analyst_password="analyst-pass",
        manager_username="admin",
        manager_password="admin-pass",
    )
    app = create_app(settings=settings, runtime=runtime)
    return TestClient(app), runtime, settings


def login(client: TestClient, username: str, password: str) -> str:
    response = client.post("/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200
    return response.json()["access_token"]


def sample_payload(transaction_id: str, amount: float = 150.0) -> dict[str, object]:
    return {
        "transaction_id": transaction_id,
        "transaction_timestamp": "2026-06-03T12:00:00Z",
        "sender_id": "sender-1",
        "receiver_id": "receiver-1",
        "amount": amount,
        "transaction_location": "VN-HCM",
        "transaction_type": "card_not_present",
        "currency": "USD",
        "channel": "web",
        "raw_attributes": {"device_id": "device-1"},
    }


def test_score_queue_detail_decision_and_rescore_flow(tmp_path: Path) -> None:
    client, runtime, settings = build_client(tmp_path)
    with client:
        analyst_token = login(client, settings.analyst_username, settings.analyst_password)
        headers = {"Authorization": f"Bearer {analyst_token}"}

        score_response = client.post("/score", json=sample_payload("tx-001"), headers=headers)
        assert score_response.status_code == 200
        score_body = score_response.json()
        assert score_body["transaction_id"] == "tx-001"
        assert score_body["review_status"] == "pending"
        assert score_body["latest_output"]["decision"] == "block"
        assert score_body["latest_output"]["fraud_score"] == score_body["latest_output"]["final_risk_score"]
        assert score_body["latest_output"]["threshold"] == 0.6
        assert score_body["latest_output"]["model_scores_overview"]["Event_GNN"] == 0.85
        assert score_body["latest_output"]["explanation_summary"]["main_risk_source"] == "graph_model_drives_risk"

        queue_response = client.get("/cases", headers=headers)
        assert queue_response.status_code == 200
        queue_body = queue_response.json()
        assert queue_body["total"] == 1
        assert queue_body["items"][0]["transaction_id"] == "tx-001"

        detail_response = client.get("/cases/tx-001", headers=headers)
        assert detail_response.status_code == 200
        detail_body = detail_response.json()
        assert detail_body["latest_output"]["transaction_id"] == "tx-001"
        assert detail_body["latest_output"]["fraud_score"] == detail_body["latest_output"]["final_risk_score"]
        assert "explanation_summary" not in detail_body["explanation_payload"]
        assert detail_body["feedback_history"] == []

        decision_response = client.post(
            "/cases/tx-001/decision",
            json={"analyst_decision": "review", "note": "Needs manual verification."},
            headers=headers,
        )
        assert decision_response.status_code == 200
        decision_body = decision_response.json()
        assert decision_body["review_status"] == "reviewed"
        assert decision_body["latest_analyst_decision"] == "review"
        assert decision_body["review_history"][0]["analyst_username"] == settings.analyst_username

        rescore_response = client.post("/cases/tx-001/rescore", headers=headers)
        assert rescore_response.status_code == 200
        rescore_body = rescore_response.json()
        assert rescore_body["review_status"] == "pending"
        assert rescore_body["latest_analyst_decision"] is None
        assert rescore_body["latest_output"]["final_risk_score"] == 0.42
        assert [call["persist_event"] for call in runtime.calls] == [True, False]


def test_case_filters_and_contracts_remain_compatible(tmp_path: Path) -> None:
    client, _, settings = build_client(tmp_path)
    input_schema = json.loads(Path("end_to_end/input_schema.json").read_text(encoding="utf-8"))
    output_schema = json.loads(Path("end_to_end/output_schema.json").read_text(encoding="utf-8"))

    with client:
        analyst_token = login(client, settings.analyst_username, settings.analyst_password)
        headers = {"Authorization": f"Bearer {analyst_token}"}
        low_amount_payload = sample_payload("tx-002", amount=20.0)
        high_amount_payload = sample_payload("tx-003", amount=200.0)

        assert set(input_schema["required"]).issubset(low_amount_payload.keys())
        assert client.post("/score", json=low_amount_payload, headers=headers).status_code == 200
        assert client.post("/score", json=high_amount_payload, headers=headers).status_code == 200

        filtered = client.get("/cases", headers=headers, params={"risk_bucket": "critical"})
        assert filtered.status_code == 200
        filtered_body = filtered.json()
        assert filtered_body["total"] == 1
        assert filtered_body["items"][0]["transaction_id"] == "tx-003"

        detail = client.get("/cases/tx-003", headers=headers)
        latest_output = detail.json()["latest_output"]
        assert set(output_schema["required"]).issubset(latest_output.keys())
        assert latest_output["threshold"] == 0.6
        assert latest_output["model_scores_overview"]["LightGBM"] == latest_output["model_scores"]["lightgbm"]


def test_score_request_aliases_are_accepted_and_normalized(tmp_path: Path) -> None:
    client, runtime, settings = build_client(tmp_path)
    with client:
        analyst_token = login(client, settings.analyst_username, settings.analyst_password)
        headers = {"Authorization": f"Bearer {analyst_token}"}
        aliased_payload = {
            "transaction_id": "tx-alias",
            "timestamp": "2026-06-03T12:00:00Z",
            "sender_id": "sender-1",
            "receiver_id": "receiver-1",
            "amount": 80.0,
            "location": "VN-HCM",
            "transaction_type": "card_not_present",
        }
        response = client.post("/score", json=aliased_payload, headers=headers)
        assert response.status_code == 200
        payload_seen_by_runtime = runtime.calls[0]["payload"]
        assert payload_seen_by_runtime["transaction_timestamp"] == aliased_payload["timestamp"]
        assert payload_seen_by_runtime["transaction_location"] == aliased_payload["location"]
        assert "timestamp" not in payload_seen_by_runtime
        assert "location" not in payload_seen_by_runtime


def test_conflicting_request_aliases_return_400(tmp_path: Path) -> None:
    client, _, settings = build_client(tmp_path)
    with client:
        analyst_token = login(client, settings.analyst_username, settings.analyst_password)
        headers = {"Authorization": f"Bearer {analyst_token}"}
        payload = sample_payload("tx-conflict")
        payload["timestamp"] = "2026-06-03T12:30:00Z"
        response = client.post("/score", json=payload, headers=headers)
        assert response.status_code == 400
        assert "Conflicting values" in str(response.json()["detail"])


def test_explanation_summary_patterns(tmp_path: Path) -> None:
    client, _, settings = build_client(tmp_path)
    with client:
        analyst_token = login(client, settings.analyst_username, settings.analyst_password)
        headers = {"Authorization": f"Bearer {analyst_token}"}
        scenarios = [
            (
                "tx-agreement",
                {"event_gnn": 0.9, "adaboost": 0.8, "lightgbm": 0.7},
                "agreement_between_tabular_and_graph_models",
                "high",
                "high",
            ),
            (
                "tx-tabular",
                {"event_gnn": 0.2, "adaboost": 0.8, "lightgbm": 0.7},
                "tabular_models_drive_risk",
                "high",
                "low",
            ),
            (
                "tx-graph",
                {"event_gnn": 0.9, "adaboost": 0.2, "lightgbm": 0.3},
                "graph_model_drives_risk",
                "low",
                "high",
            ),
            (
                "tx-mixed",
                {"event_gnn": 0.9, "adaboost": 0.2, "lightgbm": 0.7},
                "mixed_model_signals",
                "medium",
                "high",
            ),
        ]
        for transaction_id, override_scores, main_risk_source, tabular_signal, graph_signal in scenarios:
            payload = sample_payload(transaction_id)
            payload["raw_attributes"] = {"override_model_scores": override_scores}
            response = client.post("/score", json=payload, headers=headers)
            assert response.status_code == 200
            summary = response.json()["latest_output"]["explanation_summary"]
            assert summary["main_risk_source"] == main_risk_source
            assert summary["tabular_signal"] == tabular_signal
            assert summary["graph_signal"] == graph_signal


def test_metrics_require_manager_role(tmp_path: Path) -> None:
    client, _, settings = build_client(tmp_path)
    with client:
        analyst_token = login(client, settings.analyst_username, settings.analyst_password)
        analyst_headers = {"Authorization": f"Bearer {analyst_token}"}
        assert client.post("/score", json=sample_payload("tx-004"), headers=analyst_headers).status_code == 200

        analyst_metrics = client.get("/metrics/summary", headers=analyst_headers)
        assert analyst_metrics.status_code == 403

        admin_token = login(client, settings.manager_username, settings.manager_password)
        admin_headers = {"Authorization": f"Bearer {admin_token}"}
        admin_metrics = client.get("/metrics/summary", headers=admin_headers)
        assert admin_metrics.status_code == 200
        metrics_body = admin_metrics.json()
        assert metrics_body["total_cases"] == 1
        assert metrics_body["pending_review_cases"] == 1


def test_feedback_submission_and_feedback_history(tmp_path: Path) -> None:
    client, _, settings = build_client(tmp_path)
    with client:
        analyst_token = login(client, settings.analyst_username, settings.analyst_password)
        headers = {"Authorization": f"Bearer {analyst_token}"}
        assert client.post("/score", json=sample_payload("tx-005"), headers=headers).status_code == 200

        feedback_response = client.post(
            "/cases/tx-005/feedback",
            json={
                "confirmed_label": "fraud",
                "feedback_timestamp": "2026-06-03T18:00:00Z",
                "note": "Confirmed after manual investigation.",
            },
            headers=headers,
        )
        assert feedback_response.status_code == 200
        feedback_body = feedback_response.json()
        assert feedback_body["feedback_history"][0]["confirmed_label"] == "fraud"
        assert feedback_body["feedback_history"][0]["reviewer_username"] == settings.analyst_username
        assert feedback_body["feedback_history"][0]["note"] == "Confirmed after manual investigation."


def test_feedback_unknown_case_returns_404(tmp_path: Path) -> None:
    client, _, settings = build_client(tmp_path)
    with client:
        analyst_token = login(client, settings.analyst_username, settings.analyst_password)
        headers = {"Authorization": f"Bearer {analyst_token}"}
        response = client.post(
            "/cases/missing-case/feedback",
            json={"confirmed_label": "fraud", "feedback_timestamp": "2026-06-03T18:00:00Z"},
            headers=headers,
        )
        assert response.status_code == 404


def test_monitoring_summary_tracks_score_and_rescore_events(tmp_path: Path) -> None:
    client, _, settings = build_client(tmp_path)
    with client:
        analyst_token = login(client, settings.analyst_username, settings.analyst_password)
        analyst_headers = {"Authorization": f"Bearer {analyst_token}"}
        assert client.post("/score", json=sample_payload("tx-006"), headers=analyst_headers).status_code == 200
        assert client.post("/cases/tx-006/rescore", headers=analyst_headers).status_code == 200

        admin_token = login(client, settings.manager_username, settings.manager_password)
        admin_headers = {"Authorization": f"Bearer {admin_token}"}
        summary_response = client.get("/monitoring/summary", headers=admin_headers)
        assert summary_response.status_code == 200
        summary_body = summary_response.json()
        assert summary_body["total_events"] == 2
        assert summary_body["event_type_counts"] == {"score": 1, "rescore": 1}
        assert summary_body["average_latency_ms"] >= 0
        assert summary_body["average_latency_by_event_type"]["score"] >= 0
        assert summary_body["average_latency_by_event_type"]["rescore"] >= 0
        assert summary_body["latest_event_at"] is not None


def test_monitoring_summary_requires_manager_role(tmp_path: Path) -> None:
    client, _, settings = build_client(tmp_path)
    with client:
        analyst_token = login(client, settings.analyst_username, settings.analyst_password)
        analyst_headers = {"Authorization": f"Bearer {analyst_token}"}
        assert client.post("/score", json=sample_payload("tx-007"), headers=analyst_headers).status_code == 200
        response = client.get("/monitoring/summary", headers=analyst_headers)
        assert response.status_code == 403


def test_cors_allows_local_next_origin(tmp_path: Path) -> None:
    client, _, _ = build_client(tmp_path)
    with client:
        response = client.options(
            "/auth/login",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
            },
        )
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_startup_recovers_legacy_sqlite_without_password_hash(tmp_path: Path) -> None:
    database_path = tmp_path / "legacy_fraud_ops.db"
    connection = sqlite3.connect(database_path)
    try:
        connection.execute(
            """
            CREATE TABLE users (
                id INTEGER PRIMARY KEY,
                username TEXT NOT NULL UNIQUE,
                role TEXT NOT NULL,
                is_active BOOLEAN NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                last_login_at TEXT NULL
            )
            """
        )
        connection.commit()
    finally:
        connection.close()

    runtime = FakeScoringRuntime()
    settings = Settings(
        database_url=f"sqlite:///{database_path.as_posix()}",
        auth_secret="test-secret",
        auth_token_ttl_seconds=3600,
        bootstrap_history=False,
        cors_allowed_origins=("http://localhost:3000",),
        analyst_username="analyst",
        analyst_password="analyst-pass",
        manager_username="admin",
        manager_password="admin-pass",
    )

    app = create_app(settings=settings, runtime=runtime)
    with TestClient(app) as client:
        response = client.post("/auth/login", json={"username": "analyst", "password": "analyst-pass"})
        assert response.status_code == 200

    backup_candidates = sorted(tmp_path.glob("legacy_fraud_ops.legacy-*.db"))
    assert backup_candidates
