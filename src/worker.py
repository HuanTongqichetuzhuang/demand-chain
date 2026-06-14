"""
Platform Worker — 后台调度引擎。
每分钟扫描需求库，触发匹配。
"""
import asyncio
import logging

from src.shared.config import settings
from src.shared.database import async_session
from src.shared.models import Demand, DemandStatus

logger = logging.getLogger(__name__)


async def scan_and_match():
    while True:
        try:
            async with async_session() as session:
                result = await session.execute(
                    "SELECT count(*) FROM demands WHERE status = 'OPEN'"
                )
                count = result.scalar()
                if count and count > 0:
                    logger.info(f"[Worker] 发现 {count} 条待匹配需求")
                    await process_open_demands(session, count)
        except Exception as e:
            logger.error(f"[Worker] 扫描异常: {e}")
        await asyncio.sleep(settings.worker_interval_seconds)


async def process_open_demands(session, count: int):
    """处理待匹配需求 — 当前为桩实现，完整匹配逻辑待开发。"""
    logger.info(f"[Worker] 匹配引擎已触发，待匹配数={count}")
    # Phase 1 匹配逻辑：语义相似度 + pgvector
    # 此处为桩，后续迭代实现


async def main():
    logging.basicConfig(
        level=getattr(logging, settings.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger.info(f"[Worker] 启动，轮询间隔={settings.worker_interval_seconds}s")
    await scan_and_match()


if __name__ == "__main__":
    asyncio.run(main())
