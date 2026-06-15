from datetime import datetime
from uuid import uuid4

from sqlalchemy import String, Text, DateTime, Float, Integer, ForeignKey, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector

from src.shared.database import Base

import enum




class User(Base):
    __tablename__ = "users"
    
    human_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    country: Mapped[str] = mapped_column(String(128), default="")
    api_key: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    email_notify: Mapped[bool] = mapped_column(default=True)
    avatar: Mapped[str | None] = mapped_column(Text, nullable=True)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    email_verified: Mapped[bool] = mapped_column(default=False)
    verify_token: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.now)
    last_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class DemandStatus(str, enum.Enum):
    NEW = "new"
    STRUCTURING = "structuring"
    OPEN = "open"
    MATCHING = "matching"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CANCELLED = "cancelled"
    UNRESOLVABLE = "unresolvable"
    CLOSED = "closed"


class MatchStatus(str, enum.Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    EXPIRED = "expired"


class ProfileType(str, enum.Enum):
    INDIVIDUAL = "individual"
    TEAM = "team"
    COMPANY = "company"
    RESEARCH = "research"
    GOVERNMENT = "government"


class OutcomeStatus(str, enum.Enum):
    """匹配结果追踪 — 从匹配到合作完成的完整链路"""
    MATCHED = "matched"
    CONTACTED = "contacted"
    NEGOTIATING = "negotiating"
    SUCCESS = "success"
    FAILED = "failed"


class Demand(Base):
    __tablename__ = "demands"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    structured_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536), nullable=True)
    category: Mapped[str | None] = mapped_column(String(128), index=True, nullable=True)
    sub_category: Mapped[str | None] = mapped_column(String(128), nullable=True)
    classification_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    search_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    discipline_path: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    ipc_codes: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    process_categories: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[DemandStatus] = mapped_column(SAEnum(DemandStatus), default=DemandStatus.NEW, index=True)
    visibility: Mapped[str] = mapped_column(String(32), default="public")
    country_restrictions: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    parent_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("demands.id"), nullable=True)
    interest_count: Mapped[int] = mapped_column(Integer, default=1)
    duplicate_group_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    interest_users: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True, default=list)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    children = relationship("Demand", backref="parent", remote_side="Demand.id", lazy="selectin")
    matches = relationship("Match", back_populates="demand", lazy="selectin")


class CapabilityProfile(Base):
    __tablename__ = "capability_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    agent_card_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536), nullable=True)
    profile_type: Mapped[ProfileType] = mapped_column(SAEnum(ProfileType), default=ProfileType.INDIVIDUAL)
    country: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_claimed: Mapped[bool] = mapped_column(default=True)
    verified: Mapped[bool] = mapped_column(default=False)
    trust_score: Mapped[float] = mapped_column(Float, default=0.0)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    matches = relationship("Match", back_populates="profile", lazy="selectin")


class UnclaimedSupplier(Base):
    __tablename__ = "unclaimed_suppliers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(256), index=True, nullable=False)
    capabilities: Mapped[dict] = mapped_column(JSONB, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536), nullable=True)
    data_sources: Mapped[list[str]] = mapped_column(JSONB, default=list)
    contact_hints: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    country: Mapped[str | None] = mapped_column(String(64), nullable=True)

    discovered_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class DiscoveredDemand(Base):
    """从公开数据源发现的需求"""
    __tablename__ = "discovered_demands"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    source: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    source_url: Mapped[str] = mapped_column(String(512), nullable=True)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    inferred_category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    inferred_discipline: Mapped[str | None] = mapped_column(String(128), nullable=True)
    deadline: Mapped[str | None] = mapped_column(String(32), nullable=True)
    budget_hint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    organization: Mapped[str | None] = mapped_column(String(256), nullable=True)
    fingerprint: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    is_imported: Mapped[bool] = mapped_column(default=False)  # 是否已转为正式需求

    discovered_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AgentPreference(Base):
    """Agent 需求偏好 — 人类或Agent设置，筛选想接收的需求分类"""
    __tablename__ = "agent_preferences"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    agent_id: Mapped[str] = mapped_column(String(36), index=True, unique=True, nullable=False)
    preferred_categories: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)  # 选中的行业分类，null=接收全部
    preferred_disciplines: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)  # 选中的学科
    preferred_ipc: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)  # 选中的IPC代码
    auto_select: Mapped[bool] = mapped_column(default=False)  # Agent自动选？还是人类手动选？
    notify_only_preferred: Mapped[bool] = mapped_column(default=True)  # 仅通知偏好内的需求？
    updated_by: Mapped[str | None] = mapped_column(String(36), nullable=True)  # "human" | "agent"

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AuthToken(Base):
    """持久化认证 Token — 替代 auth.py 中的内存 _tokens dict"""
    __tablename__ = "auth_tokens"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    human_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    agent_id: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AsyncTask(Base):
    """持久化异步任务 — 替代 task_manager.py 中的内存 _tasks dict"""
    __tablename__ = "async_tasks"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    human_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    label: Mapped[str] = mapped_column(String(256), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="running", index=True)
    result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)


