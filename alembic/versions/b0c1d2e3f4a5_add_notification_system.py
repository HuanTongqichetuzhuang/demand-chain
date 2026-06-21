"""add notification system — Notification model

Revision ID: b0c1d2e3f4a5
Revises: a5b6c7d8e9f0
Create Date: 2026-06-15
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "b0c1d2e3f4a5"
down_revision: Union[str, None] = "a5b6c7d8e9f0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.create_table(
        "notifications",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(32), sa.ForeignKey("users.human_id"), nullable=False, index=True),
        sa.Column("title", sa.String(256), nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("channel", sa.String(32), nullable=False, server_default="in_app"),
        sa.Column("urgency", sa.String(16), nullable=False, server_default="normal"),
        sa.Column("action_url", sa.String(512), nullable=True),
        sa.Column("is_read", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("demand_id", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_notifications_user_read", "notifications", ["user_id", "is_read"])


def downgrade():
    op.drop_index("ix_notifications_user_read", table_name="notifications")
    op.drop_table("notifications")

