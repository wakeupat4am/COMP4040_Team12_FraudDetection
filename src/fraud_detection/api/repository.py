"""Persistence boundary for fraud case storage."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from fraud_detection.api.db import Base, create_db_engine, create_session_factory, ensure_sqlite_directory, get_database_url
from fraud_detection.api.db_models import AnalystReview, AuditLog, ScoredEvent


@dataclass(slots=True)
class PersistedCase:
    event_id: str
    request_payload: dict[str, Any]
    score_payload: dict[str, Any]
    scored_at: datetime
    status: str = "scored"
    current_analyst_decision: str | None = None
    analyst_note: str | None = None
    decision_updated_at: datetime | None = None


@dataclass(slots=True)
class CaseListResult:
    items: list[PersistedCase]
    total: int


@dataclass(slots=True)
class MetricsSummary:
    total_cases: int
    by_risk_bucket: dict[str, int]
    by_decision: dict[str, int]
    reviewed_cases: int


class CaseRepository(Protocol):
    def save_scored_case(
        self,
        request_payload: dict[str, Any],
        score_payload: dict[str, Any],
    ) -> PersistedCase:
        """Persist a scored case and return the stored representation."""

    def list_cases(self) -> list[PersistedCase]:
        """Return all scored cases in queue order."""

    def get_case(self, event_id: str) -> PersistedCase | None:
        """Return a single scored case or None."""

    def list_cases_paginated(
        self,
        *,
        risk_bucket: str | None,
        decision: str | None,
        status: str | None,
        dataset_family: str | None,
        date_from: datetime | None,
        date_to: datetime | None,
        page: int,
        page_size: int,
    ) -> CaseListResult:
        """Return filtered queue results."""

    def update_case_decision(
        self,
        event_id: str,
        analyst_decision: str,
        note: str,
        actor: str = "analyst",
    ) -> PersistedCase | None:
        """Persist an analyst decision for a case."""

    def rescore_case(
        self,
        event_id: str,
        score_payload: dict[str, Any],
        actor: str = "system",
    ) -> PersistedCase | None:
        """Replace the current score payload for an existing case."""

    def get_metrics_summary(self) -> MetricsSummary:
        """Return aggregate metrics for the dashboard."""


class InMemoryCaseRepository:
    """Simple repository used until a database-backed repository is added."""

    def __init__(self) -> None:
        self._cases: dict[str, PersistedCase] = {}
        self._ordered_ids: list[str] = []

    def save_scored_case(
        self,
        request_payload: dict[str, Any],
        score_payload: dict[str, Any],
    ) -> PersistedCase:
        now = datetime.now(timezone.utc)
        event_id = score_payload["event_id"]
        case = PersistedCase(
            event_id=event_id,
            request_payload=request_payload,
            score_payload=score_payload,
            scored_at=now,
        )
        if event_id not in self._cases:
            self._ordered_ids.insert(0, event_id)
        self._cases[event_id] = case
        return case

    def list_cases(self) -> list[PersistedCase]:
        return [self._cases[event_id] for event_id in self._ordered_ids]

    def get_case(self, event_id: str) -> PersistedCase | None:
        return self._cases.get(event_id)

    def list_cases_paginated(
        self,
        *,
        risk_bucket: str | None,
        decision: str | None,
        status: str | None,
        dataset_family: str | None,
        date_from: datetime | None,
        date_to: datetime | None,
        page: int,
        page_size: int,
    ) -> CaseListResult:
        filtered = self.list_cases()
        if risk_bucket is not None:
            filtered = [case for case in filtered if case.score_payload["risk_bucket"] == risk_bucket]
        if decision is not None:
            filtered = [case for case in filtered if case.score_payload["decision"] == decision]
        if status is not None:
            filtered = [case for case in filtered if case.status == status]
        if dataset_family is not None:
            filtered = [case for case in filtered if case.score_payload["dataset_family"] == dataset_family]
        if date_from is not None:
            filtered = [case for case in filtered if case.scored_at >= date_from]
        if date_to is not None:
            filtered = [case for case in filtered if case.scored_at <= date_to]

        total = len(filtered)
        start = (page - 1) * page_size
        end = start + page_size
        return CaseListResult(items=filtered[start:end], total=total)

    def update_case_decision(
        self,
        event_id: str,
        analyst_decision: str,
        note: str,
        actor: str = "analyst",
    ) -> PersistedCase | None:
        case = self._cases.get(event_id)
        if case is None:
            return None
        now = datetime.now(timezone.utc)
        case.current_analyst_decision = analyst_decision
        case.analyst_note = note
        case.decision_updated_at = now
        case.status = "reviewed"
        return case

    def rescore_case(
        self,
        event_id: str,
        score_payload: dict[str, Any],
        actor: str = "system",
    ) -> PersistedCase | None:
        case = self._cases.get(event_id)
        if case is None:
            return None
        case.score_payload = score_payload
        case.scored_at = datetime.now(timezone.utc)
        return case

    def get_metrics_summary(self) -> MetricsSummary:
        cases = self.list_cases()
        by_risk_bucket = {"low": 0, "medium": 0, "high": 0, "critical": 0}
        by_decision = {"allow": 0, "review": 0, "block": 0}
        reviewed_cases = 0
        for case in cases:
            by_risk_bucket[case.score_payload["risk_bucket"]] += 1
            by_decision[case.score_payload["decision"]] += 1
            if case.current_analyst_decision is not None:
                reviewed_cases += 1
        return MetricsSummary(
            total_cases=len(cases),
            by_risk_bucket=by_risk_bucket,
            by_decision=by_decision,
            reviewed_cases=reviewed_cases,
        )


def _to_persisted_case(record: ScoredEvent) -> PersistedCase:
    return PersistedCase(
        event_id=record.event_id,
        request_payload=record.request_payload,
        score_payload=record.score_payload,
        scored_at=record.scored_at,
        status=record.status,
        current_analyst_decision=record.current_analyst_decision,
        analyst_note=record.analyst_note,
        decision_updated_at=record.decision_updated_at,
    )


class SQLAlchemyCaseRepository:
    """Database-backed repository using SQLAlchemy ORM."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    @classmethod
    def from_database_url(cls, database_url: str | None = None) -> "SQLAlchemyCaseRepository":
        url = database_url or get_database_url()
        ensure_sqlite_directory(url)
        return cls(create_session_factory(url))

    def init_schema(self) -> None:
        engine = self._session_factory.kw["bind"]
        Base.metadata.create_all(engine)

    def save_scored_case(
        self,
        request_payload: dict[str, Any],
        score_payload: dict[str, Any],
    ) -> PersistedCase:
        with self._session_factory() as session:
            record = session.scalar(
                select(ScoredEvent).where(ScoredEvent.event_id == score_payload["event_id"])
            )
            if record is None:
                record = ScoredEvent(
                    event_id=score_payload["event_id"],
                    dataset_family=score_payload["dataset_family"],
                    final_risk_score=score_payload["final_risk_score"],
                    risk_bucket=score_payload["risk_bucket"],
                    decision=score_payload["decision"],
                    status="scored",
                    request_payload=request_payload,
                    score_payload=score_payload,
                    explanation_payload=score_payload["explanation_stub"],
                )
                session.add(record)
                action = "score_created"
            else:
                record.dataset_family = score_payload["dataset_family"]
                record.final_risk_score = score_payload["final_risk_score"]
                record.risk_bucket = score_payload["risk_bucket"]
                record.decision = score_payload["decision"]
                record.status = "scored"
                record.request_payload = request_payload
                record.score_payload = score_payload
                record.explanation_payload = score_payload["explanation_stub"]
                record.scored_at = datetime.now(timezone.utc)
                action = "score_updated"

            session.add(
                AuditLog(
                    event_id=score_payload["event_id"],
                    action=action,
                    actor="system",
                    payload={"dataset_family": score_payload["dataset_family"]},
                )
            )
            session.commit()
            session.refresh(record)
            return _to_persisted_case(record)

    def list_cases(self) -> list[PersistedCase]:
        with self._session_factory() as session:
            records = session.scalars(select(ScoredEvent).order_by(ScoredEvent.scored_at.desc())).all()
            return [_to_persisted_case(record) for record in records]

    def get_case(self, event_id: str) -> PersistedCase | None:
        with self._session_factory() as session:
            record = session.scalar(select(ScoredEvent).where(ScoredEvent.event_id == event_id))
            return None if record is None else _to_persisted_case(record)

    def list_cases_paginated(
        self,
        *,
        risk_bucket: str | None,
        decision: str | None,
        status: str | None,
        dataset_family: str | None,
        date_from: datetime | None,
        date_to: datetime | None,
        page: int,
        page_size: int,
    ) -> CaseListResult:
        with self._session_factory() as session:
            query = select(ScoredEvent)
            count_query = select(func.count()).select_from(ScoredEvent)

            filters = []
            if risk_bucket is not None:
                filters.append(ScoredEvent.risk_bucket == risk_bucket)
            if decision is not None:
                filters.append(ScoredEvent.decision == decision)
            if status is not None:
                filters.append(ScoredEvent.status == status)
            if dataset_family is not None:
                filters.append(ScoredEvent.dataset_family == dataset_family)
            if date_from is not None:
                filters.append(ScoredEvent.scored_at >= date_from)
            if date_to is not None:
                filters.append(ScoredEvent.scored_at <= date_to)

            for clause in filters:
                query = query.where(clause)
                count_query = count_query.where(clause)

            total = session.scalar(count_query) or 0
            offset = (page - 1) * page_size
            records = session.scalars(
                query.order_by(ScoredEvent.scored_at.desc()).offset(offset).limit(page_size)
            ).all()
            return CaseListResult(items=[_to_persisted_case(record) for record in records], total=total)

    def update_case_decision(
        self,
        event_id: str,
        analyst_decision: str,
        note: str,
        actor: str = "analyst",
    ) -> PersistedCase | None:
        with self._session_factory() as session:
            record = session.scalar(select(ScoredEvent).where(ScoredEvent.event_id == event_id))
            if record is None:
                return None
            now = datetime.now(timezone.utc)
            record.current_analyst_decision = analyst_decision
            record.analyst_note = note
            record.decision_updated_at = now
            record.status = "reviewed"
            session.add(
                AnalystReview(
                    event_id=event_id,
                    analyst_decision=analyst_decision,
                    note=note,
                )
            )
            session.add(
                AuditLog(
                    event_id=event_id,
                    action="decision_submitted",
                    actor=actor,
                    payload={"analyst_decision": analyst_decision, "note": note},
                )
            )
            session.commit()
            session.refresh(record)
            return _to_persisted_case(record)

    def rescore_case(
        self,
        event_id: str,
        score_payload: dict[str, Any],
        actor: str = "system",
    ) -> PersistedCase | None:
        with self._session_factory() as session:
            record = session.scalar(select(ScoredEvent).where(ScoredEvent.event_id == event_id))
            if record is None:
                return None
            record.dataset_family = score_payload["dataset_family"]
            record.final_risk_score = score_payload["final_risk_score"]
            record.risk_bucket = score_payload["risk_bucket"]
            record.decision = score_payload["decision"]
            record.score_payload = score_payload
            record.explanation_payload = score_payload["explanation_stub"]
            record.scored_at = datetime.now(timezone.utc)
            session.add(
                AuditLog(
                    event_id=event_id,
                    action="case_rescored",
                    actor=actor,
                    payload={"final_risk_score": score_payload["final_risk_score"]},
                )
            )
            session.commit()
            session.refresh(record)
            return _to_persisted_case(record)

    def get_metrics_summary(self) -> MetricsSummary:
        with self._session_factory() as session:
            total_cases = session.scalar(select(func.count()).select_from(ScoredEvent)) or 0
            by_risk_bucket = {"low": 0, "medium": 0, "high": 0, "critical": 0}
            by_decision = {"allow": 0, "review": 0, "block": 0}

            risk_rows = session.execute(
                select(ScoredEvent.risk_bucket, func.count()).group_by(ScoredEvent.risk_bucket)
            ).all()
            decision_rows = session.execute(
                select(ScoredEvent.decision, func.count()).group_by(ScoredEvent.decision)
            ).all()
            reviewed_cases = session.scalar(
                select(func.count()).select_from(ScoredEvent).where(ScoredEvent.current_analyst_decision.is_not(None))
            ) or 0

            for bucket, count in risk_rows:
                by_risk_bucket[bucket] = count
            for decision, count in decision_rows:
                by_decision[decision] = count

            return MetricsSummary(
                total_cases=total_cases,
                by_risk_bucket=by_risk_bucket,
                by_decision=by_decision,
                reviewed_cases=reviewed_cases,
            )

    def get_request_payload(self, event_id: str) -> dict[str, Any] | None:
        with self._session_factory() as session:
            record = session.scalar(select(ScoredEvent).where(ScoredEvent.event_id == event_id))
            return None if record is None else record.request_payload
