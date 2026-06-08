"""Case orchestration service for scoring, analyst review, and metrics."""

from __future__ import annotations

import time
from datetime import datetime
from typing import TYPE_CHECKING
from typing import Any

from sqlalchemy.orm import Session

from ..models import ScoredCase, User
from ..repositories import CaseFilters, WorkflowRepository
from .gemini import GeminiAdvisoryService, GeminiAnalysisPayload, GeminiNotConfiguredError, GeminiUpstreamError

if TYPE_CHECKING:
    from ..runtime import ProductionScoringRuntime


class CaseService:
    def __init__(
        self,
        session: Session,
        runtime: ProductionScoringRuntime,
        gemini_advisor: GeminiAdvisoryService,
    ) -> None:
        self.session = session
        self.runtime = runtime
        self.gemini_advisor = gemini_advisor
        self.workflow = WorkflowRepository()

    def score_case(self, payload: dict[str, Any], actor: User) -> dict[str, Any]:
        if self.workflow.get_case_by_transaction_id(self.session, payload["transaction_id"]) is not None:
            raise ValueError(f"Case '{payload['transaction_id']}' already exists; use /cases/{{transaction_id}}/rescore")
        started_at = time.perf_counter()
        output = self.runtime.score_transaction(payload, persist_event=True)
        latency_ms = (time.perf_counter() - started_at) * 1000.0
        scored_case = self.workflow.create_scored_case(self.session, payload, output, actor.id)
        self.workflow.record_monitoring_event(
            self.session,
            scored_case=scored_case,
            event_type="score",
            latency_ms=latency_ms,
            actor_user_id=actor.id,
            output_payload=output,
        )
        self.session.commit()
        return self.get_case_detail(scored_case.transaction_id)

    def list_cases(
        self,
        risk_bucket: str | None,
        decision: str | None,
        review_status: str | None,
        created_from: datetime | None,
        created_to: datetime | None,
        page: int,
        page_size: int,
    ) -> dict[str, Any]:
        filters = CaseFilters(
            risk_bucket=risk_bucket,
            decision=decision,
            review_status=review_status,
            created_from=created_from,
            created_to=created_to,
            page=page,
            page_size=page_size,
        )
        items, total = self.workflow.list_cases(self.session, filters)
        return {
            "items": [self._queue_item(case) for case in items],
            "page": page,
            "page_size": page_size,
            "total": total,
        }

    def get_case_detail(self, transaction_id: str) -> dict[str, Any]:
        scored_case = self.workflow.get_case_by_transaction_id(self.session, transaction_id)
        if scored_case is None:
            raise LookupError(f"Unknown case '{transaction_id}'")
        return self._detail_item(scored_case)

    def submit_decision(self, transaction_id: str, analyst_decision: str, note: str, actor: User) -> dict[str, Any]:
        scored_case = self.workflow.get_case_by_transaction_id(self.session, transaction_id)
        if scored_case is None:
            raise LookupError(f"Unknown case '{transaction_id}'")
        self.workflow.record_analyst_review(self.session, scored_case, actor.id, analyst_decision, note)
        self.session.commit()
        return self.get_case_detail(transaction_id)

    def rescore_case(self, transaction_id: str, actor: User) -> dict[str, Any]:
        scored_case = self.workflow.get_case_by_transaction_id(self.session, transaction_id)
        if scored_case is None:
            raise LookupError(f"Unknown case '{transaction_id}'")
        started_at = time.perf_counter()
        output = self.runtime.score_transaction(scored_case.original_request_payload, persist_event=False)
        latency_ms = (time.perf_counter() - started_at) * 1000.0
        self.workflow.record_rescore(self.session, scored_case, output, actor.id)
        self.workflow.record_monitoring_event(
            self.session,
            scored_case=scored_case,
            event_type="rescore",
            latency_ms=latency_ms,
            actor_user_id=actor.id,
            output_payload=output,
        )
        self.session.commit()
        return self.get_case_detail(transaction_id)

    def submit_feedback(
        self,
        transaction_id: str,
        confirmed_label: str,
        feedback_timestamp: datetime | None,
        note: str | None,
        actor: User,
    ) -> dict[str, Any]:
        scored_case = self.workflow.get_case_by_transaction_id(self.session, transaction_id)
        if scored_case is None:
            raise LookupError(f"Unknown case '{transaction_id}'")
        self.workflow.record_feedback(self.session, scored_case, actor.id, confirmed_label, feedback_timestamp, note)
        self.session.commit()
        return self.get_case_detail(transaction_id)

    def generate_gemini_analysis(self, transaction_id: str, actor: User) -> dict[str, Any]:
        scored_case = self.workflow.get_case_by_transaction_id(self.session, transaction_id)
        if scored_case is None:
            raise LookupError(f"Unknown case '{transaction_id}'")
        if scored_case.latest_score_run_id is None:
            raise GeminiUpstreamError("The case does not have a score run available for Gemini analysis.")

        case_snapshot = self._gemini_case_snapshot(scored_case)
        try:
            analysis_payload = self.gemini_advisor.build_analysis_payload(case_snapshot, scored_case.latest_score_run_id)
        except GeminiNotConfiguredError as exc:
            self.workflow.record_gemini_failure(self.session, scored_case, actor.id, str(exc))
            self.session.commit()
            raise
        except GeminiUpstreamError as exc:
            self.workflow.record_gemini_failure(self.session, scored_case, actor.id, str(exc))
            self.session.commit()
            raise

        self.workflow.record_gemini_analysis(self.session, scored_case, analysis_payload, actor.id)
        self.session.commit()
        return self.get_case_detail(transaction_id)

    def metrics_summary(self) -> dict[str, Any]:
        return self.workflow.metrics_summary(self.session)

    def monitoring_summary(self) -> dict[str, Any]:
        return self.workflow.monitoring_summary(self.session)

    def _queue_item(self, scored_case: ScoredCase) -> dict[str, Any]:
        return {
            "transaction_id": scored_case.transaction_id,
            "final_risk_score": scored_case.final_risk_score,
            "risk_bucket": scored_case.risk_bucket,
            "decision": scored_case.decision,
            "review_status": scored_case.review_status,
            "last_scored_at": scored_case.last_scored_at,
            "created_at": scored_case.created_at,
            "updated_at": scored_case.updated_at,
            "latest_analyst_decision": scored_case.latest_analyst_decision,
            "latest_note": scored_case.latest_note,
        }

    def _detail_item(self, scored_case: ScoredCase) -> dict[str, Any]:
        review_history = self.workflow.list_review_history(self.session, scored_case.id)
        feedback_history = self.workflow.list_feedback_history(self.session, scored_case.id)
        audit_trail = self.workflow.list_audit_logs(self.session, scored_case.transaction_id)
        latest_output = self.runtime.align_output(scored_case.current_output_payload)
        latest_gemini_analysis: dict[str, Any] | None = None
        if scored_case.latest_gemini_analysis_payload is not None:
            latest_gemini_analysis = GeminiAnalysisPayload.model_validate(
                scored_case.latest_gemini_analysis_payload,
            ).model_dump(mode="json")
        return {
            **self._queue_item(scored_case),
            "original_request_payload": scored_case.original_request_payload,
            "latest_output": latest_output,
            "explanation_payload": scored_case.explanation_payload,
            "routing_metadata": scored_case.routing_metadata,
            "latest_gemini_analysis": latest_gemini_analysis,
            "latest_score_run_id": scored_case.latest_score_run_id,
            "review_history": [
                {
                    "analyst_decision": review.analyst_decision,
                    "note": review.note,
                    "created_at": review.created_at,
                    "analyst_username": username,
                }
                for review, username in review_history
            ],
            "feedback_history": [
                {
                    "confirmed_label": feedback.confirmed_label,
                    "feedback_timestamp": feedback.feedback_timestamp,
                    "note": feedback.note,
                    "reviewer_username": username,
                }
                for feedback, username in feedback_history
            ],
            "audit_trail": [
                {
                    "action": entry.action,
                    "details": entry.details,
                    "created_at": entry.created_at,
                    "actor_username": username,
                }
                for entry, username in audit_trail
            ],
        }

    def _gemini_case_snapshot(self, scored_case: ScoredCase) -> dict[str, Any]:
        latest_output = self.runtime.align_output(scored_case.current_output_payload)
        original_request = scored_case.original_request_payload
        explanation_payload = scored_case.explanation_payload
        return {
            "transaction_id": scored_case.transaction_id,
            "risk_bucket": scored_case.risk_bucket,
            "decision": scored_case.decision,
            "last_scored_at": scored_case.last_scored_at.isoformat(),
            "latest_score_run_id": scored_case.latest_score_run_id,
            "transaction_summary": {
                "transaction_timestamp": original_request.get("transaction_timestamp"),
                "sender_id": original_request.get("sender_id"),
                "receiver_id": original_request.get("receiver_id"),
                "amount": original_request.get("amount"),
                "transaction_location": original_request.get("transaction_location"),
                "transaction_type": original_request.get("transaction_type"),
                "currency": original_request.get("currency"),
                "channel": original_request.get("channel"),
                "raw_attributes": self._truncate_mapping(original_request.get("raw_attributes")),
            },
            "score_summary": {
                "transaction_id": latest_output["transaction_id"],
                "pipeline_profile": latest_output["pipeline_profile"],
                "final_risk_score": latest_output["final_risk_score"],
                "fraud_score": latest_output["fraud_score"],
                "threshold": latest_output["threshold"],
                "risk_bucket": latest_output["risk_bucket"],
                "decision": latest_output["decision"],
                "model_scores_overview": latest_output["model_scores_overview"],
                "required_state_status": latest_output["required_state_status"],
                "explanation_summary": latest_output["explanation_summary"],
            },
            "explanation_summary": {
                "state_availability": explanation_payload.get("state_availability"),
                "tabular_risk_factors": self._truncate_sequence(
                    explanation_payload.get("tabular_risk_factors"),
                    limit=5,
                ),
                "event_context_summary": self._truncate_sequence(
                    explanation_payload.get("event_context_summary"),
                    limit=5,
                ),
            },
            "routing_metadata": self._truncate_mapping(scored_case.routing_metadata, limit=10),
        }

    def _truncate_mapping(self, value: Any, limit: int = 8) -> dict[str, Any] | None:
        if not isinstance(value, dict):
            return None
        items = list(value.items())[:limit]
        return {key: self._truncate_scalar_or_nested(item_value) for key, item_value in items}

    def _truncate_sequence(self, value: Any, limit: int = 5) -> list[Any]:
        if not isinstance(value, list):
            return []
        return [self._truncate_scalar_or_nested(item) for item in value[:limit]]

    def _truncate_scalar_or_nested(self, value: Any) -> Any:
        if isinstance(value, dict):
            return self._truncate_mapping(value, limit=6)
        if isinstance(value, list):
            return [self._truncate_scalar_or_nested(item) for item in value[:5]]
        if isinstance(value, str) and len(value) > 280:
            return f"{value[:277]}..."
        return value
