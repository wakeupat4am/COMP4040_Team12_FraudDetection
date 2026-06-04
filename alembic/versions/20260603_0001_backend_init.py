"""Initialize fraud analyst backend tables.

Revision ID: 20260603_0001
Revises:
Create Date: 2026-06-03
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260603_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(length=128), nullable=False),
        sa.Column("password_hash", sa.String(length=512), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=True)

    op.create_table(
        "scored_cases",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("transaction_id", sa.String(length=255), nullable=False),
        sa.Column("original_request_payload", sa.JSON(), nullable=False),
        sa.Column("current_output_payload", sa.JSON(), nullable=False),
        sa.Column("explanation_payload", sa.JSON(), nullable=False),
        sa.Column("routing_metadata", sa.JSON(), nullable=False),
        sa.Column("pipeline_profile", sa.String(length=128), nullable=False),
        sa.Column("final_risk_score", sa.Float(), nullable=False),
        sa.Column("risk_bucket", sa.String(length=32), nullable=False),
        sa.Column("decision", sa.String(length=32), nullable=False),
        sa.Column("review_status", sa.String(length=32), nullable=False),
        sa.Column("latest_analyst_decision", sa.String(length=32), nullable=True),
        sa.Column("latest_note", sa.Text(), nullable=True),
        sa.Column("latest_score_run_id", sa.Integer(), nullable=True),
        sa.Column("last_scored_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_scored_cases_transaction_id", "scored_cases", ["transaction_id"], unique=True)

    op.create_table(
        "case_score_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("scored_case_id", sa.Integer(), sa.ForeignKey("scored_cases.id"), nullable=False),
        sa.Column("triggered_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("run_type", sa.String(length=32), nullable=False),
        sa.Column("request_payload", sa.JSON(), nullable=False),
        sa.Column("output_payload", sa.JSON(), nullable=False),
        sa.Column("explanation_payload", sa.JSON(), nullable=False),
        sa.Column("routing_metadata", sa.JSON(), nullable=False),
        sa.Column("final_risk_score", sa.Float(), nullable=False),
        sa.Column("risk_bucket", sa.String(length=32), nullable=False),
        sa.Column("decision", sa.String(length=32), nullable=False),
        sa.Column("scored_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_case_score_runs_scored_case_id", "case_score_runs", ["scored_case_id"], unique=False)

    op.create_table(
        "analyst_reviews",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("scored_case_id", sa.Integer(), sa.ForeignKey("scored_cases.id"), nullable=False),
        sa.Column("analyst_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("analyst_decision", sa.String(length=32), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_analyst_reviews_scored_case_id", "analyst_reviews", ["scored_case_id"], unique=False)

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("transaction_id", sa.String(length=255), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"], unique=False)
    op.create_index("ix_audit_logs_transaction_id", "audit_logs", ["transaction_id"], unique=False)

    op.create_foreign_key(
        "fk_scored_cases_latest_score_run_id",
        "scored_cases",
        "case_score_runs",
        ["latest_score_run_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_scored_cases_latest_score_run_id", "scored_cases", type_="foreignkey")
    op.drop_index("ix_audit_logs_transaction_id", table_name="audit_logs")
    op.drop_index("ix_audit_logs_action", table_name="audit_logs")
    op.drop_table("audit_logs")
    op.drop_index("ix_analyst_reviews_scored_case_id", table_name="analyst_reviews")
    op.drop_table("analyst_reviews")
    op.drop_index("ix_case_score_runs_scored_case_id", table_name="case_score_runs")
    op.drop_table("case_score_runs")
    op.drop_index("ix_scored_cases_transaction_id", table_name="scored_cases")
    op.drop_table("scored_cases")
    op.drop_index("ix_users_username", table_name="users")
    op.drop_table("users")
