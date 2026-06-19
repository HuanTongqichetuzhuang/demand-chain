"""
协作工作区服务 — 供需双方Agent共同记录需求细化与方案讨论。
需求方可授权供给方关注进展；双方Agent可读写工作记忆。
"""
import json
import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.models import (
    CollaborationWorkspace, WorkingMemoryEntry, Match, MatchStatus
)

logger = logging.getLogger(__name__)

ENTRY_TYPES = {
    "clarification": "需求澄清",
    "spec_refinement": "指标细化",
    "proposal": "方案建议",
    "decision": "决策记录",
    "progress": "进展更新",
    "blocker": "遇到的障碍",
}


class CollaborationService:
    def __init__(self, session: AsyncSession):
        self.session = session

    # ============================================================
    # 工作区管理
    # ============================================================

    async def create_workspace(
        self, match_id: str, demand_id: str,
        demand_agent_id: str, supply_agent_id: str
    ) -> CollaborationWorkspace:
        ws = CollaborationWorkspace(
            id=str(uuid4()),
            match_id=match_id,
            demand_id=demand_id,
            demand_agent_id=demand_agent_id,
            supply_agent_id=supply_agent_id,
            working_memory={"entries": [], "last_updated": datetime.now(timezone.utc).isoformat()},
        )
        self.session.add(ws)
        await self.session.commit()
        logger.info(f"[WorkSpace] 创建: {ws.id[:8]}... 需求={demand_id[:8]}...")
        return ws

    async def get_workspace(self, workspace_id: str) -> Optional[CollaborationWorkspace]:
        result = await self.session.execute(
            select(CollaborationWorkspace).where(CollaborationWorkspace.id == workspace_id)
        )
        return result.scalar_one_or_none()

    async def get_workspace_by_match(self, match_id: str) -> Optional[CollaborationWorkspace]:
        result = await self.session.execute(
            select(CollaborationWorkspace).where(CollaborationWorkspace.match_id == match_id)
        )
        return result.scalar_one_or_none()

    # ============================================================
    # 工作记忆
    # ============================================================

    async def add_entry(
        self, workspace_id: str, agent_id: str,
        entry_type: str, content: str,
        visible_to_demand: bool = True, visible_to_supply: bool = True,
    ) -> WorkingMemoryEntry:
        ws = await self.get_workspace(workspace_id)
        if not ws:
            raise ValueError("工作区不存在")

        entry = WorkingMemoryEntry(
            id=str(uuid4()),
            workspace_id=workspace_id,
            agent_id=agent_id,
            entry_type=entry_type,
            content=content,
            visible_to_demand=visible_to_demand,
            visible_to_supply=visible_to_supply,
        )
        self.session.add(entry)

        # 更新工作区记忆摘要
        if ws.working_memory is None:
            ws.working_memory = {"entries": []}
        ws.working_memory["entries"].append({
            "id": entry.id,
            "type": entry_type,
            "content": content[:200],
            "timestamp": entry.created_at.isoformat(),
        })
        ws.working_memory["last_updated"] = datetime.now(timezone.utc).isoformat()

        await self.session.commit()
        logger.info(f"[WorkSpace] 新记忆: {entry_type} 来自 {agent_id[:8]}...")
        return entry

    async def get_entries(
        self, workspace_id: str, agent_role: str = "any", limit: int = 50
    ) -> list[WorkingMemoryEntry]:
        query = select(WorkingMemoryEntry).where(
            WorkingMemoryEntry.workspace_id == workspace_id
        ).order_by(desc(WorkingMemoryEntry.created_at)).limit(limit)
        result = await self.session.execute(query)
        entries = list(result.scalars().all())

        if agent_role == "demand":
            entries = [e for e in entries if e.visible_to_demand]
        elif agent_role == "supply":
            entries = [e for e in entries if e.visible_to_supply]

        return entries

    # ============================================================
    # 授权与关注
    # ============================================================

    async def grant_consent(self, workspace_id: str) -> CollaborationWorkspace:
        """需求方授权供给方参与协作"""
        ws = await self.get_workspace(workspace_id)
        if not ws:
            raise ValueError("工作区不存在")
        ws.consent_granted = True
        ws.consent_granted_at = datetime.now(timezone.utc)
        ws.status = "active"
        await self.session.commit()
        logger.info(f"[WorkSpace] 需求方已授权: {workspace_id[:8]}...")
        return ws

    async def revoke_consent(self, workspace_id: str) -> CollaborationWorkspace:
        """需求方撤销授权"""
        ws = await self.get_workspace(workspace_id)
        if not ws:
            raise ValueError("工作区不存在")
        ws.consent_granted = False
        ws.status = "paused"
        await self.session.commit()
        return ws

    async def follow_demand(self, workspace_id: str) -> CollaborationWorkspace:
        """供给方关注需求进展"""
        ws = await self.get_workspace(workspace_id)
        if not ws:
            raise ValueError("工作区不存在")
        if not ws.consent_granted:
            raise ValueError("需求方尚未授权，无法关注")
        ws.following = True
        await self.session.commit()
        return ws

    async def unfollow_demand(self, workspace_id: str) -> CollaborationWorkspace:
        ws = await self.get_workspace(workspace_id)
        if not ws:
            raise ValueError("工作区不存在")
        ws.following = False
        await self.session.commit()
        return ws

    # ============================================================
    # 序列化
    # ============================================================

    def to_dict(self, ws: CollaborationWorkspace, entries: list = None) -> dict:
        return {
            "workspace_id": ws.id,
            "match_id": ws.match_id,
            "demand_id": ws.demand_id,
            "consent_granted": ws.consent_granted,
            "following": ws.following,
            "status": ws.status,
            "working_memory_summary": ws.working_memory,
            "entries": [
                {
                    "id": e.id,
                    "type": e.entry_type,
                    "type_label": ENTRY_TYPES.get(e.entry_type, e.entry_type),
                    "content": e.content,
                    "agent_id": e.agent_id[:8],
                    "visible_to_demand": e.visible_to_demand,
                    "visible_to_supply": e.visible_to_supply,
                    "created_at": e.created_at.isoformat(),
                }
                for e in (entries or [])
            ],
            "created_at": ws.created_at.isoformat(),
        }

