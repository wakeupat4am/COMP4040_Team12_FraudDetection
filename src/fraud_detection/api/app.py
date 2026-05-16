"""FastAPI app exposing the first fraud-operations backend surface."""

from __future__ import annotations

from datetime import datetime

from fastapi import FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware

from fraud_detection.api.models import (
    AnalystDecisionRequestModel,
    CaseQueueItemModel,
    CaseQueueResponseModel,
    DecisionResponseModel,
    MetricsSummaryModel,
    ScoreRequestModel,
    ScoreResponseModel,
)
from fraud_detection.api.repository import (
    CaseRepository,
    InMemoryCaseRepository,
    PersistedCase,
    SQLAlchemyCaseRepository,
)
from fraud_detection.scoring import score_payload


def _build_case_response(case: PersistedCase) -> ScoreResponseModel:
    return ScoreResponseModel(
        **case.score_payload,
        scored_at=case.scored_at,
        status=case.status,
        current_analyst_decision=case.current_analyst_decision,
        analyst_note=case.analyst_note,
        decision_updated_at=case.decision_updated_at,
    )


def _build_queue_item(case: PersistedCase) -> CaseQueueItemModel:
    payload = case.score_payload
    return CaseQueueItemModel(
        event_id=payload["event_id"],
        dataset_family=payload["dataset_family"],
        final_risk_score=payload["final_risk_score"],
        risk_bucket=payload["risk_bucket"],
        decision=payload["decision"],
        status=case.status,
        scored_at=case.scored_at,
        current_analyst_decision=case.current_analyst_decision,
        decision_updated_at=case.decision_updated_at,
    )


def _build_decision_response(case: PersistedCase) -> DecisionResponseModel:
    assert case.current_analyst_decision is not None
    assert case.analyst_note is not None
    assert case.decision_updated_at is not None
    return DecisionResponseModel(
        event_id=case.event_id,
        status=case.status,
        current_analyst_decision=case.current_analyst_decision,
        analyst_note=case.analyst_note,
        decision_updated_at=case.decision_updated_at,
    )


def create_app(repository: CaseRepository | None = None) -> FastAPI:
    app = FastAPI(title="Fraud Ops API", version="0.1.0")
    case_repository = repository or SQLAlchemyCaseRepository.from_database_url()
    if isinstance(case_repository, SQLAlchemyCaseRepository):
        case_repository.init_schema()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health_check() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/score", response_model=ScoreResponseModel, status_code=status.HTTP_201_CREATED)
    def score_case(request: ScoreRequestModel) -> ScoreResponseModel:
        score_result = score_payload(request.model_dump())
        case = case_repository.save_scored_case(
            request_payload=request.model_dump(),
            score_payload=score_result,
        )
        return _build_case_response(case)

    @app.get("/cases", response_model=CaseQueueResponseModel)
    def list_cases(
        risk_bucket: str | None = Query(default=None),
        decision: str | None = Query(default=None),
        status_filter: str | None = Query(default=None, alias="status"),
        dataset_family: str | None = Query(default=None),
        date_from: datetime | None = Query(default=None),
        date_to: datetime | None = Query(default=None),
        page: int = Query(default=1, ge=1),
        page_size: int = Query(default=20, ge=1, le=200),
    ) -> CaseQueueResponseModel:
        result = case_repository.list_cases_paginated(
            risk_bucket=risk_bucket,
            decision=decision,
            status=status_filter,
            dataset_family=dataset_family,
            date_from=date_from,
            date_to=date_to,
            page=page,
            page_size=page_size,
        )
        return CaseQueueResponseModel(
            items=[_build_queue_item(case) for case in result.items],
            total=result.total,
            page=page,
            page_size=page_size,
        )

    @app.get("/cases/{event_id}", response_model=ScoreResponseModel)
    def get_case(event_id: str) -> ScoreResponseModel:
        case = case_repository.get_case(event_id)
        if case is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Case '{event_id}' was not found.",
            )
        return _build_case_response(case)

    @app.post("/score/rescore/{event_id}", response_model=ScoreResponseModel)
    def rescore_case(event_id: str) -> ScoreResponseModel:
        if not hasattr(case_repository, "get_request_payload"):
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail="Repository does not support rescoring.",
            )
        request_payload = case_repository.get_request_payload(event_id)
        if request_payload is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Case '{event_id}' was not found.",
            )
        rescored = case_repository.rescore_case(event_id, score_payload(request_payload))
        if rescored is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Case '{event_id}' was not found.",
            )
        return _build_case_response(rescored)

    @app.post("/cases/{event_id}/decision", response_model=DecisionResponseModel)
    def submit_case_decision(
        event_id: str,
        request: AnalystDecisionRequestModel,
    ) -> DecisionResponseModel:
        if request.event_id != event_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Path event_id must match request event_id.",
            )
        case = case_repository.update_case_decision(
            event_id=event_id,
            analyst_decision=request.analyst_decision,
            note=request.note,
        )
        if case is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Case '{event_id}' was not found.",
            )
        return _build_decision_response(case)

    @app.get("/metrics/summary", response_model=MetricsSummaryModel)
    def get_metrics_summary() -> MetricsSummaryModel:
        metrics = case_repository.get_metrics_summary()
        return MetricsSummaryModel(
            total_cases=metrics.total_cases,
            by_risk_bucket=metrics.by_risk_bucket,
            by_decision=metrics.by_decision,
            reviewed_cases=metrics.reviewed_cases,
        )

    return app


app = create_app()
