"""
通知模块 — Agent 联系人类的所有渠道。
支持：对话内、微信（Server酱/企业微信）、飞书、邮件、通用Webhook。
"""
import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


class NotificationUrgency(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class Notification:
    user_id: str
    title: str
    body: str
    urgency: NotificationUrgency = NotificationUrgency.NORMAL
    action_url: Optional[str] = None
    demand_id: Optional[str] = None
    expires_at: Optional[datetime] = None


class BaseChannel(ABC):
    @abstractmethod
    async def send(self, notification: Notification, config: dict) -> bool:
        ...


# ============================================================
# 微信渠道
# ============================================================

class WechatServerChan(BaseChannel):
    """
    通过 Server酱 (sct.ftqq.com) 推送到微信。
    用户免费注册获取 SendKey，平台用它发通知到用户微信。
    免费额度：每天5条，够Phase 1用。
    """
    async def send(self, n: Notification, config: dict) -> bool:
        sendkey = config.get("wechat_serverchan_key")
        if not sendkey:
            return False
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    f"https://sctapi.ftqq.com/{sendkey}.send",
                    json={"title": n.title, "desp": f"{n.body}\n\n[查看详情]({n.action_url or ''})"}
                )
                ok = resp.status_code == 200
                logger.info(f"[Server酱] {n.title[:20]}... → {'OK' if ok else resp.status_code}")
                return ok
        except Exception as e:
            logger.error(f"[Server酱] 失败: {e}")
            return False


class WecomBotChannel(BaseChannel):
    """
    企业微信机器人 Webhook。
    用户在企业微信群中添加机器人，获取 Webhook URL。
    完全免费，不限量。
    """
    async def send(self, n: Notification, config: dict) -> bool:
        url = config.get("wecom_webhook_url")
        if not url:
            return False
        try:
            color = {"low": "info", "normal": "comment", "high": "warning", "critical": "warning"}
            payload = {
                "msgtype": "markdown",
                "markdown": {
                    "content": (
                        f"## {n.title}\n"
                        f"{n.body}\n\n"
                        f"> 紧急程度：{n.urgency.value} | "
                        f"{'[查看详情](' + n.action_url + ')' if n.action_url else ''}"
                    )
                }
            }
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(url, json=payload)
                ok = resp.status_code < 400
                logger.info(f"[企业微信] {n.title[:20]}... → {'OK' if ok else resp.status_code}")
                return ok
        except Exception as e:
            logger.error(f"[企业微信] 失败: {e}")
            return False


# ============================================================
# 飞书渠道
# ============================================================

class FeishuBotChannel(BaseChannel):
    """
    飞书机器人 Webhook。
    用户在飞书群中添加自定义机器人，获取 Webhook URL。
    完全免费，不限量。支持富文本卡片。
    """
    async def send(self, n: Notification, config: dict) -> bool:
        url = config.get("feishu_webhook_url")
        if not url:
            return False
        try:
            color_map = {"low": "blue", "normal": "green", "high": "orange", "critical": "red"}
            payload = {
                "msg_type": "interactive",
                "card": {
                    "header": {
                        "title": {"tag": "plain_text", "content": n.title},
                        "template": color_map.get(n.urgency.value, "green"),
                    },
                    "elements": [
                        {"tag": "div", "text": {"tag": "lark_md", "content": n.body}},
                        {"tag": "hr"},
                        {"tag": "note", "elements": [
                            {"tag": "plain_text", "content": f"紧急度: {n.urgency.value}  |  需求链平台"}
                        ]},
                    ]
                }
            }
            if n.action_url:
                payload["card"]["elements"].append({
                    "tag": "action",
                    "actions": [{"tag": "button", "text": {"tag": "plain_text", "content": "查看详情"}, "url": n.action_url, "type": "primary"}]
                })
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(url, json=payload)
                ok = resp.status_code < 400
                logger.info(f"[飞书] {n.title[:20]}... → {'OK' if ok else resp.status_code}")
                return ok
        except Exception as e:
            logger.error(f"[飞书] 失败: {e}")
            return False


# ============================================================
# 通用渠道
# ============================================================

