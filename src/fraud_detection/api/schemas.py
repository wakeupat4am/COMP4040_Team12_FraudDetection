"""API request and response models."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


DecisionValue = Literal["allow", "review", "block"]
RoleValue = Literal["analyst", "manager_admin"]
ReviewStatusValue = Literal["pending", "reviewed"]
ConfirmedLabelValue = Literal["fraud", "legitimate"]
ConfidenceValue = Literal["low", "medium", "high"]


class ScoreRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    transaction_id: str
    transaction_timestamp: str
    sender_id: str
    receiver_id: str
    amount: float = Field(ge=0)
    transaction_location: str
    transaction_type: str
    currency: str | None = None
    channel: str | None = None
    raw_attributes: dict[str, Any] | None = None

    @model_validator(mode="before")
    @classmethod
    def normalize_aliases(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        normalized = dict(data)
        aliases = {
            "timestamp": "transaction_timestamp",
            "location": "transaction_location",
        }
        for alias, canonical in aliases.items():
            alias_present = alias in normalized
            canonical_present = canonical in normalized
            if alias_present and canonical_present and normalized[alias] != normalized[canonical]:
                raise ValueError(f"Conflicting values for '{canonical}' and alias '{alias}'")
            if alias_present and not canonical_present:
                normalized[canonical] = normalized[alias]
        return normalized


class CurrentUserResponse(BaseModel):
    username: str
    role: RoleValue
    is_active: bool


class AnalystDecisionRequest(BaseModel):
    analyst_decision: DecisionValue
    note: str = Field(min_length=1)


class CaseFeedbackRequest(BaseModel):
    confirmed_label: ConfirmedLabelValue
    feedback_timestamp: datetime | None = None
    note: str | None = None


class OverviewModelScores(BaseModel):
    LightGBM: float
    AdaBoost: float
    Event_GNN: float


class ExplanationSummary(BaseModel):
    main_risk_source: str
    tabular_signal: Literal["high", "medium", "low"]
    graph_signal: Literal["high", "low"]
    reason: str


class PipelineOutputContract(BaseModel):
    transaction_id: str
    pipeline_profile: str
    final_risk_score: float
    fraud_score: float
    threshold: float
    risk_bucket: str
    decision: DecisionValue
    model_scores: dict[str, float]
    model_scores_overview: OverviewModelScores
    required_state_status: dict[str, bool]
    routing_metadata: dict[str, Any] = Field(default_factory=dict)
    explanation_summary: ExplanationSummary
    explanations: dict[str, Any]


class CaseQueueItem(BaseModel):
    transaction_id: str
    final_risk_score: float
    risk_bucket: str
    decision: DecisionValue
    review_status: ReviewStatusValue
    last_scored_at: datetime
    created_at: datetime
    updated_at: datetime
    latest_analyst_decision: DecisionValue | None = None
    latest_note: str | None = None


class AuditEntry(BaseModel):
    action: str
    details: dict[str, Any]
    created_at: datetime
    actor_username: str | None = None


class ReviewEntry(BaseModel):
    analyst_decision: DecisionValue
    note: str
    created_at: datetime
    analyst_username: str | None = None


class FeedbackEntry(BaseModel):
    confirmed_label: ConfirmedLabelValue
    feedback_timestamp: datetime
    note: str | None = None
    reviewer_username: str | None = None


class GeminiAnalysisResponse(BaseModel):
    recommended_decision: DecisionValue
    confidence: ConfidenceValue
    summary: str
    key_factors: list[str]
    risk_flags: list[str]
    follow_up_actions: list[str]
    model: str
    analyzed_at: datetime
    source_score_run_id: int


class CaseDetailResponse(CaseQueueItem):
    original_request_payload: dict[str, Any]
    latest_output: PipelineOutputContract
    explanation_payload: dict[str, Any]
    routing_metadata: dict[str, Any]
    latest_gemini_analysis: GeminiAnalysisResponse | None = None
    latest_score_run_id: int | None = None
    review_history: list[ReviewEntry]
    feedback_history: list[FeedbackEntry]
    audit_trail: list[AuditEntry]


class CaseListResponse(BaseModel):
    items: list[CaseQueueItem]
    page: int
    page_size: int
    total: int


class MetricsSummaryResponse(BaseModel):
    total_cases: int
    average_final_risk_score: float
    risk_bucket_counts: dict[str, int]
    decision_counts: dict[str, int]
    review_status_counts: dict[str, int]
    pending_review_cases: int


class MonitoringSummaryResponse(BaseModel):
    total_events: int
    average_latency_ms: float
    event_type_counts: dict[str, int]
    average_latency_by_event_type: dict[str, float]
    latest_event_at: datetime | None = None


class HealthResponse(BaseModel):
    status: str


class ConfigResponse(BaseModel):
    model_config = ConfigDict(extra="allow")
