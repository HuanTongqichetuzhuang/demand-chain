"""
Platform Worker — 后台调度引擎。
每 15 分钟扫描新入库的 OPEN 需求，触发增量匹配。
暴露 /health 端点供 Docker 健康检查，连续失败告警。
"""
import asyncio
import json
import logging
import time
from datetime import datetime, timezone

import httpx

from src.shared.config import settings
from src.shared.database import async_session
from src.shared.models import Demand, DemandStatus
from sqlalchemy import select, func

from src.shared.flywheel import run_learning_cycle

logger = logging.getLogger(__name__)

# 支持环境变量覆盖（兼容旧版配置）
import os as _os
MATCH_INTERVAL = int(_os.environ.get("WORKER_INTERVAL_SECONDS", "900"))  # 15 minutes
SUBSCRIPTION_INTERVAL = 300  # 5 minutes — 订阅匹配检查
FLYWHEEL_INTERVAL = 3600  # 1 hour — 数据飞轮学习周期
HEALTH_PORT = 8003
MAX_CONSECUTIVE_FAILURES = 3
MATCH_TIMEOUT_SECONDS = 60

# Health state
_healthy = True
_last_match_ts: float | None = None
_consecutive_failures = 0


# ── HTTP health server ───────────────────────────────────────────

async def health_server():
    """轻量 HTTP 服务，仅响应 /health 供 Docker healthcheck 探测。"""
    import asyncio as _a

    async def handle(reader: _a.StreamReader, writer: _a.StreamWriter):
        request = (await reader.read(1024)).decode("utf-8", errors="replace")
        status_line = "200 OK" if _healthy else "503 Service Unavailable"
        body = json.dumps({
            "status": "ok" if _healthy else "error",
            "consecutive_failures": _consecutive_failures,
        })
        response = (
            f"HTTP/1.1 {status_line}\r\n"
            f"Content-Type: application/json\r\n"
            f"Content-Length: {len(body)}\r\n"
            f"Connection: close\r\n\r\n"
            f"{body}"
        )
        writer.write(response.encode())
        await writer.drain()
        writer.close()

    server = await _a.start_server(handle, "0.0.0.0", HEALTH_PORT)
    logger.info(f"[Worker] Health server listening on :{HEALTH_PORT}")
    async with server:
        await server.serve_forever()


# ── Alert helper ─────────────────────────────────────────────────

_alerted_consecutive = False  # avoid flooding alerts on every cycle


async def send_alert(title: str, body: str):
    """通过 ALERT_WEBHOOK_URL 发送告警（支持 Server酱 / 企业微信机器人）。"""
    url = settings.alert_webhook_url
    if not url:
        logger.warning("[Worker] alert_webhook_url not set — skipping alert")
        return
    try:
        payload = {"title": title, "body": body}
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json=payload)
            logger.info(f"[Worker] Alert sent -> {resp.status_code}")
    except Exception as e:
        logger.error(f"[Worker] Failed to send alert: {e}")


# ── Core matching loop ───────────────────────────────────────────

async def scan_and_match():
    global _healthy, _last_match_ts, _consecutive_failures, _alerted_consecutive

    while True:
        start = time.monotonic()
        try:
            async with async_session() as session:
                from sqlalchemy import func as sa_func, select as sa_select
                stmt = sa_select(sa_func.count()).select_from(Demand).where(Demand.status == DemandStatus.OPEN)
                r = await session.execute(stmt)
                open_count = r.scalar() or 0

                if open_count > 0:
                    logger.info(f"[Worker] {open_count} OPEN demands — running matching engine")
                    from src.matching.engine import run_matching
                    result = await run_matching(dry_run=False)
                    matched = result.get("matched", 0)
                    total = result.get("total", 0)

                    elapsed = time.monotonic() - start
                    if elapsed > MATCH_TIMEOUT_SECONDS:
                        logger.warning(
                            f"[Worker] SLOW MATCH — {elapsed:.1f}s (> {MATCH_TIMEOUT_SECONDS}s limit): "
                            f"{matched} candidate(s) across {total} demand(s)"
                        )

                    logger.info(f"[Worker] Matching done ({elapsed:.1f}s): "
                                f"{matched} candidate(s) across {total} demand(s)")
                else:
                    logger.debug(f"[Worker] No OPEN demands to match")

            # Success — reset failure counter
            _healthy = True
            _last_match_ts = time.time()
            _consecutive_failures = 0
            _alerted_consecutive = False

        except Exception as e:
            _consecutive_failures += 1
            _healthy = _consecutive_failures < MAX_CONSECUTIVE_FAILURES
            logger.error(f"[Worker] Error (failure #{_consecutive_failures}): {e}")
            import traceback
            traceback.print_exc()

            if _consecutive_failures >= MAX_CONSECUTIVE_FAILURES and not _alerted_consecutive:
                _alerted_consecutive = True
                await send_alert(
                    title="[需求链 Worker] 连续匹配失败告警",
                    body=(
                        f"Worker 已连续 {_consecutive_failures} 次匹配失败。\n\n"
                        f"最后错误: {e}\n\n"
                        f"请登录服务器检查: docker logs dc-worker --tail 50"
                    ),
                )

        await asyncio.sleep(MATCH_INTERVAL)


