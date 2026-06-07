"""ORM models for the analyst workflow backend."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(512))
    role: Mapped[str] = mapped_column(String(32))
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    analyst_reviews: Mapped[list["AnalystReview"]] = relationship(back_populates="analyst")
    feedback_entries: Mapped[list["FraudFeedback"]] = relationship(back_populates="reviewer")


class ScoredCase(Base):
    __tablename__ = "scored_cases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    transaction_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    original_request_payload: Mapped[dict] = mapped_column(JSON)
    current_output_payload: Mapped[dict] = mapped_column(JSON)
    explanation_payload: Mapped[dict] = mapped_column(JSON)
    routing_metadata: Mapped[dict] = mapped_column(JSON)
    latest_gemini_analysis_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    pipeline_profile: Mapped[str] = mapped_column(String(128))
    final_risk_score: Mapped[float] = mapped_column(Float)
    risk_bucket: Mapped[str] = mapped_column(String(32))
    decision: Mapped[str] = mapped_column(String(32))
    review_status: Mapped[str] = mapped_column(String(32), default="pending")
    latest_analyst_decision: Mapped[str | None] = mapped_column(String(32), nullable=True)
    latest_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    latest_score_run_id: Mapped[int | None] = mapped_column(ForeignKey("case_score_runs.id"), nullable=True)
    last_scored_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    score_runs: Mapped[list["CaseScoreRun"]] = relationship(back_populates="scored_case", foreign_keys="CaseScoreRun.scored_case_id")
    analyst_reviews: Mapped[list["AnalystReview"]] = relationship(back_populates="scored_case")
    feedback_entries: Mapped[list["FraudFeedback"]] = relationship(back_populates="scored_case")
    monitoring_events: Mapped[list["MonitoringEvent"]] = relationship(back_populates="scored_case")


class CaseScoreRun(Base):
    __tablename__ = "case_score_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scored_case_id: Mapped[int] = mapped_column(ForeignKey("scored_cases.id"), index=True)
    triggered_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    run_type: Mapped[str] = mapped_column(String(32))
    request_payload: Mapped[dict] = mapped_column(JSON)
    output_payload: Mapped[dict] = mapped_column(JSON)
    explanation_payload: Mapped[dict] = mapped_column(JSON)
    routing_metadata: Mapped[dict] = mapped_column(JSON)
    final_risk_score: Mapped[float] = mapped_column(Float)
    risk_bucket: Mapped[str] = mapped_column(String(32))
    decision: Mapped[str] = mapped_column(String(32))
    scored_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    scored_case: Mapped[ScoredCase] = relationship(back_populates="score_runs", foreign_keys=[scored_case_id])
    monitoring_events: Mapped[list["MonitoringEvent"]] = relationship(back_populates="score_run")


class AnalystReview(Base):
    __tablename__ = "analyst_reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scored_case_id: Mapped[int] = mapped_column(ForeignKey("scored_cases.id"), index=True)
    analyst_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    analyst_decision: Mapped[str] = mapped_column(String(32))
    note: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    scored_case: Mapped[ScoredCase] = relationship(back_populates="analyst_reviews")
    analyst: Mapped[User] = relationship(back_populates="analyst_reviews")


class FraudFeedback(Base):
    __tablename__ = "fraud_feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scored_case_id: Mapped[int] = mapped_column(ForeignKey("scored_cases.id"), index=True)
    reviewer_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    confirmed_label: Mapped[str] = mapped_column(String(32))
    feedback_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    scored_case: Mapped[ScoredCase] = relationship(back_populates="feedback_entries")
    reviewer: Mapped[User] = relationship(back_populates="feedback_entries")


class MonitoringEvent(Base):
    __tablename__ = "monitoring_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scored_case_id: Mapped[int] = mapped_column(ForeignKey("scored_cases.id"), index=True)
    score_run_id: Mapped[int | None] = mapped_column(ForeignKey("case_score_runs.id"), index=True, nullable=True)
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    transaction_id: Mapped[str] = mapped_column(String(255), index=True)
    event_type: Mapped[str] = mapped_column(String(32), index=True)
    latency_ms: Mapped[float] = mapped_column(Float)
    decision: Mapped[str] = mapped_column(String(32))
    final_risk_score: Mapped[float] = mapped_column(Float)
    history_available: Mapped[bool] = mapped_column(Boolean)
    graph_context_available: Mapped[bool] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    scored_case: Mapped[ScoredCase] = relationship(back_populates="monitoring_events")
    score_run: Mapped[CaseScoreRun | None] = relationship(back_populates="monitoring_events")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    transaction_id: Mapped[str | None] = mapped_column(String(255), index=True, nullable=True)
    action: Mapped[str] = mapped_column(String(64), index=True)
    details: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
