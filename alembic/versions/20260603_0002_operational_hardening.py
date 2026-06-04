"""Add feedback and monitoring tables.

Revision ID: 20260603_0002
Revises: 20260603_0001
Create Date: 2026-06-03
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260603_0002"
down_revision = "20260603_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "fraud_feedback",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("scored_case_id", sa.Integer(), sa.ForeignKey("scored_cases.id"), nullable=False),
        sa.Column("reviewer_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("confirmed_label", sa.String(length=32), nullable=False),
        sa.Column("feedback_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_fraud_feedback_scored_case_id", "fraud_feedback", ["scored_case_id"], unique=False)

    op.create_table(
        "monitoring_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("scored_case_id", sa.Integer(), sa.ForeignKey("scored_cases.id"), nullable=False),
        sa.Column("score_run_id", sa.Integer(), sa.ForeignKey("case_score_runs.id"), nullable=True),
        sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("transaction_id", sa.String(length=255), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("latency_ms", sa.Float(), nullable=False),
        sa.Column("decision", sa.String(length=32), nullable=False),
        sa.Column("final_risk_score", sa.Float(), nullable=False),
        sa.Column("history_available", sa.Boolean(), nullable=False),
        sa.Column("graph_context_available", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_monitoring_events_scored_case_id", "monitoring_events", ["scored_case_id"], unique=False)
    op.create_index("ix_monitoring_events_score_run_id", "monitoring_events", ["score_run_id"], unique=False)
    op.create_index("ix_monitoring_events_transaction_id", "monitoring_events", ["transaction_id"], unique=False)
    op.create_index("ix_monitoring_events_event_type", "monitoring_events", ["event_type"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_monitoring_events_event_type", table_name="monitoring_events")
    op.drop_index("ix_monitoring_events_transaction_id", table_name="monitoring_events")
    op.drop_index("ix_monitoring_events_score_run_id", table_name="monitoring_events")
    op.drop_index("ix_monitoring_events_scored_case_id", table_name="monitoring_events")
    op.drop_table("monitoring_events")
    op.drop_index("ix_fraud_feedback_scored_case_id", table_name="fraud_feedback")
    op.drop_table("fraud_feedback")
