"""重分类现有需求 — 用新的二级分类体系设置 sub_category"""
import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

async def main():
    from src.shared.database import async_session
    from src.shared.models import Demand
    from src.shared.classification import classify_text
    from sqlalchemy import select

    async with async_session() as session:
        r = await session.execute(select(Demand))
        rows = list(r.scalars().all())

    updated = 0
    for d in rows:
        text = d.raw_text or ""
        if d.structured_json:
            text += " " + json.dumps(d.structured_json, ensure_ascii=False)
        cat, sub = classify_text(text)
        old_sub = getattr(d, "sub_category", None) or ""
        if sub and sub != old_sub:
            d.sub_category = sub
            updated += 1
            print(f"  {d.id[:8]} {d.category} → {sub} ({d.raw_text[:40]})")

    if updated:
        async with async_session() as session:
            for d in rows:
                if getattr(d, "sub_category", None):
                    session.add(d)
            await session.commit()
        print(f"\n✅ 已更新 {updated} 条需求的 sub_category")
    else:
        print("没有需要更新的需求")

if __name__ == "__main__":
    import json
    asyncio.run(main())
