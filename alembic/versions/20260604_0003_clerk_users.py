"""Add Clerk user identity mapping."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260604_0003"
down_revision = "20260603_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("clerk_user_id", sa.String(length=255), nullable=True))
    op.alter_column("users", "password_hash", existing_type=sa.String(length=512), nullable=True)
    op.create_index("ix_users_clerk_user_id", "users", ["clerk_user_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_users_clerk_user_id", table_name="users")
    op.alter_column("users", "password_hash", existing_type=sa.String(length=512), nullable=False)
    op.drop_column("users", "clerk_user_id")
