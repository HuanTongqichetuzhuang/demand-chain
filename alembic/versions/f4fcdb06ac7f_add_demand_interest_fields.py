"""add demand interest fields — interest_count, duplicate_group_id, interest_users

Revision ID: f4fcdb06ac7f
Revises: 8c209c0fbdd4
Create Date: 2026-06-14
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "f4fcdb06ac7f"
down_revision: Union[str, None] = "8c209c0fbdd4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.add_column("demands", sa.Column("interest_count", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("demands", sa.Column("duplicate_group_id", sa.String(36), nullable=True))
    op.add_column("demands", sa.Column("interest_users", postgresql.JSONB(), nullable=True))
    op.create_index("ix_demands_duplicate_group_id", "demands", ["duplicate_group_id"])


def downgrade():
    op.drop_index("ix_demands_duplicate_group_id")
    op.drop_column("demands", "interest_users")
    op.drop_column("demands", "duplicate_group_id")
    op.drop_column("demands", "interest_count")

