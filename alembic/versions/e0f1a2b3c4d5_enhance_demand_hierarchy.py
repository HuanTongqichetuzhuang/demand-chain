"""enhance demand hierarchy — add level and sort_order columns

Revision ID: e0f1a2b3c4d5
Revises: d0e1f2a3b4c5
Create Date: 2026-06-15
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "e0f1a2b3c4d5"
down_revision: Union[str, None] = "d0e1f2a3b4c5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.add_column("demands", sa.Column("level", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("demands", sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"))
    op.create_index("ix_demands_parent_level", "demands", ["parent_id", "level"])


def downgrade():
    op.drop_index("ix_demands_parent_level", table_name="demands")
    op.drop_column("demands", "sort_order")
    op.drop_column("demands", "level")

