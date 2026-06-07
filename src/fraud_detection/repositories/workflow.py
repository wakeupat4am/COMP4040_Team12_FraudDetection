"""Repository helpers for fraud analyst workflow persistence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import AnalystReview, AuditLog, CaseScoreRun, FraudFeedback, MonitoringEvent, ScoredCase, User


@dataclass(frozen=True)
class CaseFilters:
    risk_bucket: str | None = None
    decision: str | None = None
    review_status: str | None = None
    created_from: datetime | None = None
    created_to: datetime | None = None
    page: int = 1
    page_size: int = 25


class UserRepository:
    def get_by_username(self, session: Session, username: str) -> User | None:
        return session.scalar(select(User).where(User.username == username))

    def get_by_id(self, session: Session, user_id: int) -> User | None:
        return session.get(User, user_id)

    def create(self, session: Session, username: str, password_hash: str, role: str) -> User:
        user = User(username=username, password_hash=password_hash, role=role)
        session.add(user)
        session.flush()
        return user


class WorkflowRepository:
    def get_case_by_transaction_id(self, session: Session, transaction_id: str) -> ScoredCase | None:
        return session.scalar(select(ScoredCase).where(ScoredCase.transaction_id == transaction_id))

    def _apply_case_filters(self, statement, filters: CaseFilters):
        if filters.risk_bucket:
            statement = statement.where(ScoredCase.risk_bucket == filters.risk_bucket)
        if filters.decision:
            statement = statement.where(ScoredCase.decision == filters.decision)
        if filters.review_status:
            statement = statement.where(ScoredCase.review_status == filters.review_status)
        if filters.created_from:
            statement = statement.where(ScoredCase.created_at >= filters.created_from)
        if filters.created_to:
            statement = statement.where(ScoredCase.created_at <= filters.created_to)
        return statement

    def list_cases(self, session: Session, filters: CaseFilters) -> tuple[list[ScoredCase], int]:
        base = self._apply_case_filters(select(ScoredCase), filters)
        count_statement = self._apply_case_filters(select(func.count()).select_from(ScoredCase), filters)
        total = int(session.scalar(count_statement) or 0)
        offset = (max(filters.page, 1) - 1) * max(filters.page_size, 1)
        items = session.scalars(
            base.order_by(ScoredCase.last_scored_at.desc(), ScoredCase.id.desc()).offset(offset).limit(filters.page_size)
        ).all()
        return list(items), total

    def create_scored_case(
        self,
        session: Session,
        request_payload: dict[str, Any],
        output_payload: dict[str, Any],
        actor_user_id: int | None,
    ) -> ScoredCase:
        scored_case = ScoredCase(
            transaction_id=output_payload["transaction_id"],
            original_request_payload=request_payload,
            current_output_payload=output_payload,
            explanation_payload=output_payload["explanations"],
            routing_metadata=output_payload.get("routing_metadata", {}),
            pipeline_profile=output_payload["pipeline_profile"],
            final_risk_score=float(output_payload["final_risk_score"]),
            risk_bucket=output_payload["risk_bucket"],
            decision=output_payload["decision"],
            review_status="pending",
        )
        session.add(scored_case)
        session.flush()
        score_run = self.append_score_run(session, scored_case, request_payload, output_payload, "initial", actor_user_id)
        scored_case.latest_score_run_id = score_run.id
        scored_case.last_scored_at = score_run.scored_at
        self.add_audit_log(
            session,
            transaction_id=scored_case.transaction_id,
            action="score_created",
            actor_user_id=actor_user_id,
            details={"score_run_id": score_run.id, "decision": output_payload["decision"]},
        )
        session.flush()
        return scored_case

    def append_score_run(
        self,
        session: Session,
        scored_case: ScoredCase,
        request_payload: dict[str, Any],
        output_payload: dict[str, Any],
        run_type: str,
        actor_user_id: int | None,
    ) -> CaseScoreRun:
        score_run = CaseScoreRun(
            scored_case_id=scored_case.id,
            triggered_by_user_id=actor_user_id,
            run_type=run_type,
            request_payload=request_payload,
            output_payload=output_payload,
            explanation_payload=output_payload["explanations"],
            routing_metadata=output_payload.get("routing_metadata", {}),
            final_risk_score=float(output_payload["final_risk_score"]),
            risk_bucket=output_payload["risk_bucket"],
            decision=output_payload["decision"],
        )
        session.add(score_run)
        session.flush()

        scored_case.current_output_payload = output_payload
        scored_case.explanation_payload = output_payload["explanations"]
        scored_case.routing_metadata = output_payload.get("routing_metadata", {})
        scored_case.latest_gemini_analysis_payload = None
        scored_case.pipeline_profile = output_payload["pipeline_profile"]
        scored_case.final_risk_score = float(output_payload["final_risk_score"])
        scored_case.risk_bucket = output_payload["risk_bucket"]
        scored_case.decision = output_payload["decision"]
        scored_case.latest_score_run_id = score_run.id
        scored_case.last_scored_at = score_run.scored_at
        scored_case.review_status = "pending"
        scored_case.latest_analyst_decision = None
        scored_case.latest_note = None
        session.flush()
        return score_run

    def record_rescore(
        self,
        session: Session,
        scored_case: ScoredCase,
        output_payload: dict[str, Any],
        actor_user_id: int,
    ) -> ScoredCase:
        score_run = self.append_score_run(
            session,
            scored_case=scored_case,
            request_payload=scored_case.original_request_payload,
            output_payload=output_payload,
            run_type="rescore",
            actor_user_id=actor_user_id,
        )
        self.add_audit_log(
            session,
            transaction_id=scored_case.transaction_id,
            action="case_rescored",
            actor_user_id=actor_user_id,
            details={"score_run_id": score_run.id, "decision": output_payload["decision"]},
        )
        return scored_case

    def record_analyst_review(
        self,
        session: Session,
        scored_case: ScoredCase,
        analyst_user_id: int,
        analyst_decision: str,
        note: str,
    ) -> AnalystReview:
        review = AnalystReview(
            scored_case_id=scored_case.id,
            analyst_user_id=analyst_user_id,
            analyst_decision=analyst_decision,
            note=note,
        )
        session.add(review)
        scored_case.review_status = "reviewed"
        scored_case.latest_analyst_decision = analyst_decision
        scored_case.latest_note = note
        session.flush()
        self.add_audit_log(
            session,
            transaction_id=scored_case.transaction_id,
            action="analyst_decision_submitted",
            actor_user_id=analyst_user_id,
            details={"analyst_decision": analyst_decision, "note": note},
        )
        return review

    def record_feedback(
        self,
        session: Session,
        scored_case: ScoredCase,
        reviewer_user_id: int,
        confirmed_label: str,
        feedback_timestamp: datetime | None,
        note: str | None,
    ) -> FraudFeedback:
        feedback = FraudFeedback(
            scored_case_id=scored_case.id,
            reviewer_user_id=reviewer_user_id,
            confirmed_label=confirmed_label,
            feedback_timestamp=feedback_timestamp or datetime.now(tz=timezone.utc),
            note=note,
        )
        session.add(feedback)
        session.flush()
        self.add_audit_log(
            session,
            transaction_id=scored_case.transaction_id,
            action="feedback_submitted",
            actor_user_id=reviewer_user_id,
            details={"confirmed_label": confirmed_label, "note": note},
        )
        return feedback

    def record_gemini_analysis(
        self,
        session: Session,
        scored_case: ScoredCase,
        analysis_payload: dict[str, Any],
        actor_user_id: int,
    ) -> None:
        scored_case.latest_gemini_analysis_payload = analysis_payload
        session.flush()
        self.add_audit_log(
            session,
            transaction_id=scored_case.transaction_id,
            action="gemini_analysis_generated",
            actor_user_id=actor_user_id,
            details={
                "model": analysis_payload["model"],
                "recommended_decision": analysis_payload["recommended_decision"],
                "source_score_run_id": analysis_payload["source_score_run_id"],
            },
        )

    def record_gemini_failure(
        self,
        session: Session,
        scored_case: ScoredCase,
        actor_user_id: int,
        error_message: str,
    ) -> None:
        self.add_audit_log(
            session,
            transaction_id=scored_case.transaction_id,
            action="gemini_analysis_failed",
            actor_user_id=actor_user_id,
            details={"error": error_message},
        )

    def record_monitoring_event(
        self,
        session: Session,
        scored_case: ScoredCase,
        event_type: str,
        latency_ms: float,
        actor_user_id: int | None,
        output_payload: dict[str, Any],
    ) -> MonitoringEvent:
        state_status = output_payload["required_state_status"]
        event = MonitoringEvent(
            scored_case_id=scored_case.id,
            score_run_id=scored_case.latest_score_run_id,
            actor_user_id=actor_user_id,
            transaction_id=scored_case.transaction_id,
            event_type=event_type,
            latency_ms=float(latency_ms),
            decision=output_payload["decision"],
            final_risk_score=float(output_payload["final_risk_score"]),
            history_available=bool(state_status["history_available"]),
            graph_context_available=bool(state_status["graph_context_available"]),
        )
        session.add(event)
        session.flush()
        return event

    def add_audit_log(
        self,
        session: Session,
        transaction_id: str | None,
        action: str,
        actor_user_id: int | None,
        details: dict[str, Any],
    ) -> AuditLog:
        entry = AuditLog(transaction_id=transaction_id, action=action, actor_user_id=actor_user_id, details=details)
        session.add(entry)
        session.flush()
        return entry

    def list_review_history(self, session: Session, scored_case_id: int) -> list[tuple[AnalystReview, str | None]]:
        statement = (
            select(AnalystReview, User.username)
            .join(User, AnalystReview.analyst_user_id == User.id)
            .where(AnalystReview.scored_case_id == scored_case_id)
            .order_by(AnalystReview.created_at.desc(), AnalystReview.id.desc())
        )
        return list(session.execute(statement).all())

    def list_audit_logs(self, session: Session, transaction_id: str) -> list[tuple[AuditLog, str | None]]:
        statement = (
            select(AuditLog, User.username)
            .join(User, AuditLog.actor_user_id == User.id, isouter=True)
            .where(AuditLog.transaction_id == transaction_id)
            .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        )
        return list(session.execute(statement).all())

    def list_feedback_history(self, session: Session, scored_case_id: int) -> list[tuple[FraudFeedback, str | None]]:
        statement = (
            select(FraudFeedback, User.username)
            .join(User, FraudFeedback.reviewer_user_id == User.id)
            .where(FraudFeedback.scored_case_id == scored_case_id)
            .order_by(FraudFeedback.feedback_timestamp.desc(), FraudFeedback.id.desc())
        )
        return list(session.execute(statement).all())

    def monitoring_summary(self, session: Session) -> dict[str, Any]:
        total_events = int(session.scalar(select(func.count()).select_from(MonitoringEvent)) or 0)
        average_latency = float(session.scalar(select(func.avg(MonitoringEvent.latency_ms))) or 0.0)
        latest_event_at = session.scalar(select(func.max(MonitoringEvent.created_at)))

        event_type_rows = session.execute(select(MonitoringEvent.event_type, func.count()).group_by(MonitoringEvent.event_type)).all()
        latency_rows = session.execute(select(MonitoringEvent.event_type, func.avg(MonitoringEvent.latency_ms)).group_by(MonitoringEvent.event_type)).all()

        return {
            "total_events": total_events,
            "average_latency_ms": average_latency,
            "event_type_counts": {str(value): int(count) for value, count in event_type_rows if value is not None},
            "average_latency_by_event_type": {str(value): float(avg) for value, avg in latency_rows if value is not None and avg is not None},
            "latest_event_at": latest_event_at,
        }

    def metrics_summary(self, session: Session) -> dict[str, Any]:
        total_cases = int(session.scalar(select(func.count()).select_from(ScoredCase)) or 0)
        average_score = float(session.scalar(select(func.avg(ScoredCase.final_risk_score))) or 0.0)

        def grouped_counts(column) -> dict[str, int]:
            rows = session.execute(select(column, func.count()).group_by(column)).all()
            return {str(value): int(count) for value, count in rows if value is not None}

        return {
            "total_cases": total_cases,
            "average_final_risk_score": average_score,
            "risk_bucket_counts": grouped_counts(ScoredCase.risk_bucket),
            "decision_counts": grouped_counts(ScoredCase.decision),
            "review_status_counts": grouped_counts(ScoredCase.review_status),
            "pending_review_cases": int(
                session.scalar(select(func.count()).select_from(ScoredCase).where(ScoredCase.review_status == "pending")) or 0
            ),
        }
