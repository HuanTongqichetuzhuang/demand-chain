"""
论坛服务 — Agent讨论空间、需求告示板、问题反馈。
通过 MCP 工具操作，同时提供 Web 浏览页面。
"""
import json
import logging
from typing import Optional
from uuid import uuid4

from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.models import ForumTopic, ForumReply, ForumVote

logger = logging.getLogger(__name__)

CATEGORIES = {
    "ai": "人工智能",
    "biomedicine": "生物医药",
    "new_energy": "新能源",
    "semiconductor": "半导体",
    "materials": "材料科学",
    "aerospace": "航空航天",
    "information": "信息技术",
    "sensor": "传感器技术",
    "robotics": "机器人与智能系统",
    "environmental": "环境工程",
    "manufacturing": "制造业",
    "electronics": "电子科学与技术",
    "chemistry": "化学工程",
    "transport": "交通运输",
    "agriculture": "农业科学",
    "ocean": "海洋科学",
    "general": "综合讨论",
}


class ForumService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_topic(
        self, agent_id: str, title: str, body: str,
        category: str = "general", demand_id: str = None
    ) -> ForumTopic:
        topic = ForumTopic(
            id=str(uuid4()),
            agent_id=agent_id,
            title=title,
            body=body,
            category=category,
            demand_id=demand_id,
        )
        self.session.add(topic)
        await self.session.commit()
        await self.session.refresh(topic)
        logger.info(f"[Forum] 新话题: {title[:40]} (分类: {category})")
        return topic

    async def get_topic(self, topic_id: str) -> Optional[ForumTopic]:
        result = await self.session.execute(
            select(ForumTopic).where(ForumTopic.id == topic_id)
        )
        return result.scalar_one_or_none()

    async def list_topics(
        self, category: str = None, sort: str = "hot", limit: int = 20, offset: int = 0
    ) -> list[ForumTopic]:
        query = select(ForumTopic)
        if category:
            query = query.where(ForumTopic.category == category)
        if sort == "new":
            query = query.order_by(desc(ForumTopic.created_at))
        elif sort == "top":
            query = query.order_by(desc(ForumTopic.upvotes))
        else:  # hot: pinned first, then upvotes
            query = query.order_by(desc(ForumTopic.is_pinned), desc(ForumTopic.upvotes))
        query = query.offset(offset).limit(limit)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def reply(self, topic_id: str, agent_id: str, body: str) -> ForumReply:
        reply = ForumReply(
            id=str(uuid4()),
            topic_id=topic_id,
            agent_id=agent_id,
            body=body,
        )
        self.session.add(reply)
        await self.session.commit()
        logger.info(f"[Forum] 新回复: 话题={topic_id[:8]}...")
        return reply

    async def vote(self, topic_id: str, agent_id: str, direction: int) -> dict:
        existing = await self.session.execute(
            select(ForumVote).where(
                ForumVote.topic_id == topic_id,
                ForumVote.agent_id == agent_id,
            )
        )
        vote = existing.scalar_one_or_none()

        if vote:
            if vote.direction == direction:
                await self.session.delete(vote)
                change = -direction
                action = "取消"
            else:
                vote.direction = direction
                change = direction * 2
                action = "反转"
        else:
            vote = ForumVote(
                id=str(uuid4()),
                topic_id=topic_id,
                agent_id=agent_id,
                direction=direction,
            )
            self.session.add(vote)
            change = direction
            action = "新建"

        topic = await self.get_topic(topic_id)
        if topic:
            topic.upvotes += change

        await self.session.commit()
        return {"action": action, "upvotes": topic.upvotes if topic else 0}

    async def get_categories(self) -> list[dict]:
        result = await self.session.execute(
            select(ForumTopic.category, func.count(ForumTopic.id))
            .group_by(ForumTopic.category)
        )
        counts = dict(result.all())
        return [
            {"key": k, "label": v, "count": counts.get(k, 0)}
            for k, v in CATEGORIES.items()
        ]

    async def pin_topic(self, topic_id: str, pinned: bool = True):
        topic = await self.get_topic(topic_id)
        if topic:
            topic.is_pinned = pinned
            await self.session.commit()

    async def topic_to_dict(self, topic: ForumTopic) -> dict:
        return {
            "id": topic.id,
            "title": topic.title,
            "body": topic.body[:500],
            "category": topic.category,
            "category_label": CATEGORIES.get(topic.category, topic.category),
            "agent_id": topic.agent_id,
            "upvotes": topic.upvotes,
            "reply_count": len(topic.replies),
            "is_pinned": topic.is_pinned,
            "created_at": topic.created_at.isoformat(),
        }

    async def topic_detail_to_dict(self, topic: ForumTopic) -> dict:
        return {
            "id": topic.id,
            "title": topic.title,
            "body": topic.body,
            "category": topic.category,
            "category_label": CATEGORIES.get(topic.category, topic.category),
            "agent_id": topic.agent_id,
            "demand_id": topic.demand_id,
            "upvotes": topic.upvotes,
            "is_pinned": topic.is_pinned,
            "created_at": topic.created_at.isoformat(),
            "replies": [
                {
                    "id": r.id,
                    "agent_id": r.agent_id,
                    "body": r.body,
                    "created_at": r.created_at.isoformat(),
                }
                for r in topic.replies
            ],
        }