async def flywheel_cycle():
    """数据飞轮学习周期 — 每小时处理一次 match_outcomes，更新信任分和权重。"""
    global _healthy

    while True:
        try:
            stats = await run_learning_cycle()
            if stats["processed"] > 0:
                logger.info(f"[Worker] 飞轮学习完成: {stats}")
            _healthy = True
        except Exception as e:
            logger.error(f"[Worker] 飞轮学习失败: {e}")
            import traceback
            traceback.print_exc()

        await asyncio.sleep(FLYWHEEL_INTERVAL)


# ── Subscription matching ─────────────────────────────────────────

async def subscription_check_cycle():
    """每5分钟检查新需求，匹配用户订阅并推送通知。"""
    global _healthy
    _last_checked_id: str | None = None

    while True:
        try:
            async with async_session() as session:
                from src.shared.models import DemandSubscription, Demand, DemandStatus, Notification
                from sqlalchemy import select, func as sa_func
                from uuid import uuid4

                # Get the latest demand id we've already processed
                if _last_checked_id is None:
                    r = await session.execute(
                        select(Demand).order_by(Demand.created_at.desc()).limit(1)
                    )
                    latest = r.scalar_one_or_none()
                    if latest:
                        _last_checked_id = latest.id
                    await asyncio.sleep(SUBSCRIPTION_INTERVAL)
                    continue

                # Find demands created after our last check
                r = await session.execute(
                    select(Demand).where(
                        Demand.status == DemandStatus.OPEN,
                        Demand.id > _last_checked_id
                    ).order_by(Demand.created_at.asc())
                )
                new_demands = list(r.scalars().all())
                if not new_demands:
                    await asyncio.sleep(SUBSCRIPTION_INTERVAL)
                    continue

                logger.info(f"[Worker] {len(new_demands)} new demand(s) — checking subscriptions")

                # Load all active subscriptions
                r = await session.execute(
                    select(DemandSubscription).where(DemandSubscription.is_active == True)
                )
                subscriptions = list(r.scalars().all())

                for demand in new_demands:
                    demand_text = f"{demand.raw_text or ''} {demand.category or ''} {demand.search_text or ''}".lower()

                    for sub in subscriptions:
                        # Check keywords match
                        keyword_match = False
                        if sub.keywords:
                            kw_list = [kw.lower() for kw in sub.keywords if kw]
                            for kw in kw_list:
                                if kw in demand_text:
                                    keyword_match = True
                                    break

                        # Check categories match
                        category_match = False
                        if sub.categories:
                            for cat in sub.categories:
                                if cat and cat.lower() == (demand.category or "").lower():
                                    category_match = True
                                    break

                        # If no filters, match everything
                        no_filters = not sub.keywords and not sub.categories
                        if not (no_filters or keyword_match or category_match):
                            continue

                        # Send notification
                        if sub.notify_web:
                            n = Notification(
                                id=str(uuid4()),
                                user_id=sub.user_id,
                                title=f"📋 新需求匹配: {demand.raw_text[:40]}...",
                                body=f"关键词: {', '.join(sub.keywords or [])} | "
                                     f"分类: {demand.category or '未知'}\n"
                                     f"{demand.raw_text[:200]}",
                                channel="subscription",
                                urgency="normal",
                                action_url=f"/demand_square.html?highlight={demand.id}",
                                is_read=False,
                            )
                            session.add(n)

                # Also send email notifications
                for sub in subscriptions:
                    if sub.notify_email:
                        # Find matching demands for this subscription
                        matching_demands = []
                        for demand in new_demands:
                            demand_text = f"{demand.raw_text or ''} {demand.category or ''} {demand.search_text or ''}".lower()
                            kw_match = any(kw.lower() in demand_text for kw in (sub.keywords or []) if kw)
                            cat_match = any(
                                cat.lower() == (demand.category or "").lower()
                                for cat in (sub.categories or [])
                            )
                            no_filters = not sub.keywords and not sub.categories
                            if no_filters or kw_match or cat_match:
                                matching_demands.append(demand)

                        if matching_demands:
                            from src.shared.notifications import notification_service, Notification as NotifObj, NotificationUrgency
                            from src.shared.models import User
                            r = await session.execute(select(User).where(User.human_id == sub.user_id))
                            user = r.scalar_one_or_none()
                            if user and user.email:
                                # Find user config for notification channels
                                user_config = {"notification": {"channels": ["email"]}}
                                try:
                                    await notification_service.notify(
                                        NotifObj(
                                            user_id=sub.user_id,
                                            title=f"[订阅] {sub.name} — {len(matching_demands)}条新需求",
                                            body="\n".join([f"• {d.raw_text[:80]}" for d in matching_demands[:5]]),
                                            urgency=NotificationUrgency.NORMAL,
                                            action_url="/demand_square.html",
                                        ),
                                        user_config,
                                    )
                                except Exception as e:
                                    logger.warning(f"[Worker] Email notify failed for {user.email}: {e}")

                await session.commit()
                _last_checked_id = new_demands[-1].id

        except Exception as e:
            logger.error(f"[Worker] Subscription check error: {e}")
            import traceback
            traceback.print_exc()

        await asyncio.sleep(SUBSCRIPTION_INTERVAL)


async def main():
    logging.basicConfig(
        level=getattr(logging, settings.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger.info(f"[Worker] Started — matching every {MATCH_INTERVAL}s, "
                f"subscription every {SUBSCRIPTION_INTERVAL}s, "
                f"flywheel every {FLYWHEEL_INTERVAL}s, "
                f"health on :{HEALTH_PORT}")
    await asyncio.gather(health_server(), scan_and_match(), subscription_check_cycle(), flywheel_cycle())


if __name__ == "__main__":
    asyncio.run(main())

