"""add match_outcomes and category_weights for flywheel

Revision ID: 3a7b4e8c1d2f
Revises: f4fcdb06ac7f
Create Date: 2026-06-14
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "3a7b4e8c1d2f"
down_revision: Union[str, None] = "f4fcdb06ac7f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # MatchOutcome table (status as String, not Enum — avoid asyncpg enum serialization issues)
    op.create_table(
        "match_outcomes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("match_id", sa.String(36), sa.ForeignKey("matches.id"), nullable=False, index=True),
        sa.Column("demand_id", sa.String(36), sa.ForeignKey("demands.id"), nullable=False, index=True),
        sa.Column("supplier_id", sa.String(36), sa.ForeignKey("capability_profiles.id"), nullable=False, index=True),
        sa.Column("status", sa.String(32), nullable=False, index=True, server_default="matched"),
        sa.Column("outcome_detail", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.text("now()")),
    )

    # CategoryWeight table
    op.create_table(
        "category_weights",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("demand_category", sa.String(128), nullable=False, index=True),
        sa.Column("supplier_category", sa.String(128), nullable=False, index=True),
        sa.Column("weight", sa.Float, nullable=False, server_default="0.5"),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.text("now()")),
    )


def downgrade():
    op.drop_table("category_weights")
    op.drop_table("match_outcomes")
