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
                r = await session.execute(
                    select(func.count(Demand.id)).where(Demand.status == DemandStatus.OPEN)
                )
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


async def main():
    logging.basicConfig(
        level=getattr(logging, settings.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger.info(f"[Worker] Started — matching every {MATCH_INTERVAL}s, "
                f"flywheel every {FLYWHEEL_INTERVAL}s, "
                f"health on :{HEALTH_PORT}")
    await asyncio.gather(health_server(), scan_and_match(), flywheel_cycle())


if __name__ == "__main__":
    asyncio.run(main())
