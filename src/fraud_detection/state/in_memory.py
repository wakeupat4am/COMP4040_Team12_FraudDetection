"""In-memory state store adapter used by the production scoring service."""

from __future__ import annotations

from end_to_end.state_store import InMemoryStateStore


class InMemoryHistoricalStateStore(InMemoryStateStore):
    """Typed adapter for the v1 historical-state implementation."""


def build_default_state_store() -> InMemoryHistoricalStateStore:
    return InMemoryHistoricalStateStore()
