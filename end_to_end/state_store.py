from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


SSFD_BOOTSTRAP_COLUMNS = {"Time", "Source", "Target", "Amount", "Location", "Type", "Labels"}


def parse_timestamp(value: str | float | int) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()


@dataclass
class TransactionEvent:
    transaction_id: str
    transaction_timestamp: str
    sender_id: str
    receiver_id: str
    amount: float
    transaction_location: str
    transaction_type: str
    currency: str | None = None
    channel: str | None = None
    raw_attributes: dict[str, Any] | None = None

    @property
    def timestamp_value(self) -> float:
        return parse_timestamp(self.transaction_timestamp)


class InMemoryStateStore:
    def __init__(self, max_recent_events: int = 2000) -> None:
        self.max_recent_events = max_recent_events
        self._sender_events: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self._receiver_events: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self._pair_events: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
        self._recent_events: deque[dict[str, Any]] = deque(maxlen=max_recent_events)
        self._total_events = 0

    @property
    def total_events(self) -> int:
        return self._total_events

    def to_record(self, event: TransactionEvent, label: int | None = None) -> dict[str, Any]:
        return {
            "transaction_id": event.transaction_id,
            "timestamp": event.timestamp_value,
            "sequence_time": float(self._total_events),
            "transaction_timestamp": event.transaction_timestamp,
            "sender_id": event.sender_id,
            "receiver_id": event.receiver_id,
            "amount": float(event.amount),
            "transaction_location": event.transaction_location,
            "transaction_type": event.transaction_type,
            "currency": event.currency,
            "channel": event.channel,
            "raw_attributes": event.raw_attributes or {},
            "label": label,
        }

    def add_transaction(self, event: TransactionEvent, label: int | None = None) -> None:
        record = self.to_record(event, label=label)
        self._sender_events[event.sender_id].append(record)
        self._receiver_events[event.receiver_id].append(record)
        self._pair_events[(event.sender_id, event.receiver_id)].append(record)
        self._recent_events.append(record)
        self._total_events += 1

    def bootstrap_from_ssfd_history(self) -> None:
        root = Path(__file__).resolve().parents[1]
        paths = [
            root / "data" / "processed" / "ssfd_lightgbm_unlabeled.csv",
            root / "data" / "processed" / "ssfd_lightgbm_train.csv",
        ]
        for path in paths:
            if not path.exists():
                continue
            df = pd.read_csv(path)
            if not SSFD_BOOTSTRAP_COLUMNS.issubset(df.columns):
                continue
            for row in df.itertuples(index=False):
                event = TransactionEvent(
                    transaction_id=f"bootstrap_{getattr(row, 'Time')}_{getattr(row, 'Source')}_{getattr(row, 'Target')}",
                    transaction_timestamp=datetime.fromtimestamp(float(getattr(row, "Time")), tz=timezone.utc).isoformat(),
                    sender_id=str(getattr(row, "Source")),
                    receiver_id=str(getattr(row, "Target")),
                    amount=float(getattr(row, "Amount")),
                    transaction_location=str(getattr(row, "Location")),
                    transaction_type=str(getattr(row, "Type")),
                    raw_attributes={"bootstrapped": True, "original_time": float(getattr(row, "Time"))},
                )
                label = int(getattr(row, "Labels"))
                record = self.to_record(event, label=label if label in {0, 1} else None)
                record["sequence_time"] = float(getattr(row, "Time"))
                self._sender_events[event.sender_id].append(record)
                self._receiver_events[event.receiver_id].append(record)
                self._pair_events[(event.sender_id, event.receiver_id)].append(record)
                self._recent_events.append(record)
                self._total_events += 1

    def get_sender_history(self, sender_id: str) -> list[dict[str, Any]]:
        return list(self._sender_events.get(sender_id, []))

    def get_receiver_history(self, receiver_id: str) -> list[dict[str, Any]]:
        return list(self._receiver_events.get(receiver_id, []))

    def get_pair_history(self, sender_id: str, receiver_id: str) -> list[dict[str, Any]]:
        return list(self._pair_events.get((sender_id, receiver_id), []))

    def get_recent_events(self, limit: int = 250) -> list[dict[str, Any]]:
        if limit <= 0:
            return []
        return list(self._recent_events)[-limit:]

    def get_recent_sender_events(self, sender_id: str, limit: int = 50) -> list[dict[str, Any]]:
        return self.get_sender_history(sender_id)[-limit:]

    def get_recent_receiver_events(self, receiver_id: str, limit: int = 50) -> list[dict[str, Any]]:
        return self.get_receiver_history(receiver_id)[-limit:]

    def history_available(self, sender_id: str, receiver_id: str) -> bool:
        return bool(self._sender_events.get(sender_id) or self._receiver_events.get(receiver_id))

    def graph_context_available(self, sender_id: str, receiver_id: str) -> bool:
        return bool(self.get_recent_events(1) or self._pair_events.get((sender_id, receiver_id)))
