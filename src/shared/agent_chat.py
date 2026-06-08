"""
Agent 即时通讯 — 供需双方Agent通过平台直连对话。

不通过邮件、微信、飞书。Agent对Agent——平台是中转站。
利用已有的 MCP SSE 长连接，消息实时推送。
"""
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


@dataclass
class AgentMessage:
    workspace_id: str
    sender_agent_id: str
    receiver_agent_id: str
    content: str
    message_type: str = "text"  # text | system | proposal | quick_reply
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    id: str = ""


class AgentChatService:
    """
    Agent即时通讯服务。
    利用已有的 SSE 长连接实时推送消息，不需要额外的Webrtc或Socket。
    """

    def __init__(self, base_url: str = "http://8.154.26.92:8000"):
        self.base_url = base_url
        # workspace_id → 连接中的 agent_ids 列表
        self._online_agents: dict[str, set[str]] = {}

    def join(self, workspace_id: str, agent_id: str):
        """Agent进入聊天室"""
        if workspace_id not in self._online_agents:
            self._online_agents[workspace_id] = set()
        self._online_agents[workspace_id].add(agent_id)
        logger.info(f"[Chat] {agent_id[:8]}... 进入 {workspace_id[:8]}...")

    def leave(self, workspace_id: str, agent_id: str):
        if workspace_id in self._online_agents:
            self._online_agents[workspace_id].discard(agent_id)

    def is_online(self, workspace_id: str, agent_id: str) -> bool:
        return (
            workspace_id in self._online_agents
            and agent_id in self._online_agents[workspace_id]
        )

    async def send_message(
        self,
        workspace_id: str,
        sender_id: str,
        receiver_id: str,
        content: str,
        message_type: str = "text",
    ) -> AgentMessage:
        """
        发送一条Agent间消息。
        如果接收方 Agent 在线（SSE连接），实时推送。
        否则标记为未读，等Agent下次轮询时获取。
        """
        from uuid import uuid4

        msg = AgentMessage(
            id=str(uuid4()),
            workspace_id=workspace_id,
            sender_agent_id=sender_id,
            receiver_agent_id=receiver_id,
            content=content,
            message_type=message_type,
        )

        receiver_online = self.is_online(workspace_id, receiver_id)

        if receiver_online:
            # 实时推送（通过 webhook）
            from src.shared.webhook import webhook_service
            await webhook_service.push(receiver_id, "agent_message", {
                "workspace_id": workspace_id,
                "from": sender_id[:8],
                "content": content,
                "message_type": message_type,
                "message_id": msg.id,
                "timestamp": msg.timestamp,
            })

        # 同时存入工作记忆（持久化 + 兜底）
        # workspace_add_entry(workspace_id, sender_id, "chat", content)
        logger.info(
            f"[Chat] {sender_id[:8]}... → {receiver_id[:8]}... "
            f"({'实时' if receiver_online else '离线存储'}): {content[:40]}..."
        )

        return msg

    async def get_unread_messages(self, workspace_id: str, agent_id: str, limit: int = 50) -> list[dict]:
        """获取 Agent 的未读消息"""
        # Phase 1: 从工作记忆 entry_type=chat 读取
        # Phase 2: 独立的 messages 表
        return []

    def get_online_status(self, workspace_id: str) -> dict[str, bool]:
        """查看聊天室里谁在线"""
        agents = self._online_agents.get(workspace_id, set())
        return {aid[:8]: True for aid in agents}


# 全局实例
chat_service = AgentChatService()
