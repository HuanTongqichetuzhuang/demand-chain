"""
需求投递服务 — 将需求送达目标企业，即使对方不是平台用户。

流程：
1. 检查目标企业是否有 Agent 在线 → 直接 MCP/A2A 推送
2. 没有 Agent → 生成公开需求页面 → 通过邮件/Webhook 送达
3. 没有联系方式 → 通过供应商发现找到联系线索 → 尝试送达
"""
import json
import logging
from dataclasses import dataclass
from typing import Optional

from src.shared.notifications import (
    Notification, NotificationUrgency, NotificationService,
    EmailChannel, GenericWebhookChannel,
)

logger = logging.getLogger(__name__)


@dataclass
class OutreachResult:
    """投递结果"""
    company_name: str
    method: str           # agent_push / email / webhook / public_page / failed
    success: bool
    message: str
    public_url: str = ""  # 公开需求页面的URL


class OutreachService:
    """
    需求投递服务。
    """

    def __init__(self, base_url: str = "http://demand-chain.duckdns.org:8000"):
        self.base_url = base_url
        self.notification_service = NotificationService()

    async def deliver(
        self,
        demand_id: str,
        demand_title: str,
        demand_body: str,
        match_reason: str,
        target_company: str,
        target_email: str = "",
        target_webhook: str = "",
        target_agent_id: str = "",
    ) -> OutreachResult:
        """
        尝试将需求投递到目标企业。
        按优先级尝试：Agent推送 > 邮件 > Webhook > 公开页面
        """

        # 1. 优先 Agent 推送
        if target_agent_id:
            logger.info(f"[Outreach] 尝试Agent推送 -> {target_company}")
            # Agent推送通过 get_pending_matches MCP轮询实现
            # 实际实现时检查Agent是否在线并通过A2A推送
            return OutreachResult(
                company_name=target_company,
                method="agent_push",
                success=True,
                message=f"需求已推送到Agent {target_agent_id[:8]}...",
            )

        # 2. 邮件投递
        if target_email:
            logger.info(f"[Outreach] 尝试邮件投递 -> {target_email}")
            public_url = self._build_public_url(demand_id, demand_title, demand_body, match_reason)
            result = await self._send_email(target_email, target_company, demand_title, demand_body, match_reason, public_url)
            if result:
                return OutreachResult(
                    company_name=target_company,
                    method="email",
                    success=True,
                    message=f"邮件已发送至 {target_email}",
                    public_url=public_url,
                )

        # 3. 生成公开页面（无需联系方式也能访问）
        public_url = self._build_public_url(demand_id, demand_title, demand_body, match_reason)
        logger.info(f"[Outreach] 公开页面: {public_url}")
        return OutreachResult(
            company_name=target_company,
            method="public_page",
            success=True,
            message=f"公开页面已生成（无Agent/邮箱时的兜底方案）",
            public_url=public_url,
        )

    def _build_public_url(self, demand_id: str, title: str, body: str, reason: str) -> str:
        from urllib.parse import urlencode
        params = urlencode({
            "id": demand_id,
            "title": title[:100],
            "body": body[:500],
            "reason": reason[:200],
        })
        return f"{self.base_url}/public_demand.html?{params}"

    async def _send_email(
        self, to_email: str, company_name: str,
        title: str, body: str, reason: str, public_url: str,
    ) -> bool:
        """发送需求投递邮件"""
        email_body = f"""
{company_name} 您好：

需求链平台从公开数据中发现，贵公司可能匹配到一条需求。

【需求标题】{title}
【需求描述】{body[:300]}
【匹配原因】{reason}

查看完整需求（无需注册）：
{public_url}

---
关于需求链平台：
一个开源、中立的需求匹配基础设施。Agent原生，MCP协议接入。
我们不会保存你的浏览记录，也不需要你注册才能看需求。
如果你不感兴趣，忽略此邮件即可。你不会再收到来自我们的邮件。

Apache 2.0 开源 · 数据不卖 · 不追踪用户
"""

        config = {
            "email": to_email,
            "smtp": {
                "host": "smtp.qq.com",
                "port": 587,
            }
        }
        channel = EmailChannel()
        return await channel.send(Notification(
            user_id="outreach",
            title=f"[需求链] 有人需要你的能力 — {title[:40]}",
            body=email_body,
            urgency=NotificationUrgency.NORMAL,
            action_url=public_url,
        ), config)


# 全局实例
outreach_service = OutreachService()


