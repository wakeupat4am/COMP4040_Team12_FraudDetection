from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from .state_store import InMemoryStateStore, TransactionEvent


@dataclass
class BuiltFeatures:
    tabular_features: dict[str, float | int | str]
    event_context_frame: pd.DataFrame
    state_status: dict[str, bool]


def _last_gap(current_ts: float, history: list[dict[str, Any]]) -> float:
    if not history:
        return 0.0
    return max(current_ts - float(history[-1]["sequence_time"]), 0.0)


def _mean_amount(history: list[dict[str, Any]]) -> float:
    if not history:
        return 0.0
    return float(sum(float(item["amount"]) for item in history) / len(history))


def build_tabular_features(event: TransactionEvent, state_store: InMemoryStateStore) -> dict[str, float | int | str]:
    sender_history = state_store.get_sender_history(event.sender_id)
    receiver_history = state_store.get_receiver_history(event.receiver_id)
    pair_history = state_store.get_pair_history(event.sender_id, event.receiver_id)
    current_ts = float(state_store.total_events)

    sender_mean = _mean_amount(sender_history)
    receiver_mean = _mean_amount(receiver_history)
    pair_mean = _mean_amount(pair_history)

    features: dict[str, float | int | str] = {
        "Time": float(current_ts),
        "Amount": float(event.amount),
        "amount_log1p": float(np.log1p(max(float(event.amount), 0.0))),
        "Source": event.sender_id,
        "Target": event.receiver_id,
        "Location": event.transaction_location,
        "Type": event.transaction_type,
        "source_tx_count_so_far": len(sender_history),
        "target_tx_count_so_far": len(receiver_history),
        "location_tx_count_so_far": sum(1 for item in state_store.get_recent_events(state_store.total_events) if item["transaction_location"] == event.transaction_location),
        "type_tx_count_so_far": sum(1 for item in state_store.get_recent_events(state_store.total_events) if item["transaction_type"] == event.transaction_type),
        "source_target_pair_count_so_far": len(pair_history),
        "source_time_gap": _last_gap(current_ts, sender_history),
        "target_time_gap": _last_gap(current_ts, receiver_history),
        "pair_time_gap": _last_gap(current_ts, pair_history),
        "source_amount_mean_before": sender_mean,
        "target_amount_mean_before": receiver_mean,
        "pair_amount_mean_before": pair_mean,
        "amount_vs_source_mean": float(event.amount) - sender_mean,
        "amount_vs_target_mean": float(event.amount) - receiver_mean,
        "amount_vs_pair_mean": float(event.amount) - pair_mean,
        "source_seen_target_before": int(len(pair_history) > 0),
        "source_seen_location_before": int(any(item["transaction_location"] == event.transaction_location for item in sender_history)),
        "source_seen_type_before": int(any(item["transaction_type"] == event.transaction_type for item in sender_history)),
        "source_freq": (len(sender_history) / state_store.total_events) if state_store.total_events else 0.0,
        "source_count": len(sender_history),
        "target_freq": (len(receiver_history) / state_store.total_events) if state_store.total_events else 0.0,
        "target_count": len(receiver_history),
        "location_freq": (
            sum(1 for item in state_store.get_recent_events(state_store.total_events) if item["transaction_location"] == event.transaction_location) / state_store.total_events
            if state_store.total_events
            else 0.0
        ),
        "location_count": sum(1 for item in state_store.get_recent_events(state_store.total_events) if item["transaction_location"] == event.transaction_location),
        "type_freq": (
            sum(1 for item in state_store.get_recent_events(state_store.total_events) if item["transaction_type"] == event.transaction_type) / state_store.total_events
            if state_store.total_events
            else 0.0
        ),
        "type_count": sum(1 for item in state_store.get_recent_events(state_store.total_events) if item["transaction_type"] == event.transaction_type),
    }
    return features


def build_event_context(event: TransactionEvent, state_store: InMemoryStateStore, global_limit: int = 250) -> pd.DataFrame:
    context = state_store.get_recent_events(global_limit)
    sender_context = state_store.get_recent_sender_events(event.sender_id, limit=50)
    receiver_context = state_store.get_recent_receiver_events(event.receiver_id, limit=50)

    combined: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for record in context + sender_context + receiver_context:
        if record["transaction_id"] in seen_ids:
            continue
        seen_ids.add(record["transaction_id"])
        combined.append(
            {
                "event_id": int(len(combined)),
                "Time": float(record["sequence_time"]),
                "Source": record["sender_id"],
                "Target": record["receiver_id"],
                "Amount": float(record["amount"]),
                "Location": record["transaction_location"],
                "Type": record["transaction_type"],
                "Labels": 2,
                "split": "context",
            }
        )

    combined.append(
        {
            "event_id": int(len(combined)),
            "Time": float(state_store.total_events),
            "Source": event.sender_id,
            "Target": event.receiver_id,
            "Amount": float(event.amount),
            "Location": event.transaction_location,
            "Type": event.transaction_type,
            "Labels": 2,
            "split": "test",
        }
    )
    df = pd.DataFrame(combined)
    df = df.sort_values("Time").reset_index(drop=True)
    df["event_id"] = np.arange(len(df))
    return df


def build_features(event: TransactionEvent, state_store: InMemoryStateStore) -> BuiltFeatures:
    return BuiltFeatures(
        tabular_features=build_tabular_features(event, state_store),
        event_context_frame=build_event_context(event, state_store),
        state_status={
            "history_available": state_store.history_available(event.sender_id, event.receiver_id),
            "graph_context_available": state_store.graph_context_available(event.sender_id, event.receiver_id),
        },
    )
