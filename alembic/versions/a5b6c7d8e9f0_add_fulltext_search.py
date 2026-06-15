"""add full-text search — tsvector columns + GIN indexes + auto-update triggers

Revision ID: a5b6c7d8e9f0
Revises: f4fcdb06ac7f
Create Date: 2026-06-15
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "a5b6c7d8e9f0"
down_revision: Union[str, None] = "3a7b4e8c1d2f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # ── 1. Add tsvector columns ─────────────────────────────────
    op.add_column("demands", sa.Column("search_vector", postgresql.TSVECTOR(), nullable=True))
    op.add_column("capability_profiles", sa.Column("search_vector", postgresql.TSVECTOR(), nullable=True))

    # ── 2. Create GIN indexes ────────────────────────────────────
    op.create_index("ix_demands_search_vector", "demands", ["search_vector"], postgres_using="gin")
    op.create_index("ix_capability_profiles_search_vector", "capability_profiles", ["search_vector"], postgres_using="gin")

    # ── 3. Create trigger function for demands ───────────────────
    op.execute(sa.text("""
        CREATE OR REPLACE FUNCTION demands_tsvector_update()
        RETURNS trigger AS $$
        BEGIN
            NEW.search_vector := to_tsvector('simple',
                COALESCE(NEW.raw_text, '') || ' ' ||
                COALESCE(NEW.category, '') || ' ' ||
                COALESCE(NEW.sub_category, '') || ' ' ||
                COALESCE(NEW.search_text, '')
            );
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """))

    # ── 4. Create trigger for demands ───────────────────────────
    op.execute(sa.text("""
        CREATE TRIGGER trg_demands_tsvector
        BEFORE INSERT OR UPDATE OF raw_text, category, sub_category, search_text
        ON demands
        FOR EACH ROW
        EXECUTE FUNCTION demands_tsvector_update();
    """))

    # ── 5. Create trigger function for capability_profiles ──────
    op.execute(sa.text("""
        CREATE OR REPLACE FUNCTION capability_profiles_tsvector_update()
        RETURNS trigger AS $$
        DECLARE
            card_text text;
        BEGIN
            card_text := COALESCE(NEW.agent_card_json->>'name', '') || ' ' ||
                         COALESCE(NEW.agent_card_json->>'description', '') || ' ' ||
                         COALESCE(NEW.agent_card_json->>'capabilities', '') || ' ' ||
                         COALESCE(NEW.agent_card_json->>'expertise', '');
            NEW.search_vector := to_tsvector('simple', card_text);
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """))

    # ── 6. Create trigger for capability_profiles ──────────────
    op.execute(sa.text("""
        CREATE TRIGGER trg_capability_profiles_tsvector
        BEFORE INSERT OR UPDATE OF agent_card_json
        ON capability_profiles
        FOR EACH ROW
        EXECUTE FUNCTION capability_profiles_tsvector_update();
    """))

    # ── 7. Backfill existing data ────────────────────────────────
    op.execute(sa.text("""
        UPDATE demands
        SET raw_text = raw_text
        WHERE search_vector IS NULL;
    """))
    op.execute(sa.text("""
        UPDATE capability_profiles
        SET agent_card_json = agent_card_json
        WHERE search_vector IS NULL;
    """))


def downgrade():
    op.execute(sa.text("DROP TRIGGER IF EXISTS trg_demands_tsvector ON demands"))
    op.execute(sa.text("DROP TRIGGER IF EXISTS trg_capability_profiles_tsvector ON capability_profiles"))
    op.execute(sa.text("DROP FUNCTION IF EXISTS demands_tsvector_update()"))
    op.execute(sa.text("DROP FUNCTION IF EXISTS capability_profiles_tsvector_update()"))
    op.drop_index("ix_demands_search_vector", table_name="demands")
    op.drop_index("ix_capability_profiles_search_vector", table_name="capability_profiles")
    op.drop_column("demands", "search_vector")
    op.drop_column("capability_profiles", "search_vector")
