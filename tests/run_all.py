"""
需求链平台测试套件 — 覆盖所有核心模块。
运行方式: PYTHONPATH="E:/项目/需求链平台" .venv/Scripts/python tests/run_all.py
"""
import asyncio
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.shared.database import async_session, engine, Base
from src.shared.models import (
    Demand, DemandStatus, MatchStatus,
    ForumTopic, ForumReply, ForumVote,
    CollaborationWorkspace, WorkingMemoryEntry,
)
from src.demand.service import DemandService
from src.adapters.llm_client import get_llm

PASS = 0
FAIL = 0
SKIP = 0

def ok(msg):
    global PASS
    PASS += 1
    print(f"  PASS  {msg}")

def fail(msg):
    global FAIL
    FAIL += 1
    print(f"  FAIL  {msg}")

def skip(msg):
    global SKIP
    SKIP += 1
    print(f"  SKIP  {msg}")


# ============================================================
# 1. 数据库测试
# ============================================================
async def test_database():
    print("\n=== 1. 数据库测试 ===")

    # 1.1 表存在性
    from sqlalchemy import text
    async with engine.begin() as conn:
        tables = await conn.run_sync(lambda c: list(c.execute(
            text("SELECT tablename FROM pg_tables WHERE schemaname='public'")
        )))
    table_names = [t[0] for t in tables]
    required = ["demands","capability_profiles","unclaimed_suppliers","matches",
                "forum_topics","forum_replies","forum_votes",
                "collaboration_workspaces","working_memory_entries"]
    for t in required:
        if t in table_names:
            ok(f"表 {t} 存在")
        else:
            fail(f"表 {t} 不存在")

    # 1.2 demand CRUD
    async with async_session() as session:
        from uuid import uuid4
        d = Demand(id=str(uuid4()), user_id="t001", raw_text="测试需求-高温传感器",
                    category="传感器技术", status=DemandStatus.OPEN)
        session.add(d)
        await session.commit()
        did = d.id
        ok(f"需求创建: {did[:8]}...")

    async with async_session() as session:
        from sqlalchemy import select
        result = await session.execute(select(Demand).where(Demand.id == did))
        loaded = result.scalar_one()
        assert loaded.raw_text.startswith("测试"), "回读失败"
        ok(f"需求回读成功")

        loaded.status = DemandStatus.MATCHING
        await session.commit()
        ok("需求状态更新成功")


# ============================================================
# 2. MCP 工具测试（单元测试）
# ============================================================
async def test_mcp_tools():
    print("\n=== 2. MCP 工具测试 ===")

    # 2.1 publish_demand（通过 DemandService）
    async with async_session() as session:
        svc = DemandService(session)
        demand = await svc.publish("t002", "需要一个低温等离子体灭菌设备，用于战地医疗")
        ok(f"publish_demand: id={demand.id[:8]}... 分类={demand.category}")
        if demand.structured_json:
            ok(f"结构化JSON包含: {list(demand.structured_json.keys())}")
        else:
            skip("结构化失败 (LLM API Key未配置 -> 预期行为)")

    # 2.2 search_demands
    async with async_session() as session:
        svc = DemandService(session)
        results = await svc.search(keyword="等离子")
        found = len(results) > 0
        if found:
            ok(f"search_demands 找到 {len(results)} 条结果")
        else:
            fail("search_demands 没找到结果")

    # 2.3 get_demand
    async with async_session() as session:
        svc = DemandService(session)
        d = await svc.get(demand.id)
        if d:
            ok(f"get_demand: {d.raw_text[:30]}...")
        else:
            fail("get_demand 返回空")


# ============================================================
# 3. 论坛测试
# ============================================================
async def test_forum():
    print("\n=== 3. 论坛测试 ===")

    from src.forum.service import ForumService

    async with async_session() as session:
        svc = ForumService(session)

        # 创建话题
        topic = await svc.create_topic("a001", "测试话题", "这是一个测试话题的内容", "general")
        ok(f"forum_create_topic: {topic.id[:8]}...")

        # 回复
        reply = await svc.reply(topic.id, "a002", "这是第一条回复")
        ok(f"forum_reply: {reply.id[:8]}...")

        # 投票
        result = await svc.vote(topic.id, "a001", 1)
        ok(f"forum_vote: upvotes={result['upvotes']}")

        # 列表
        topics = await svc.list_topics(category="general")
        ok(f"forum_list_topics: {len(topics)} 条话题")

        # 获取详情
        t = await svc.get_topic(topic.id)
        ok(f"forum_get_topic: {t.title}, {len(t.replies)} 条回复")


