"""initial migration — create all 14 tables

Revision ID: 8c209c0fbdd4
Revises:
Create Date: 2026-06-14
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import pgvector

revision: str = "8c209c0fbdd4"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # ENUM types
    sa.Enum("NEW", "STRUCTURING", "OPEN", "MATCHING", "IN_PROGRESS",
            "RESOLVED", "CANCELLED", "UNRESOLVABLE", "CLOSED",
            name="demandstatus").create(op.get_bind())
    sa.Enum("INDIVIDUAL", "TEAM", "COMPANY", "RESEARCH", "GOVERNMENT",
            name="profiletype").create(op.get_bind())
    sa.Enum("PENDING", "ACCEPTED", "REJECTED", "EXPIRED",
            name="matchstatus").create(op.get_bind())

    # users
    op.create_table("users",
        sa.Column("human_id", sa.String(32), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(128), nullable=False),
        sa.Column("password_hash", sa.String(128), nullable=False),
        sa.Column("country", sa.String(128), nullable=False, server_default=""),
        sa.Column("api_key", sa.String(64), unique=True, nullable=True),
        sa.Column("email_notify", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("avatar", sa.Text(), nullable=True),
        sa.Column("bio", sa.Text(), nullable=True),
        sa.Column("email_verified", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("verify_token", sa.String(64), unique=True, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_login", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # demands
    op.create_table("demands",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), nullable=False, index=True),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("structured_json", postgresql.JSONB(), nullable=True),
        sa.Column("embedding", pgvector.sqlalchemy.Vector(1536), nullable=True),
        sa.Column("category", sa.String(128), nullable=True, index=True),
        sa.Column("classification_json", postgresql.JSONB(), nullable=True),
        sa.Column("search_text", sa.Text(), nullable=True),
        sa.Column("discipline_path", postgresql.JSONB(), nullable=True),
        sa.Column("ipc_codes", postgresql.JSONB(), nullable=True),
        sa.Column("process_categories", postgresql.JSONB(), nullable=True),
        sa.Column("status", sa.Enum("NEW", "STRUCTURING", "OPEN", "MATCHING",
                    "IN_PROGRESS", "RESOLVED", "CANCELLED", "UNRESOLVABLE", "CLOSED",
                    name="demandstatus"), nullable=False, index=True),
        sa.Column("visibility", sa.String(32), nullable=False, server_default="public"),
        sa.Column("country_restrictions", postgresql.JSONB(), nullable=True),
        sa.Column("parent_id", sa.String(36), sa.ForeignKey("demands.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

    # capability_profiles
    op.create_table("capability_profiles",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), nullable=False, index=True),
        sa.Column("agent_card_json", postgresql.JSONB(), nullable=False),
        sa.Column("embedding", pgvector.sqlalchemy.Vector(1536), nullable=True),
        sa.Column("profile_type",
                  sa.Enum("INDIVIDUAL", "TEAM", "COMPANY", "RESEARCH", "GOVERNMENT",
                          name="profiletype"), nullable=False),
        sa.Column("country", sa.String(64), nullable=True),
        sa.Column("is_claimed", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("verified", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("trust_score", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

    # unclaimed_suppliers
    op.create_table("unclaimed_suppliers",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(256), nullable=False, index=True),
        sa.Column("capabilities", postgresql.JSONB(), nullable=False),
        sa.Column("embedding", pgvector.sqlalchemy.Vector(1536), nullable=True),
        sa.Column("data_sources", postgresql.JSONB(), nullable=False),
        sa.Column("contact_hints", postgresql.JSONB(), nullable=True),
        sa.Column("country", sa.String(64), nullable=True),
        sa.Column("discovered_at", sa.DateTime(), nullable=False),
    )

    # discovered_demands
    op.create_table("discovered_demands",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("source", sa.String(128), nullable=False, index=True),
        sa.Column("source_url", sa.String(512), nullable=True),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("inferred_category", sa.String(64), nullable=True),
        sa.Column("inferred_discipline", sa.String(128), nullable=True),
        sa.Column("deadline", sa.String(32), nullable=True),
        sa.Column("budget_hint", sa.String(64), nullable=True),
        sa.Column("organization", sa.String(256), nullable=True),
        sa.Column("fingerprint", sa.String(32), unique=True, nullable=False),
        sa.Column("is_imported", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("discovered_at", sa.DateTime(), nullable=False),
    )

    # agent_preferences
    op.create_table("agent_preferences",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("agent_id", sa.String(36), unique=True, nullable=False, index=True),
        sa.Column("preferred_categories", postgresql.JSONB(), nullable=True),
        sa.Column("preferred_disciplines", postgresql.JSONB(), nullable=True),
        sa.Column("preferred_ipc", postgresql.JSONB(), nullable=True),
        sa.Column("auto_select", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("notify_only_preferred", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("updated_by", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

    # auth_tokens
    op.create_table("auth_tokens",
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column("human_id", sa.String(32), nullable=False, index=True),
        sa.Column("agent_id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )

    # async_tasks
    op.create_table("async_tasks",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("human_id", sa.String(32), nullable=False, index=True),
        sa.Column("label", sa.String(256), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, index=True),
        sa.Column("result", postgresql.JSONB(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    # matches
    op.create_table("matches",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("demand_id", sa.String(36),
                  sa.ForeignKey("demands.id"), nullable=False, index=True),
        sa.Column("profile_id", sa.String(36),
                  sa.ForeignKey("capability_profiles.id"), nullable=False, index=True),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("status",
                  sa.Enum("PENDING", "ACCEPTED", "REJECTED", "EXPIRED",
                          name="matchstatus"), nullable=False),
        sa.Column("is_unclaimed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

    # forum_topics
    op.create_table("forum_topics",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("agent_id", sa.String(36), nullable=False, index=True),
        sa.Column("title", sa.String(256), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("category", sa.String(64), nullable=False, index=True),
        sa.Column("demand_id", sa.String(36),
                  sa.ForeignKey("demands.id"), nullable=True, index=True),
        sa.Column("upvotes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_pinned", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

    # collaboration_workspaces
    op.create_table("collaboration_workspaces",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("match_id", sa.String(36),
                  sa.ForeignKey("matches.id"), unique=True, nullable=False),
        sa.Column("demand_id", sa.String(36),
                  sa.ForeignKey("demands.id"), nullable=False, index=True),
        sa.Column("demand_agent_id", sa.String(36), nullable=False),
        sa.Column("supply_agent_id", sa.String(36), nullable=False),
        sa.Column("working_memory", postgresql.JSONB(), nullable=True),
        sa.Column("consent_granted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("consent_granted_at", sa.DateTime(), nullable=True),
        sa.Column("following", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

    # forum_replies
    op.create_table("forum_replies",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("topic_id", sa.String(36),
                  sa.ForeignKey("forum_topics.id"), nullable=False, index=True),
        sa.Column("agent_id", sa.String(36), nullable=False, index=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    # forum_votes
    op.create_table("forum_votes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("topic_id", sa.String(36),
                  sa.ForeignKey("forum_topics.id"), nullable=False, index=True),
        sa.Column("agent_id", sa.String(36), nullable=False, index=True),
        sa.Column("direction", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    # working_memory_entries
    op.create_table("working_memory_entries",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.String(36),
                  sa.ForeignKey("collaboration_workspaces.id"), nullable=False, index=True),
        sa.Column("agent_id", sa.String(36), nullable=False),
        sa.Column("entry_type", sa.String(32), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("visible_to_demand", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("visible_to_supply", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )


def downgrade():
    op.drop_table("working_memory_entries")
    op.drop_table("forum_votes")
    op.drop_table("forum_replies")
    op.drop_table("collaboration_workspaces")
    op.drop_table("forum_topics")
    op.drop_table("matches")
    op.drop_table("async_tasks")
    op.drop_table("auth_tokens")
    op.drop_table("agent_preferences")
    op.drop_table("discovered_demands")
    op.drop_table("unclaimed_suppliers")
    op.drop_table("capability_profiles")
    op.drop_table("demands")
    op.drop_table("users")
    op.execute("DROP TYPE IF EXISTS matchstatus")
    op.execute("DROP TYPE IF EXISTS profiletype")
    op.execute("DROP TYPE IF EXISTS demandstatus")

