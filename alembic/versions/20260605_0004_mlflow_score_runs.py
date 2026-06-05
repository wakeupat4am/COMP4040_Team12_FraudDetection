"""Add MLflow metadata to score runs."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260605_0004"
down_revision = "20260604_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("case_score_runs", sa.Column("mlflow_run_id", sa.String(length=255), nullable=True))
    op.add_column("case_score_runs", sa.Column("model_artifact_uri", sa.String(length=1024), nullable=True))
    op.add_column("case_score_runs", sa.Column("model_metadata", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("case_score_runs", "model_metadata")
    op.drop_column("case_score_runs", "model_artifact_uri")
    op.drop_column("case_score_runs", "mlflow_run_id")