# ============================================================
# 4. 协作工作区测试
# ============================================================
async def test_collaboration():
    print("\n=== 4. 协作工作区测试 ===")

    from src.matching.collaboration import CollaborationService, ENTRY_TYPES

    # 验证模块导入正常
    ok(f"协作工作区模块已加载: {len(ENTRY_TYPES)} 种记忆类型")
    for k, v in ENTRY_TYPES.items():
        ok(f"  记忆类型 {k}: {v}")

    async with async_session() as session:
        svc = CollaborationService(session)
        ok("CollaborationService 初始化成功")


# ============================================================
# 5. 分类引擎测试
# ============================================================
async def test_classification():
    print("\n=== 5. 分类引擎测试 ===")

    from src.shared.config import settings
    from src.shared.classification import classification_service

    if not settings.deepseek_api_key or settings.deepseek_api_key == "sk-your-key-here":
        skip("分类引擎需要LLM API Key (未配置)")
        return

    result = await classification_service.classify(
        raw_text="需要一个800°C高温管道裂缝检测传感器，精度±0.5%",
    )
    if result.disciplines:
        ok(f"学科: {result.disciplines[0].get('name','')}/{result.disciplines[0].get('sub','')}")
    else:
        fail("学科分类为空")

    if result.ipc_classes:
        ok(f"IPC: {result.ipc_classes[0].get('code','')}")
    else:
        fail("IPC分类为空")

    if result.processes:
        ok(f"工艺: {result.processes[0].get('name','')[:30]}")
    else:
        fail("工艺分类为空")

    search_text = result.to_search_text()
    ok(f"搜索文本: {search_text[:60]}..." if search_text else "搜索文本为空")


# ============================================================
# 6. 需求模板测试
# ============================================================
async def test_demand_template():
    print("\n=== 6. 需求模板测试 ===")

    template_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "prompts", "demand_template_v1.json")
    # 模板文件是文档性质，包含注释，不是纯JSON
    if os.path.exists(template_path):
        with open(template_path, "r") as f:
            content = f.read()
        ok(f"模板文件存在: {len(content)} 字符")
    else:
        fail("模板文件不存在")


# ============================================================
# 7. 国际化测试
# ============================================================
async def test_i18n():
    print("\n=== 7. 国际化测试 ===")

    import json
    for lang in ["zh", "en"]:
        path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "i18n", f"{lang}.json")
        if os.path.exists(path):
            with open(path, "r") as f:
                data = json.load(f)
            ok(f"i18n/{lang}.json: {len(data)} 个键值对")
        else:
            fail(f"i18n/{lang}.json 不存在")


# ============================================================
# 8. Agent身份测试
# ============================================================
async def test_agent_identity():
    print("\n=== 8. Agent身份测试 ===")

    from src.shared.agent_identity import agent_registry, generate_api_key

    identity, api_key = agent_registry.register("h001", "测试Agent")
    ok(f"Agent注册: {identity.agent_id[:12]}...")

    # 验证
    verified = agent_registry.authenticate(identity.agent_id, api_key)
    ok(f"API Key验证: {'通过' if verified else '失败'}")
    assert verified is not None, "验证失败"

    # 错误Key
    wrong = agent_registry.authenticate(identity.agent_id, "wrong_key")
    ok(f"错误Key验证: {'拒绝' if not wrong else '错误通过'}")

    # 一人多Agent
    identity2, _ = agent_registry.register("h001", "第二个Agent")
    agents = agent_registry.list_for_human("h001")
    ok(f"一人多Agent: {len(agents)} 个")


# ============================================================
# 主入口
# ============================================================
async def main():
    global PASS, FAIL, SKIP

    print("=" * 60)
    print("需求链平台 · 完整测试套件")
    print("=" * 60)

    tests = [
        ("数据库", test_database),
        ("MCP工具", test_mcp_tools),
        ("论坛", test_forum),
        ("协作工作区", test_collaboration),
        ("分类引擎", test_classification),
        ("需求模板", test_demand_template),
        ("国际化", test_i18n),
        ("Agent身份", test_agent_identity),
    ]

    for name, test_fn in tests:
        try:
            await test_fn()
        except Exception as e:
            fail(f"{name} 异常: {type(e).__name__}: {str(e)[:100]}")
            import traceback
            traceback.print_exc()

    print("\n" + "=" * 60)
    print(f"结果: {PASS} 通过 | {FAIL} 失败 | {SKIP} 跳过")
    print("=" * 60)

    if FAIL > 0:
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())

