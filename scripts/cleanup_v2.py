"""第2轮清理：删除剩余的 GitHub Issues 数据"""
import asyncio, sys
sys.path.insert(0, '/app')
from src.shared.database import async_session
from src.shared.models import Demand, Match, MatchOutcome
from sqlalchemy import select, delete

GITHUB_PATTERNS_V2 = [
    "<!--",
    "Please target the `master` branch",
    "### 🚀 The feature",
    "Add CameraFeed support",
    "Add dynamic dock slots",
    "Add \"RGB Average\" remap",
    "merge multiple ArrayMeshes",
    "R/F keys for local up/down",
    "temperature sensor for Netatmo",
    "Provide shutdown() method for",
    "extend torch.distributed",
    "pytorch should allow setuptools",
]

async def main():
    async with async_session() as s:
        r = await s.execute(select(Demand).where(Demand.user_id == 'crawler'))
        to_delete = []
        for d in r.scalars().all():
            text = d.raw_text or ""
            for pat in GITHUB_PATTERNS_V2:
                if pat in text:
                    to_delete.append(d.id)
                    print(f"  删除 [{d.id[:8]}] {d.raw_text[:60]}...")
                    break
        
        if to_delete:
            await s.execute(delete(Match).where(Match.demand_id.in_(to_delete)))
            await s.execute(delete(MatchOutcome).where(MatchOutcome.demand_id.in_(to_delete)))
            await s.execute(delete(Demand).where(Demand.id.in_(to_delete)))
            await s.commit()
            print(f"\n删除了 {len(to_delete)} 条剩余 GitHub Issues")
        else:
            print("没有找到更多 GitHub Issues 数据")
asyncio.run(main())
