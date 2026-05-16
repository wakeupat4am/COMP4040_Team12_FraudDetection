from fastapi.testclient import TestClient

from fraud_detection.api.app import create_app
from fraud_detection.api.repository import SQLAlchemyCaseRepository


def build_client(tmp_path) -> TestClient:
    database_url = f"sqlite:///{tmp_path / 'fraud_ops.db'}"
    repository = SQLAlchemyCaseRepository.from_database_url(database_url)
    repository.init_schema()
    return TestClient(create_app(repository=repository))


def test_score_endpoint_persists_and_returns_case(tmp_path):
    client = build_client(tmp_path)

    response = client.post(
        "/score",
        json={
            "event_id": "evt-100",
            "event_time": 1.0,
            "source_id": "user-1",
            "target_id": "merchant-4",
            "amount": 875.0,
            "location_id": "loc-2",
            "type_id": "purchase",
            "dataset_family": "ssfd",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["event_id"] == "evt-100"
    assert body["status"] == "scored"
    assert body["explanation_stub"]["top_contributors"]

    queue_response = client.get("/cases")
    assert queue_response.status_code == 200
    queue_body = queue_response.json()
    assert queue_body["total"] == 1
    assert queue_body["page"] == 1
    assert queue_body["items"][0]["event_id"] == "evt-100"

    detail_response = client.get("/cases/evt-100")
    assert detail_response.status_code == 200
    assert detail_response.json()["event_id"] == "evt-100"


def test_score_endpoint_rejects_invalid_payload(tmp_path):
    client = build_client(tmp_path)

    response = client.post(
        "/score",
        json={
            "event_id": "evt-101",
            "event_time": 1.0,
            "source_id": "user-1",
            "target_id": "merchant-4",
            "amount": -1.0,
            "location_id": "loc-2",
            "type_id": "purchase",
            "dataset_family": "ssfd",
        },
    )

    assert response.status_code == 422


def test_list_cases_returns_empty_state(tmp_path):
    client = build_client(tmp_path)

    response = client.get("/cases")
    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0, "page": 1, "page_size": 20}


def test_get_case_returns_not_found(tmp_path):
    client = build_client(tmp_path)

    response = client.get("/cases/missing-event")
    assert response.status_code == 404
    assert response.json()["detail"] == "Case 'missing-event' was not found."


def test_rescore_decision_and_metrics_flow(tmp_path):
    client = build_client(tmp_path)

    for payload in (
        {
            "event_id": "evt-high",
            "event_time": 1.0,
            "source_id": "user-1",
            "target_id": "merchant-4",
            "amount": 875.0,
            "location_id": "loc-2",
            "type_id": "purchase",
            "dataset_family": "ssfd",
        },
        {
            "event_id": "evt-low",
            "event_time": 2.0,
            "source_id": "user-2",
            "target_id": "merchant-9",
            "amount": 10.0,
            "location_id": "loc-1",
            "type_id": "cashout",
            "dataset_family": "paysim",
        },
    ):
        assert client.post("/score", json=payload).status_code == 201

    decision_response = client.post(
        "/cases/evt-high/decision",
        json={
            "event_id": "evt-high",
            "analyst_decision": "block",
            "note": "Confirmed suspicious pattern",
        },
    )
    assert decision_response.status_code == 200
    assert decision_response.json()["status"] == "reviewed"

    rescore_response = client.post("/score/rescore/evt-high")
    assert rescore_response.status_code == 200
    assert rescore_response.json()["event_id"] == "evt-high"

    filtered_queue = client.get("/cases", params={"dataset_family": "ssfd", "page_size": 1})
    assert filtered_queue.status_code == 200
    assert filtered_queue.json()["total"] == 1
    assert filtered_queue.json()["items"][0]["event_id"] == "evt-high"

    metrics_response = client.get("/metrics/summary")
    assert metrics_response.status_code == 200
    metrics_body = metrics_response.json()
    assert metrics_body["total_cases"] == 2
    assert metrics_body["reviewed_cases"] == 1


def test_decision_endpoint_rejects_mismatched_event_id(tmp_path):
    client = build_client(tmp_path)

    assert client.post(
        "/score",
        json={
            "event_id": "evt-200",
            "event_time": 1.0,
            "source_id": "user-1",
            "target_id": "merchant-4",
            "amount": 100.0,
            "location_id": "loc-2",
            "type_id": "purchase",
            "dataset_family": "ssfd",
        },
    ).status_code == 201

    response = client.post(
        "/cases/evt-200/decision",
        json={
            "event_id": "evt-other",
            "analyst_decision": "review",
            "note": "Check identity match",
        },
    )
    assert response.status_code == 400
