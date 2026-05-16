"""Seed sample fraud cases through the local FastAPI endpoint."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


API_BASE_URL = "http://127.0.0.1:8000"


@dataclass(frozen=True)
class SampleCase:
    event_id: str
    event_time: float
    source_id: str
    target_id: str
    amount: float
    location_id: str
    type_id: str
    dataset_family: str
    raw_attributes: dict[str, object] | None = None


SAMPLE_CASES = [
    SampleCase(
        event_id="evt-seed-001",
        event_time=1.0,
        source_id="user-001",
        target_id="merchant-009",
        amount=950.0,
        location_id="loc-sg-01",
        type_id="purchase",
        dataset_family="ssfd",
        raw_attributes={"history_available": True, "graph_context_available": True},
    ),
    SampleCase(
        event_id="evt-seed-002",
        event_time=2.0,
        source_id="user-002",
        target_id="merchant-011",
        amount=37.5,
        location_id="loc-sg-02",
        type_id="cashout",
        dataset_family="paysim",
        raw_attributes={"history_available": False, "graph_context_available": True},
    ),
    SampleCase(
        event_id="evt-seed-003",
        event_time=3.0,
        source_id="user-003",
        target_id="merchant-004",
        amount=420.0,
        location_id="loc-sg-01",
        type_id="transfer",
        dataset_family="ssfd",
        raw_attributes={"history_available": True, "graph_context_available": False},
    ),
]


def post_json(url: str, payload: dict[str, object]) -> dict[str, object]:
    request = Request(
        url=url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> int:
    base_url = sys.argv[1] if len(sys.argv) > 1 else API_BASE_URL
    for sample in SAMPLE_CASES:
        payload = {
            "event_id": sample.event_id,
            "event_time": sample.event_time,
            "source_id": sample.source_id,
            "target_id": sample.target_id,
            "amount": sample.amount,
            "location_id": sample.location_id,
            "type_id": sample.type_id,
            "dataset_family": sample.dataset_family,
            "raw_attributes": sample.raw_attributes,
        }
        try:
            result = post_json(f"{base_url.rstrip('/')}/score", payload)
        except HTTPError as exc:
            print(f"HTTP error while seeding {sample.event_id}: {exc.code}", file=sys.stderr)
            return 1
        except URLError as exc:
            print(f"Connection error while seeding {sample.event_id}: {exc.reason}", file=sys.stderr)
            return 1
        print(f"Seeded {result['event_id']} with risk bucket {result['risk_bucket']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
