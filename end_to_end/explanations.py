from __future__ import annotations

from typing import Any


def build_tabular_explanations(features: dict[str, Any]) -> list[dict[str, Any]]:
    candidates = [
        ("amount_vs_source_mean", abs(float(features.get("amount_vs_source_mean", 0.0))), "Amount deviates from sender history."),
        ("amount_vs_target_mean", abs(float(features.get("amount_vs_target_mean", 0.0))), "Amount deviates from receiver history."),
        ("source_time_gap", abs(float(features.get("source_time_gap", 0.0))), "Short sender time gap can indicate burst activity."),
        ("pair_time_gap", abs(float(features.get("pair_time_gap", 0.0))), "Short sender-receiver recurrence can indicate concentrated activity."),
        ("source_seen_target_before", 1.0 - float(features.get("source_seen_target_before", 0)), "First-time sender-receiver interaction."),
        ("source_seen_type_before", 1.0 - float(features.get("source_seen_type_before", 0)), "Transaction type is novel for the sender."),
    ]
    top = sorted(candidates, key=lambda item: item[1], reverse=True)[:3]
    return [
        {
            "feature": name,
            "value": float(features.get(name, 0.0)),
            "direction": "higher_risk",
            "comment": comment,
        }
        for name, _, comment in top
    ]


def build_event_context_explanation(context_rows: int, sender_history_size: int, receiver_history_size: int) -> list[dict[str, Any]]:
    return [
        {
            "signal": "recent_event_context_size",
            "value": context_rows,
            "comment": "Number of recent events assembled for Event-GNN scoring.",
        },
        {
            "signal": "sender_history_size",
            "value": sender_history_size,
            "comment": "Historical events available for the sender.",
        },
        {
            "signal": "receiver_history_size",
            "value": receiver_history_size,
            "comment": "Historical events available for the receiver.",
        },
    ]
