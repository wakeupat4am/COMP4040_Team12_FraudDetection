"""Add latest Gemini advisory analysis payload to scored cases.

Revision ID: 20260608_0003
Revises: 20260603_0002
Create Date: 2026-06-08
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260608_0003"
down_revision = "20260603_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("scored_cases", sa.Column("latest_gemini_analysis_payload", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("scored_cases", "latest_gemini_analysis_payload")