class EmailChannel(BaseChannel):
    """通过 SMTP 发送邮件。默认网易企业邮箱。"""
    async def send(self, n: Notification, config: dict) -> bool:
        to_email = config.get("email")
        if not to_email:
            return False

        from src.shared.config import settings
        smtp_host = config.get("smtp_host") or settings.smtp_host or "smtp.qiye.163.com"
        smtp_port = int(config.get("smtp_port") or settings.smtp_port or 465)
        smtp_user = config.get("smtp_user") or settings.smtp_user
        smtp_pass = config.get("smtp_password") or settings.smtp_password

        if not smtp_user or not smtp_pass:
            logger.warning("[Email] SMTP未配置，无法发送")
            return False

        try:
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart

            msg = MIMEMultipart()
            msg["From"] = smtp_user
            msg["To"] = to_email
            msg["Subject"] = n.title

            body = f"""{n.body}

紧急程度: {n.urgency.value}

{f'查看详情: {n.action_url}' if n.action_url else ''}

---
此邮件由需求链平台自动发送。
不要回复此邮件——让你的Agent来需求链平台处理。"""
            msg.attach(MIMEText(body, "plain", "utf-8"))

            import asyncio
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, lambda: _sync_send(smtp_host, smtp_port, smtp_user, smtp_pass, msg))

            logger.info(f"[Email] 发送成功 -> {to_email}: {n.title[:30]}...")
            return True
        except Exception as e:
            logger.error(f"[Email] 发送失败 -> {to_email}: {e}")
            return False


def _sync_send(host, port, user, password, msg):
    import smtplib
    with smtplib.SMTP(host, port, timeout=15) as server:
        server.starttls()
        server.login(user, password)
        server.send_message(msg)


class GenericWebhookChannel(BaseChannel):
    async def send(self, n: Notification, config: dict) -> bool:
        url = config.get("webhook_url")
        if not url:
            return False
        try:
            payload = {"event": "demand_chain", "title": n.title, "body": n.body,
                       "urgency": n.urgency.value, "action_url": n.action_url, "demand_id": n.demand_id}
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(url, json=payload)
                return resp.status_code < 400
        except Exception as e:
            logger.error(f"[Webhook] 失败: {e}")
            return False


class InAppChannel(BaseChannel):
    """站内通知渠道 — NotificationService 的 notify() 方法已直接写入 DB，此渠道仅用于一致性"""
    async def send(self, n: Notification, config: dict) -> bool:
        return True


# ============================================================
# 通知服务
# ============================================================

class NotificationService:
    def __init__(self):
        self.channels = {
            "in_app": InAppChannel(),
            "wechat": WechatServerChan(),
            "wecom": WecomBotChannel(),
            "feishu": FeishuBotChannel(),
            "email": EmailChannel(),
            "webhook": GenericWebhookChannel(),
        }

    async def notify(self, notification: Notification, user_config: dict):
        # Always persist to database (in-app notification)
        try:
            from src.shared.database import async_session
            from src.shared.models import Notification as NotificationModel
            from uuid import uuid4
            async with async_session() as session:
                db_n = NotificationModel(
                    id=str(uuid4()),
                    user_id=notification.user_id,
                    title=notification.title,
                    body=notification.body,
                    channel="in_app",
                    urgency=notification.urgency.value,
                    action_url=notification.action_url,
                    demand_id=notification.demand_id,
                    is_read=False,
                )
                session.add(db_n)
                await session.commit()
        except Exception as e:
            logger.warning(f"[notify] DB persistence failed: {e}")

        # Send via configured external channels
        channels = user_config.get("notification", {}).get("channels", ["chat"])
        for ch_name in channels:
            if ch_name in self.channels:
                await self.channels[ch_name].send(notification, user_config.get("notification", {}))

    async def notify_new_match(self, user_id: str, demand_title: str, supplier_name: str,
                                score: float, match_id: str, user_config: dict):
        await self.notify(Notification(
            user_id=user_id,
            title=f"[新匹配] {demand_title[:30]}",
            body=f"{supplier_name}\n匹配度: {score:.0%}\n请在48小时内决定接受或拒绝。",
            urgency=NotificationUrgency.NORMAL,
            action_url=f"/matches/{match_id}",
        ), user_config)

    async def notify_l3_confirm(self, user_id: str, info_type: str, match_id: str,
                                 user_config: dict):
        await self.notify(Notification(
            user_id=user_id,
            title=f"!!! 需要确认L3信息: {info_type}",
            body=f"有一条敏感信息需要你确认后才能分享。12小时内未回复匹配可能过期。",
            urgency=NotificationUrgency.CRITICAL,
            action_url=f"/matches/{match_id}/confirm",
        ), user_config)

    async def notify_expiring(self, user_id: str, match_id: str, hours_left: int,
                               user_config: dict):
        await self.notify(Notification(
            user_id=user_id,
            title=f"!!! 匹配将在{hours_left}小时后过期",
            body=f"请尽快处理，超时将自动拒绝。",
            urgency=NotificationUrgency.CRITICAL,
            action_url=f"/matches/{match_id}",
        ), user_config)


notification_service = NotificationService()
