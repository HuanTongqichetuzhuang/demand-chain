"""add messaging system — Message model

Revision ID: d0e1f2a3b4c5
Revises: c0d1e2f3a4b5
Create Date: 2026-06-15
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "d0e1f2a3b4c5"
down_revision: Union[str, None] = "c0d1e2f3a4b5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.create_table(
        "messages",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("from_user", sa.String(32), nullable=False, index=True),
        sa.Column("to_user", sa.String(32), nullable=False, index=True),
        sa.Column("match_id", sa.String(36), sa.ForeignKey("matches.id"), nullable=True, index=True),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("is_read", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_messages_users", "messages", ["from_user", "to_user"])
    op.create_index("ix_messages_match", "messages", ["match_id", "is_read"])


def downgrade():
    op.drop_index("ix_messages_match", table_name="messages")
    op.drop_index("ix_messages_users", table_name="messages")
    op.drop_table("messages")

