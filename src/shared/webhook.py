"""
Agent Webhook 推送 — 平台主动通知Agent（代替轮询）。

新匹配产生 / L3确认请求 / 需求状态变更 → POST 到 Agent 注册的 Webhook URL。
Agent 不需要每秒轮询——事件发生即刻推送。
"""
import json
import logging
from datetime import datetime, timezone
from enum import Enum

import httpx

logger = logging.getLogger(__name__)


class WebhookEvent(str, Enum):
    NEW_MATCH = "new_match"           # 新匹配
    L3_CONFIRMATION = "l3_confirm"    # L3信息确认
    MATCH_EXPIRING = "match_expiring" # 匹配即将过期
    DEMAND_STATUS = "demand_status"   # 需求状态变更
    COLLABORATION_UPDATE = "collab_update" # 协作工作区更新


class AgentWebhookService:
    """Agent Webhook 推送服务"""

    def __init__(self):
        # agent_id → webhook_url 映射（实际数据库存储，这里用内存）
        self._registry: dict[str, str] = {}

    def register(self, agent_id: str, webhook_url: str):
        """Agent注册时存储其Webhook URL"""
        self._registry[agent_id] = webhook_url
        logger.info(f"[Webhook] 注册: {agent_id[:8]}... -> {webhook_url[:40]}...")

    def unregister(self, agent_id: str):
        self._registry.pop(agent_id, None)

    async def push(self, agent_id: str, event: WebhookEvent, payload: dict) -> bool:
        """向Agent推送事件"""
        webhook_url = self._registry.get(agent_id)
        if not webhook_url:
            logger.debug(f"[Webhook] {agent_id[:8]}.. 未注册，跳过")
            return False

        body = {
            "source": "demand-chain-platform",
            "event": event.value,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "payload": payload,
        }

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(webhook_url, json=body)
                if resp.status_code in (200, 202, 204):
                    logger.info(f"[Webhook] 推送成功: {agent_id[:8]}... {event.value}")
                    return True
                else:
                    logger.warning(f"[Webhook] HTTP {resp.status_code} for {agent_id[:8]}...")
                    return False
        except Exception as e:
            logger.warning(f"[Webhook] 推送失败: {agent_id[:8]}... {type(e).__name__}")
            return False

    async def notify_new_match(self, agent_id: str, match_id: str,
                                 demand_title: str, supplier_name: str, score: float):
        """推送新匹配通知"""
        return await self.push(agent_id, WebhookEvent.NEW_MATCH, {
            "match_id": match_id,
            "demand_title": demand_title[:100],
            "supplier_name": supplier_name,
            "score": score,
            "action_url": f"http://8.154.26.92:8000/matches/{match_id}",
            "message": f"你的需求「{demand_title[:40]}」收到新匹配：{supplier_name}（得分 {score:.2f}）"
        })

    async def notify_l3_confirm(self, agent_id: str, match_id: str,
                                  info_type: str, expires_in_hours: int):
        """推送L3确认请求"""
        return await self.push(agent_id, WebhookEvent.L3_CONFIRMATION, {
            "match_id": match_id,
            "info_type": info_type,
            "expires_in_hours": expires_in_hours,
            "expires_at": datetime.now(timezone.utc).isoformat(),  # TODO: 真实计算
            "message": f"对方请求确认 {info_type} 信息。{expires_in_hours}小时内处理，否则自动拒绝。"
        })

    async def notify_match_expiring(self, agent_id: str, match_id: str, hours_left: int):
        return await self.push(agent_id, WebhookEvent.MATCH_EXPIRING, {
            "match_id": match_id,
            "hours_left": hours_left,
            "message": f"匹配将在 {hours_left} 小时内过期，请尽快处理。"
        })

    async def notify_demand_status(self, agent_id: str, demand_id: str,
                                     new_status: str, demand_title: str):
        """推送需求状态变更（给关注者）"""
        return await self.push(agent_id, WebhookEvent.DEMAND_STATUS, {
            "demand_id": demand_id,
            "new_status": new_status,
            "demand_title": demand_title[:100],
            "message": f"你关注的需求「{demand_title[:40]}」状态变更为 {new_status}"
        })

    async def notify_collaboration(self, agent_id: str, workspace_id: str,
                                     entry_type: str, content: str):
        """推送协作工作区更新"""
        return await self.push(agent_id, WebhookEvent.COLLABORATION_UPDATE, {
            "workspace_id": workspace_id,
            "entry_type": entry_type,
            "content": content[:200],
            "message": f"协作工作区有新{entry_type}记录"
        })


# 全局实例
webhook_service = AgentWebhookService()
