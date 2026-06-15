"""修复第7条翻译"""
import asyncio, sys
sys.path.insert(0, '/app')
from src.shared.database import async_session
from src.shared.models import Demand
from sqlalchemy import select

async def fix():
    async with async_session() as s:
        r = await s.execute(select(Demand).where(Demand.id.like('fa5ee6%')))
        d = r.scalar_one_or_none()
        if d:
            d.raw_text = '特色作物研究计划（Specialty Crop Research Initiative, USDA）——美国农业部发布的研究资助计划，旨在支持特色作物的研究、推广和教育项目，涵盖作物育种、病虫害防治、食品安全和质量改进等领域。'
            await s.commit()
            print('✅ 已修复')
            print(f'  {d.raw_text[:80]}')
        else:
            print('未找到')
asyncio.run(fix())
