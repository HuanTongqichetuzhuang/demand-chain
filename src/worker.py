"""
Platform Worker — 后台调度引擎。
每 15 分钟扫描新入库的 OPEN 需求，触发增量匹配。
"""
import asyncio
import logging

from src.shared.config import settings
from src.shared.database import async_session
from src.shared.models import Demand, DemandStatus, Match
from sqlalchemy import select, func

logger = logging.getLogger(__name__)

MATCH_INTERVAL = 900  # 15 minutes


async def scan_and_match():
    while True:
        try:
            async with async_session() as session:
                # Count OPEN demands without existing matches
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
                    logger.info(f"[Worker] Matching done: {matched} candidate(s) across {total} demand(s)")
                else:
                    logger.debug(f"[Worker] No OPEN demands to match")
        except Exception as e:
            logger.error(f"[Worker] Error: {e}")
            import traceback
            traceback.print_exc()

        await asyncio.sleep(MATCH_INTERVAL)


async def main():
    logging.basicConfig(
        level=getattr(logging, settings.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger.info(f"[Worker] Started — matching every {MATCH_INTERVAL}s")
    await scan_and_match()


if __name__ == "__main__":
    asyncio.run(main())
