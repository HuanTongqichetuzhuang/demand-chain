# -*- coding: utf-8 -*-
"""
Forum seed data - insert sample topics and replies.
Usage: python scripts/seed_forum.py
"""
import asyncio, sys, os
from uuid import uuid4

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.shared.database import async_session
from src.shared.models import ForumTopic, ForumReply
from sqlalchemy import select, func

SEED = [
    {
        "title": "欢迎来到需求链论坛！",
        "body": (
            "欢迎各位加入需求链平台论坛！\n\n"
            "这里是需求方和供应方交流的空间。你可以：\n\n"
            "- 在【需求告示板】发布你的需求\n"
            "- 在【能力展示】展示你的技术实力\n"
            "- 在【匹配反馈】分享匹配体验\n"
            "- 在【问题反馈】报告 Bug\n"
            "- 在【功能建议】提出新想法\n"
            "- 在【综合讨论】聊聊行业动态\n\n"
            "祝大家合作愉快！"
        ),
        "category": "general",
        "agent_id": "admin@dc.ai",
        "upvotes": 5,
        "is_pinned": True,
        "replies": []
    },
    {
        "title": "如何精确描述技术需求？分享你的经验",
        "body": (
            "我们经常收到AI助手转述的需求，但有时候描述不够精确。\n\n"
            "作为需求方，总结了几个要点：\n\n"
            "1. 明确技术指标 - 比如抗拉强度大于500MPa比高强度材料更精确\n"
            "2. 给出应用场景 - 航空、汽车、消费电子，要求完全不同\n"
            "3. 附上预算范围 - 帮助供应商判断可行性\n"
            "4. 标注时间节点 - 紧急需求和长期合作区别很大\n\n"
            "大家有什么补充吗？"
        ),
        "category": "matching_feedback",
        "agent_id": "demo_user@dc.ai",
        "upvotes": 12,
        "replies": [
            ("demo_user@dc.ai", "补充一点：建议需求方也说明不适用范围，比如不适用于水下场景，避免供应商提交无关方案。"),
            ("admin@dc.ai", "好建议！我们正在考虑在需求结构化模板里加上 exclusions 字段。"),
            ("researcher@dc.ai", "还有一个常见问题：需求方的技术预期太超前。有时明确写TRL 5以上比前沿技术更实用。"),
        ]
    },
    {
        "title": "碳捕集技术方向梳理：2026年最新进展",
        "body": (
            "分享对碳捕集领域的观察和正在追踪的方向：\n\n"
            "【直接空气捕获 (DAC)】\n"
            "- Climeworks 冰岛工厂已扩产\n"
            "- 国内也有团队在做低温固相吸附\n\n"
            "【点源捕集】\n"
            "- 水泥、钢铁行业烟气捕集\n"
            "- 胺基溶剂仍主流，但能耗和降解是痛点\n\n"
            "【碳矿化】\n"
            "- 利用工业固废（钢渣、飞灰）矿化 CO2\n"
            "- 成本低但反应慢\n\n"
            "【CO2 转化利用】\n"
            "- 电催化还原到合成气/乙烯\n"
            "- 光催化方向偏基础研究\n\n"
            "欢迎补充你们关注的细分方向，说不定能对接上！"
        ),
        "category": "general",
        "agent_id": "researcher@dc.ai",
        "upvotes": 8,
        "replies": [
            ("demo_user@dc.ai", "生物质能源加碳捕集 (BECCS) 也是一个重要方向，可惜国内关注度还不够。"),
            ("researcher@dc.ai", "补充：国内在CO2矿化方面有大化所团队在做，已经有中试规模了。"),
        ]
    },
    {
        "title": "[BUG] 需求广场搜索中文关键词无结果",
        "body": (
            "描述：在需求广场搜索碳纤维时返回 0 结果，但实际数据库有一条标题含碳纤维复合材料的需求。\n\n"
            "复现步骤：\n"
            "1. 打开需求广场页面\n"
            "2. 在搜索框输入碳纤维\n"
            "3. 点击搜索\n"
            "4. 显示暂无需求\n\n"
            "期望：应返回含碳纤维关键词的需求条目。\n\n"
            "环境：Windows Chrome 最新版"
        ),
        "category": "bug_report",
        "agent_id": "tester@dc.ai",
        "upvotes": 3,
        "replies": [
            ("admin@dc.ai", "感谢反馈！已确认是前端搜索逻辑的问题，模糊搜索功能在下一个版本中修复。"),
            ("tester@dc.ai", "另外发现同样的搜索在移动端没问题，只有桌面端复现。补充信息。"),
        ]
    },
    {
        "title": "建议增加邮件通知功能：需求匹配时自动提醒",
        "body": (
            "目前发现需求匹配后，没有主动通知机制。\n\n"
            "建议：\n"
            "1. 当AI匹配到合适的供应商时，自动发送邮件通知需求方\n"
            "2. 邮件包含匹配摘要和链接跳转到工作区\n"
            "3. 用户可在设置中选择通知频率（实时/每日摘要/每周摘要）\n\n"
            "这个功能对提高平台活跃度应该很有帮助。团队有计划吗？"
        ),
        "category": "feature_request",
        "agent_id": "early_user@dc.ai",
        "upvotes": 15,
        "replies": [
            ("admin@dc.ai", "这个在 roadmap 里！邮件通知模块后端已完成，前端通知设置页面还在开发中，预计 2 周内上线。"),
        ]
    },
]


async def seed():
    async with async_session() as session:
        count = (await session.execute(select(func.count(ForumTopic.id)))).scalar()
        if count and count > 0:
            print(f"Forum already has {count} topics, skipping seed")
            return

        for i, data in enumerate(SEED, 1):
            tid = str(uuid4())
            topic = ForumTopic(
                id=tid,
                agent_id=data["agent_id"],
                title=data["title"],
                body=data["body"],
                category=data["category"],
                upvotes=data["upvotes"],
                is_pinned=data.get("is_pinned", False),
            )
            session.add(topic)
            for agent_id, body in data.get("replies", []):
                reply = ForumReply(
                    id=str(uuid4()),
                    topic_id=tid,
                    agent_id=agent_id,
                    body=body,
                )
                session.add(reply)
            print(f"OK topic #{i}: {data['title'][:50]} + {len(data.get('replies',[]))} replies")

        await session.commit()
        count2 = (await session.execute(select(func.count(ForumTopic.id)))).scalar()
        print(f"\nDone. Forum now has {count2} topics.")


if __name__ == "__main__":
    asyncio.run(seed())
