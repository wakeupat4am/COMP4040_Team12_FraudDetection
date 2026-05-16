"""SQLAlchemy ORM models for the fraud-operations persistence layer."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from fraud_detection.api.db import Base


class ScoredEvent(Base):
    __tablename__ = "scored_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    dataset_family: Mapped[str] = mapped_column(String(32), index=True)
    final_risk_score: Mapped[float] = mapped_column(Float)
    risk_bucket: Mapped[str] = mapped_column(String(32), index=True)
    decision: Mapped[str] = mapped_column(String(32), index=True)
    status: Mapped[str] = mapped_column(String(32), default="scored", index=True)
    current_analyst_decision: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    analyst_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    request_payload: Mapped[dict] = mapped_column(JSON)
    score_payload: Mapped[dict] = mapped_column(JSON)
    explanation_payload: Mapped[dict] = mapped_column(JSON)
    scored_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), onupdate=func.now())
    decision_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    reviews: Mapped[list["AnalystReview"]] = relationship(back_populates="scored_event", cascade="all, delete-orphan")
    audit_logs: Mapped[list["AuditLog"]] = relationship(back_populates="scored_event", cascade="all, delete-orphan")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    role: Mapped[str] = mapped_column(String(32), default="analyst")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())

    reviews: Mapped[list["AnalystReview"]] = relationship(back_populates="user")
    audit_logs: Mapped[list["AuditLog"]] = relationship(back_populates="user")


class AnalystReview(Base):
    __tablename__ = "analyst_reviews"
    __table_args__ = (UniqueConstraint("event_id", "created_at", name="uq_analyst_reviews_event_created"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[str] = mapped_column(ForeignKey("scored_events.event_id"), index=True)
    analyst_decision: Mapped[str] = mapped_column(String(32))
    note: Mapped[str] = mapped_column(Text)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), index=True)

    scored_event: Mapped[ScoredEvent] = relationship(back_populates="reviews")
    user: Mapped[User | None] = relationship(back_populates="reviews")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[str | None] = mapped_column(ForeignKey("scored_events.event_id"), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(64), index=True)
    actor: Mapped[str] = mapped_column(String(255), default="system")
    payload: Mapped[dict] = mapped_column(JSON)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), index=True)

    scored_event: Mapped[ScoredEvent | None] = relationship(back_populates="audit_logs")
    user: Mapped[User | None] = relationship(back_populates="audit_logs")
