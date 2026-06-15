"""add demand subscription — DemandSubscription model

Revision ID: c0d1e2f3a4b5
Revises: b0c1d2e3f4a5
Create Date: 2026-06-15
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "c0d1e2f3a4b5"
down_revision: Union[str, None] = "b0c1d2e3f4a5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.create_table(
        "demand_subscriptions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(32), sa.ForeignKey("users.human_id"), nullable=False, index=True),
        sa.Column("name", sa.String(128), nullable=False, server_default="默认订阅"),
        sa.Column("keywords", postgresql.JSONB(), nullable=True, default=list),
        sa.Column("categories", postgresql.JSONB(), nullable=True, default=list),
        sa.Column("notify_email", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("notify_web", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_demand_subscriptions_user", "demand_subscriptions", ["user_id", "is_active"])


def downgrade():
    op.drop_index("ix_demand_subscriptions_user", table_name="demand_subscriptions")
    op.drop_table("demand_subscriptions")
