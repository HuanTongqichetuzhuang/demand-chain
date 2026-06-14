"""
E2E测试 — 验证核心链路：数据库建表 → 需求发布 → 读取。
需要本地 PostgreSQL 运行中，否则自动跳过。
"""
import asyncio
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.shared.database import engine, async_session, Base
from src.shared.models import Demand, DemandStatus
from sqlalchemy import text


def _db_reachable():
    """模块加载时检查 DB 是否可达"""
    async def _check():
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return True
        except Exception:
            return False
    try:
        return asyncio.run(_check())
    except Exception:
        return False


skip_if_no_db = pytest.mark.skipif(
    not _db_reachable(),
    reason="需要本地 PostgreSQL（docker compose up -d db）"
)


@skip_if_no_db
@pytest.mark.asyncio
async def test_db_tables():
    """测试：创建所有表"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("所有表已创建（demands, capability_profiles, unclaimed_suppliers, matches, forum_*, collaboration_*, working_memory_*）")

@skip_if_no_db
@pytest.mark.asyncio
async def test_create_demand():
    """测试：创建一条需求"""
    async with async_session() as session:
        from uuid import uuid4
        demand = Demand(
            id=str(uuid4()),
            user_id="test_user_001",
            raw_text="需要一个800°C高温管道裂缝检测传感器，精度±0.5%",
            category="传感器技术",
            status=DemandStatus.OPEN,
            structured_json={
                "classification": {"industry": "传感器技术", "application_scenario": "石化管道"},
                "requirement": {"core_need": "高温管道裂缝检测传感器"},
                "constraints": {"budget_range": "50-200万", "timeline": {"urgency": "紧急"}},
            },
        )
        session.add(demand)
        await session.commit()
        demand_id = demand.id
        print(f"需求已创建: id={demand_id[:8]}... 分类={demand.category}")

    async with async_session() as session:
        from sqlalchemy import select
        result = await session.execute(select(Demand).where(Demand.id == demand_id))
        d = result.scalar_one()
        assert d.raw_text.startswith("需要一个"), "需求文本不匹配"
        assert d.category == "传感器技术", "分类不匹配"
        print(f"需求回读成功: {d.structured_json['requirement']['core_need']}")

async def test_llm_adapter():
    """测试：LLM适配器（需要DeepSeek API Key）"""
    from src.adapters.llm_client import get_llm
    from src.shared.config import settings

    if not settings.deepseek_api_key or settings.deepseek_api_key == "sk-your-key-here":
        print("跳过LLM测试（未配置API Key）")
        return

    llm = get_llm()
    result = await llm.chat(
        "你是需求分析助手。用JSON回复：{\"category\": \"...\", \"summary\": \"...\"}",
        "需要一个能在800°C高温下检测管道裂缝的传感器"
    )
    print(f"LLM返回: {result[:100]}...")

async def main():
    print("=" * 50)
    print("需求链平台 E2E测试")
    print("=" * 50)

    await test_db_tables()
    print()

    await test_create_demand()
    print()

    await test_llm_adapter()
    print()

    print("=" * 50)
    print("核心链路验证通过")
    print("=" * 50)

if __name__ == "__main__":
    asyncio.run(main())
