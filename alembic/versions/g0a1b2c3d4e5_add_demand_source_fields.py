"""add demand source fields — source, source_url, organization, deadline, budget_hint, location

Revision ID: g0a1b2c3d4e5
Revises: f0a1b2c3d4e5
Create Date: 2026-06-16
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "g0a1b2c3d4e5"
down_revision: Union[str, None] = "f0a1b2c3d4e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.add_column("demands", sa.Column("source", sa.String(128), nullable=True))
    op.add_column("demands", sa.Column("source_url", sa.String(512), nullable=True))
    op.add_column("demands", sa.Column("organization", sa.String(256), nullable=True))
    op.add_column("demands", sa.Column("deadline", sa.String(32), nullable=True))
    op.add_column("demands", sa.Column("budget_hint", sa.String(128), nullable=True))
    op.add_column("demands", sa.Column("location", sa.String(128), nullable=True))
    op.create_index("ix_demands_source", "demands", ["source"])
    op.create_index("ix_demands_organization", "demands", ["organization"])


def downgrade():
    op.drop_index("ix_demands_organization", table_name="demands")
    op.drop_index("ix_demands_source", table_name="demands")
    op.drop_column("demands", "location")
    op.drop_column("demands", "budget_hint")
    op.drop_column("demands", "deadline")
    op.drop_column("demands", "organization")
    op.drop_column("demands", "source_url")
    op.drop_column("demands", "source")
