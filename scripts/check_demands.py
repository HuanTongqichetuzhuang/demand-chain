"""检查需求数据 — 详细"""
import asyncio, sys, re
sys.path.insert(0, '/app')
from src.shared.database import async_session
from src.shared.models import Demand
from sqlalchemy import select, func

def is_english(text):
    if not text: return False
    cjk = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    return cjk == 0 and len(text.strip()) > 10

async def check():
    async with async_session() as s:
        r = await s.execute(select(Demand).where(Demand.user_id == 'crawler').order_by(Demand.created_at.desc()))
        crawler_demands = list(r.scalars().all())
        
        print(f"user_id=crawler 共 {len(crawler_demands)} 条:")
        for d in crawler_demands:
            eng = is_english(d.raw_text)
            source = "GITHUB" if 'github' in (d.raw_text or '').lower() else ("ENGLISH" if eng else "CHINESE")
            print(f"  [{source}] [{d.category}] {d.raw_text[:100]}...")
        
        # Also check all non-crawler demands for English
        r = await s.execute(select(Demand).where(Demand.user_id != 'crawler'))
        others = list(r.scalars().all())
        english_others = [d for d in others if is_english(d.raw_text)]
        print(f"\n非 crawler 需求中英文的: {len(english_others)} 条")
        for d in english_others[:5]:
            print(f"  [{d.user_id}] {d.raw_text[:100]}...")
asyncio.run(check())
