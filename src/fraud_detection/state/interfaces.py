"""Protocols describing the scoring state store contract."""

from __future__ import annotations

from typing import Any, Protocol


class HistoricalStateStore(Protocol):
    @property
    def total_events(self) -> int:
        ...

    def bootstrap_from_ssfd_history(self) -> None:
        ...

    def add_transaction(self, event: Any, label: int | None = None) -> None:
        ...

    def get_sender_history(self, sender_id: str) -> list[dict[str, Any]]:
        ...

    def get_receiver_history(self, receiver_id: str) -> list[dict[str, Any]]:
        ...

    def get_pair_history(self, sender_id: str, receiver_id: str) -> list[dict[str, Any]]:
        ...

    def get_recent_events(self, limit: int = 250) -> list[dict[str, Any]]:
        ...

    def get_recent_sender_events(self, sender_id: str, limit: int = 50) -> list[dict[str, Any]]:
        ...

    def get_recent_receiver_events(self, receiver_id: str, limit: int = 50) -> list[dict[str, Any]]:
        ...

    def history_available(self, sender_id: str, receiver_id: str) -> bool:
        ...

    def graph_context_available(self, sender_id: str, receiver_id: str) -> bool:
        ...
