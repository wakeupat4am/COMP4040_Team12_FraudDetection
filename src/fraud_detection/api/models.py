"""Pydantic models for the fraud-operations backend API."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


DatasetFamily = Literal["ssfd", "paysim"]
RiskBucket = Literal["low", "medium", "high", "critical"]
Decision = Literal["allow", "review", "block"]
CaseStatus = Literal["scored", "reviewed"]


class ScoreRequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str
    event_time: float
    source_id: str
    target_id: str
    amount: float = Field(ge=0)
    location_id: str
    type_id: str
    dataset_family: DatasetFamily
    raw_attributes: dict[str, Any] | None = None


class ModelScoresModel(BaseModel):
    event_gnn: float
    adaboost: float
    lightgbm: float
    hetero_gnn_shadow: float | None = None


class RequiredStateStatusModel(BaseModel):
    history_available: bool
    graph_context_available: bool


class ExplanationContributorModel(BaseModel):
    feature: str
    direction: Literal["increase", "decrease"]
    magnitude: float
    summary: str


class ExplanationStateAvailabilityModel(BaseModel):
    history_available: bool
    graph_context_available: bool
    history_summary: str
    graph_summary: str


class EvidencePanelModel(BaseModel):
    panel: str
    title: str
    items: list[str]


class ExplanationPayloadModel(BaseModel):
    summary: str
    top_contributors: list[ExplanationContributorModel]
    state_availability: ExplanationStateAvailabilityModel
    evidence_panels: list[EvidencePanelModel]


class RoutingMetadataModel(BaseModel):
    selected_ensemble: str
    base_models: list[str]


class FraudPipelineOutputModel(BaseModel):
    event_id: str
    dataset_family: DatasetFamily
    final_risk_score: float = Field(ge=0, le=1)
    risk_bucket: RiskBucket
    decision: Decision
    model_scores: ModelScoresModel
    required_state_status: RequiredStateStatusModel
    routing_metadata: RoutingMetadataModel
    explanation_stub: ExplanationPayloadModel


class PersistedCaseMetadataModel(BaseModel):
    scored_at: datetime
    status: CaseStatus
    current_analyst_decision: Decision | None = None
    analyst_note: str | None = None
    decision_updated_at: datetime | None = None


class ScoreResponseModel(FraudPipelineOutputModel, PersistedCaseMetadataModel):
    pass


class CaseQueueItemModel(BaseModel):
    event_id: str
    dataset_family: DatasetFamily
    final_risk_score: float = Field(ge=0, le=1)
    risk_bucket: RiskBucket
    decision: Decision
    status: CaseStatus
    scored_at: datetime
    current_analyst_decision: Decision | None = None
    decision_updated_at: datetime | None = None


class CaseQueueResponseModel(BaseModel):
    items: list[CaseQueueItemModel]
    total: int
    page: int
    page_size: int


class AnalystDecisionRequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str
    analyst_decision: Decision
    note: str = Field(min_length=1, max_length=4000)


class DecisionResponseModel(BaseModel):
    event_id: str
    status: CaseStatus
    current_analyst_decision: Decision
    analyst_note: str
    decision_updated_at: datetime


class MetricsSummaryModel(BaseModel):
    total_cases: int
    by_risk_bucket: dict[str, int]
    by_decision: dict[str, int]
    reviewed_cases: int
