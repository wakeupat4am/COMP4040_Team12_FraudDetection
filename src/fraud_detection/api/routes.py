"""FastAPI routes for the fraud analyst workflow backend."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from pydantic import ValidationError

from ..models import User
from ..services import CaseService
from .dependencies import get_case_service, require_roles
from .schemas import (
    AnalystDecisionRequest,
    CaseDetailResponse,
    CaseFeedbackRequest,
    CaseListResponse,
    ConfigResponse,
    CurrentUserResponse,
    HealthResponse,
    MetricsSummaryResponse,
    MonitoringSummaryResponse,
    ScoreRequest,
)


router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["system"])
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/config", response_model=ConfigResponse, tags=["system"])
async def config(case_service: CaseService = Depends(get_case_service)) -> dict[str, Any]:
    return case_service.runtime.config_snapshot()


@router.get("/me", response_model=CurrentUserResponse, tags=["auth"])
async def me(current_user: User = Depends(require_roles("analyst", "manager_admin"))) -> dict[str, Any]:
    return {"username": current_user.username, "role": current_user.role, "is_active": current_user.is_active}


@router.post("/score", response_model=CaseDetailResponse, tags=["cases"])
async def score_case(
    raw_request: dict[str, Any] = Body(...),
    case_service: CaseService = Depends(get_case_service),
    current_user: User = Depends(require_roles("analyst", "manager_admin")),
) -> dict[str, Any]:
    try:
        request = ScoreRequest.model_validate(raw_request)
        return case_service.score_case(request.model_dump(), current_user)
    except ValidationError as exc:
        case_service.session.rollback()
        detail = [{"loc": err["loc"], "msg": err["msg"], "type": err["type"]} for err in exc.errors()]
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail) from exc
    except ValueError as exc:
        case_service.session.rollback()
        status_code = status.HTTP_409_CONFLICT if "already exists" in str(exc) else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    except Exception as exc:
        case_service.session.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/cases", response_model=CaseListResponse, tags=["cases"])
async def list_cases(
    risk_bucket: str | None = Query(default=None),
    decision: str | None = Query(default=None),
    review_status: str | None = Query(default=None),
    created_from: datetime | None = Query(default=None),
    created_to: datetime | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    case_service: CaseService = Depends(get_case_service),
    _: User = Depends(require_roles("analyst", "manager_admin")),
) -> dict[str, Any]:
    return case_service.list_cases(risk_bucket, decision, review_status, created_from, created_to, page, page_size)


@router.get("/cases/{transaction_id}", response_model=CaseDetailResponse, tags=["cases"])
async def get_case_detail(
    transaction_id: str,
    case_service: CaseService = Depends(get_case_service),
    _: User = Depends(require_roles("analyst", "manager_admin")),
) -> dict[str, Any]:
    try:
        return case_service.get_case_detail(transaction_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/cases/{transaction_id}/decision", response_model=CaseDetailResponse, tags=["cases"])
async def submit_decision(
    transaction_id: str,
    request: AnalystDecisionRequest,
    case_service: CaseService = Depends(get_case_service),
    current_user: User = Depends(require_roles("analyst", "manager_admin")),
) -> dict[str, Any]:
    try:
        return case_service.submit_decision(transaction_id, request.analyst_decision, request.note, current_user)
    except LookupError as exc:
        case_service.session.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/cases/{transaction_id}/rescore", response_model=CaseDetailResponse, tags=["cases"])
async def rescore_case(
    transaction_id: str,
    case_service: CaseService = Depends(get_case_service),
    current_user: User = Depends(require_roles("analyst", "manager_admin")),
) -> dict[str, Any]:
    try:
        return case_service.rescore_case(transaction_id, current_user)
    except LookupError as exc:
        case_service.session.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except Exception as exc:
        case_service.session.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/cases/{transaction_id}/feedback", response_model=CaseDetailResponse, tags=["cases"])
async def submit_feedback(
    transaction_id: str,
    request: CaseFeedbackRequest,
    case_service: CaseService = Depends(get_case_service),
    current_user: User = Depends(require_roles("analyst", "manager_admin")),
) -> dict[str, Any]:
    try:
        return case_service.submit_feedback(
            transaction_id=transaction_id,
            confirmed_label=request.confirmed_label,
            feedback_timestamp=request.feedback_timestamp,
            note=request.note,
            actor=current_user,
        )
    except LookupError as exc:
        case_service.session.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/metrics/summary", response_model=MetricsSummaryResponse, tags=["metrics"])
async def metrics_summary(
    case_service: CaseService = Depends(get_case_service),
    _: User = Depends(require_roles("manager_admin")),
) -> dict[str, Any]:
    return case_service.metrics_summary()


@router.get("/monitoring/summary", response_model=MonitoringSummaryResponse, tags=["monitoring"])
async def monitoring_summary(
    case_service: CaseService = Depends(get_case_service),
    _: User = Depends(require_roles("manager_admin")),
) -> dict[str, Any]:
    return case_service.monitoring_summary()