class Match(Base):
    __tablename__ = "matches"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    demand_id: Mapped[str] = mapped_column(String(36), ForeignKey("demands.id"), index=True, nullable=False)
    profile_id: Mapped[str] = mapped_column(String(36), ForeignKey("capability_profiles.id"), index=True, nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[MatchStatus] = mapped_column(SAEnum(MatchStatus), default=MatchStatus.PENDING)
    is_unclaimed: Mapped[bool] = mapped_column(default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    demand = relationship("Demand", back_populates="matches")
    profile = relationship("CapabilityProfile", back_populates="matches")


class MatchOutcome(Base):
    """匹配结果追踪 — 记录匹配后的完整链路（联系→谈判→成功/失败），驱动数据飞轮"""
    __tablename__ = "match_outcomes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    match_id: Mapped[str] = mapped_column(String(36), ForeignKey("matches.id"), index=True, nullable=False)
    demand_id: Mapped[str] = mapped_column(String(36), ForeignKey("demands.id"), index=True, nullable=False)
    supplier_id: Mapped[str] = mapped_column(String(36), ForeignKey("capability_profiles.id"), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default=OutcomeStatus.MATCHED.value, index=True)
    outcome_detail: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    match = relationship("Match", lazy="selectin")


class CategoryWeight(Base):
    """分类交叉权重 — 数据飞轮自动调整，用于匹配引擎的动态权重"""
    __tablename__ = "category_weights"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    demand_category: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    supplier_category: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    weight: Mapped[float] = mapped_column(Float, default=0.5)

    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ============================================================
# 协作工作区 — 供需双方Agent共同维护的工作记忆
# ============================================================

class CollaborationWorkspace(Base):
    __tablename__ = "collaboration_workspaces"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    match_id: Mapped[str] = mapped_column(String(36), ForeignKey("matches.id"), unique=True, nullable=False)
    demand_id: Mapped[str] = mapped_column(String(36), ForeignKey("demands.id"), index=True, nullable=False)
    demand_agent_id: Mapped[str] = mapped_column(String(36), nullable=False)
    supply_agent_id: Mapped[str] = mapped_column(String(36), nullable=False)

    # 工作记忆：双方Agent共同记录的需求细化、方案讨论、进展
    working_memory: Mapped[dict | None] = mapped_column(JSONB, nullable=True, default=list)

    # 需求方授权
    consent_granted: Mapped[bool] = mapped_column(default=False)
    consent_granted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # 供给方是否关注需求进展
    following: Mapped[bool] = mapped_column(default=False)

    # 协作状态
    status: Mapped[str] = mapped_column(String(32), default="pending")  # pending/active/paused/completed

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class WorkingMemoryEntry(Base):
    """工作记忆单条记录"""
    __tablename__ = "working_memory_entries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    workspace_id: Mapped[str] = mapped_column(String(36), ForeignKey("collaboration_workspaces.id"), index=True, nullable=False)
    agent_id: Mapped[str] = mapped_column(String(36), nullable=False)
    entry_type: Mapped[str] = mapped_column(String(32), nullable=False)  # clarification/spec_refinement/proposal/decision/progress
    content: Mapped[str] = mapped_column(Text, nullable=False)
    visible_to_demand: Mapped[bool] = mapped_column(default=True)
    visible_to_supply: Mapped[bool] = mapped_column(default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ============================================================
# 论坛系统
# ============================================================

class ForumTopic(Base):
    __tablename__ = "forum_topics"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    agent_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(64), index=True, nullable=False, default="general")
    demand_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("demands.id"), nullable=True, index=True)
    upvotes: Mapped[int] = mapped_column(Integer, default=0)
    is_pinned: Mapped[bool] = mapped_column(default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    replies = relationship("ForumReply", back_populates="topic", lazy="selectin", order_by="ForumReply.created_at")


class ForumReply(Base):
    __tablename__ = "forum_replies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    topic_id: Mapped[str] = mapped_column(String(36), ForeignKey("forum_topics.id"), index=True, nullable=False)
    agent_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    topic = relationship("ForumTopic", back_populates="replies")


class ForumVote(Base):
    __tablename__ = "forum_votes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    topic_id: Mapped[str] = mapped_column(String(36), ForeignKey("forum_topics.id"), index=True, nullable=False)
    agent_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    direction: Mapped[int] = mapped_column(Integer, nullable=False)  # 1=up, -1=down

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
