from __future__ import annotations

from end_to_end.feature_builder import build_features
from end_to_end.state_store import InMemoryStateStore, TransactionEvent


def _event(transaction_id: str, timestamp: str, sender: str, receiver: str, amount: float, location: str, tx_type: str) -> TransactionEvent:
    return TransactionEvent(
        transaction_id=transaction_id,
        transaction_timestamp=timestamp,
        sender_id=sender,
        receiver_id=receiver,
        amount=amount,
        transaction_location=location,
        transaction_type=tx_type,
    )


def test_feature_builder_uses_only_prior_history() -> None:
    state = InMemoryStateStore()
    first = _event("tx1", "2026-06-02T10:00:00Z", "S1", "T1", 10.0, "L1", "TP1")
    second = _event("tx2", "2026-06-02T10:01:00Z", "S1", "T2", 40.0, "L1", "TP1")

    state.add_transaction(first)
    built = build_features(second, state)

    assert built.tabular_features["source_tx_count_so_far"] == 1
    assert built.tabular_features["target_tx_count_so_far"] == 0
    assert built.tabular_features["source_target_pair_count_so_far"] == 0
    assert built.tabular_features["source_amount_mean_before"] == 10.0
    assert built.tabular_features["amount_vs_source_mean"] == 30.0


def test_event_context_has_single_test_node_and_sequential_event_ids() -> None:
    state = InMemoryStateStore()
    state.add_transaction(_event("tx1", "2026-06-02T10:00:00Z", "S1", "T1", 10.0, "L1", "TP1"))
    state.add_transaction(_event("tx2", "2026-06-02T10:01:00Z", "S2", "T1", 11.0, "L1", "TP2"))
    candidate = _event("tx3", "2026-06-02T10:02:00Z", "S1", "T3", 12.0, "L2", "TP1")

    built = build_features(candidate, state)
    frame = built.event_context_frame

    assert frame["split"].tolist().count("test") == 1
    assert frame["event_id"].tolist() == list(range(len(frame)))
