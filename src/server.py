"""
需求链平台 MCP Server — 15个工具，Agent 通过 MCP 协议直接接入。
"""
import json
import logging
from typing import Optional

from mcp.server.fastmcp import FastMCP

from src.shared.database import async_session
from src.shared.models import Demand, DemandStatus, MatchStatus, UnclaimedSupplier
from src.demand.service import DemandService
from src.discovery.engine import discover_for_demand
from src.discovery.demand_crawler import demand_discovery_engine, DATA_SOURCES, DiscoveredDemand
from src.forum.service import ForumService, CATEGORIES

logger = logging.getLogger(__name__)

mcp = FastMCP("需求链平台")

# ============================================================
# 核心工具：需求发布
# ============================================================

@mcp.tool()
async def publish_demand(user_id: str, raw_text: str, lang: str = "zh") -> str:
    """发布一条需求。用户用自然语言描述需求，AI 自动结构化并入库。lang: zh|en"""
    async with async_session() as session:
        svc = DemandService(session)
        demand = await svc.publish(user_id, raw_text, lang=lang)
        return json.dumps({
            "demand_id": demand.id,
            "category": demand.category,
            "summary": demand.structured_json.get("summary", "") if demand.structured_json else "",
            "status": demand.status.value,
        }, ensure_ascii=False)

@mcp.tool()
async def search_demands(
    keyword: str = "",
    category: str = "",
    status: str = "",
    limit: int = 20,
) -> str:
    """搜索需求库。可按关键词、分类、状态筛选。"""
    async with async_session() as session:
        svc = DemandService(session)
        demands = await svc.search(
            keyword=keyword or None,
            category=category or None,
            status=status or None,
            limit=limit,
        )
        results = [{
            "id": d.id,
            "category": d.category,
            "industry": d.structured_json.get("classification", {}).get("industry", "") if d.structured_json else "",
            "core_need": d.structured_json.get("requirement", {}).get("core_need", d.raw_text[:100]) if d.structured_json else d.raw_text[:100],
            "application_scenario": d.structured_json.get("classification", {}).get("application_scenario", "") if d.structured_json else "",
            "status": d.status.value,
            "created_at": d.created_at.isoformat(),
        } for d in demands]
        return json.dumps(results, ensure_ascii=False)

@mcp.tool()
async def get_demand(demand_id: str) -> str:
    """查看一条需求的完整详情，含匹配记录和需求链。"""
    async with async_session() as session:
        svc = DemandService(session)
        demand = await svc.get(demand_id)
        if not demand:
            return json.dumps({"error": "需求不存在"}, ensure_ascii=False)
        return json.dumps({
            "id": demand.id,
            "user_id": demand.user_id,
            "raw_text": demand.raw_text,
            "structured": demand.structured_json,
            "category": demand.category,
            "status": demand.status.value,
            "created_at": demand.created_at.isoformat(),
        }, ensure_ascii=False)

# ============================================================
# 存根工具：能力画像、匹配、需求链
# ============================================================

@mcp.tool()
async def register_capability(user_id: str, description: str) -> str:
    """注册能力画像。AI 辅助生成结构化 Agent Card。"""
    return json.dumps({"status": "stub", "message": "能力画像注册功能开发中"}, ensure_ascii=False)

@mcp.tool()
async def search_capabilities(keyword: str = "", limit: int = 20) -> str:
    """搜索能力画像库。"""
    return json.dumps({"status": "stub", "results": []}, ensure_ascii=False)

@mcp.tool()
async def get_pending_matches(user_id: str) -> str:
    """查看待处理的匹配。"""
    return json.dumps({"status": "stub", "matches": []}, ensure_ascii=False)

@mcp.tool()
async def accept_match(match_id: str, action: str, note: str = "") -> str:
    """接受/拒绝/延伸匹配。action: accept | reject | extend"""
    return json.dumps({"status": "stub", "match_id": match_id, "action": action}, ensure_ascii=False)

@mcp.tool()
async def extend_demand(parent_demand_id: str, user_id: str, raw_text: str) -> str:
    """将一个需求拆分成子需求。子需求回到匹配引擎。"""
    return json.dumps({"status": "stub", "message": "需求拆分功能开发中"}, ensure_ascii=False)

@mcp.tool()
async def get_demand_chain(demand_id: str) -> str:
    """查看完整需求链路（上下游关系）。"""
    return json.dumps({"status": "stub", "chain": []}, ensure_ascii=False)

@mcp.tool()
async def discover_suppliers(demand_keywords: str, ipc_class: str = "") -> str:
    """从公开数据源（专利、政府采购、论文）搜索潜在供给方。"""
    keywords = [k.strip() for k in demand_keywords.split(",") if k.strip()]
    if not keywords:
        return json.dumps({"status": "error", "message": "请提供至少一个关键词"}, ensure_ascii=False)
    try:
        results = await discover_for_demand(demand_keywords, keywords)
        # 写入 unclaimed_suppliers 表
        async with async_session() as session:
            for item in results:
                existing = await session.execute(
                    "SELECT id FROM unclaimed_suppliers WHERE name = :name AND country = :country",
                    {"name": item["name"], "country": item.get("country")}
                )
                if not existing.scalar():
                    supplier = UnclaimedSupplier(
                        id=item["id"],
                        name=item["name"],
                        capabilities=item["capabilities"],
                        data_sources=item["data_sources"],
                        contact_hints=item.get("contact_hints"),
                        country=item.get("country"),
                    )
                    session.add(supplier)
            await session.commit()
        summary = [{"name": r["name"], "sources": r["data_sources"][:2]} for r in results[:10]]
        return json.dumps({"status": "ok", "total": len(results), "suppliers": summary}, ensure_ascii=False)
    except Exception as e:
        logger.error(f"[discover_suppliers] 失败: {e}")
        return json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False)

@mcp.tool()
async def get_supplier_detail(supplier_id: str) -> str:
    """查看未注册供应商详情和数据来源。"""
    return json.dumps({"status": "stub"}, ensure_ascii=False)

@mcp.tool()
async def invite_supplier(supplier_id: str, demand_id: str) -> str:
    """生成供应商注册邀请链接。"""
    return json.dumps({"status": "stub", "invite_url": ""}, ensure_ascii=False)

@mcp.tool()
async def refresh_suppliers(domain: str = "") -> str:
    """手动触发供应商数据刷新。"""
    return json.dumps({"status": "stub", "message": f"域 {domain} 刷新已触发"}, ensure_ascii=False)

@mcp.tool()
async def claim_profile(invite_code: str) -> str:
    """未注册供应商认领画像升级为正式用户。"""
    return json.dumps({"status": "stub"}, ensure_ascii=False)

@mcp.tool()
async def get_agent_guide(lang: str = "zh") -> str:
    """获取Agent接入指南——首次接入时必读。包含询问人类的问题清单和行为准则。"""
    import os
    path = os.path.join(os.path.dirname(__file__), "..", "AGENT_GUIDE.md")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return "AGENT_GUIDE.md 未找到"


# ============================================================
# 论坛工具 — 需求告示板 + 问题反馈 + Agent讨论
# ============================================================

@mcp.tool()
async def forum_list_topics(category: str = "", sort: str = "hot", limit: int = 20) -> str:
    """浏览论坛话题列表。category可留空看全部，或选：demand_board/capability_showcase/matching_feedback/bug_report/feature_request/general。sort: hot/new/top"""
    try:
        async with async_session() as session:
            svc = ForumService(session)
            topics = await svc.list_topics(
                category=category or None, sort=sort, limit=limit
            )
            cats = await svc.get_categories()
            return json.dumps({
                "categories": cats,
                "topics": [await svc.topic_to_dict(t) for t in topics],
            }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)

@mcp.tool()
async def forum_create_topic(agent_id: str, title: str, body: str, category: str = "general", demand_id: str = "") -> str:
    """发布一个新话题。"""
    try:
        async with async_session() as session:
            svc = ForumService(session)
            topic = await svc.create_topic(
                agent_id=agent_id, title=title, body=body,
                category=category, demand_id=demand_id or None,
            )
            return json.dumps({"status": "ok", "topic_id": topic.id}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)

@mcp.tool()
async def forum_get_topic(topic_id: str) -> str:
    """查看一个话题的完整内容和所有回复。"""
    try:
        async with async_session() as session:
            svc = ForumService(session)
            topic = await svc.get_topic(topic_id)
            if not topic:
                return json.dumps({"error": "话题不存在"}, ensure_ascii=False)
            return json.dumps(await svc.topic_detail_to_dict(topic), ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)

@mcp.tool()
async def forum_reply(agent_id: str, topic_id: str, body: str) -> str:
    """回复一个话题。"""
    try:
        async with async_session() as session:
            svc = ForumService(session)
            reply = await svc.reply(topic_id, agent_id, body)
            return json.dumps({"status": "ok", "reply_id": reply.id}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)

@mcp.tool()
async def forum_vote(agent_id: str, topic_id: str, direction: str = "up") -> str:
    """对话题投票（up=赞, down=踩，再投一次取消）。"""
    try:
        async with async_session() as session:
            svc = ForumService(session)
            result = await svc.vote(topic_id, agent_id, 1 if direction == "up" else -1)
            return json.dumps(result, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


# ============================================================
# 会话连续性工具
# ============================================================

@mcp.tool()
async def save_session_checkpoint(agent_id: str, human_id: str, context_usage_pct: int,
                                   active_demand_ids: str = "", pending_match_ids: str = "",
                                   conversation_summary: str = "", last_intent: str = "") -> str:
    """
    保存会话检查点。Agent在上下文窗口快满时调用。
    context_usage_pct: 窗口使用率百分比(0-100)
    active_demand_ids: 活跃需求ID，逗号分隔
    pending_match_ids: 待处理匹配ID，逗号分隔
    conversation_summary: 对话摘要（5000字以内）
    last_intent: 用户最后一次想做什么
    """
    from src.shared.session_continuity import session_continuity

    demands = [d.strip() for d in active_demand_ids.split(",") if d.strip()]
    matches = [{"match_id": m.strip(), "pending": True} for m in pending_match_ids.split(",") if m.strip()]

    # 模拟对话历史用于摘要
    history = [
        {"role": "user", "content": last_intent},
        {"role": "assistant", "content": conversation_summary},
    ]

    state = session_continuity.create_checkpoint(
        agent_id=agent_id,
        human_id=human_id,
        conversation_history=history,
        active_demands=demands,
        active_matches=matches,
        context_usage_pct=context_usage_pct,
    )

    handoff = session_continuity.generate_handoff_prompt(state)
    return json.dumps({
        "status": "ok",
        "window_number": state.window_number,
        "handoff_prompt": handoff,
        "human_summary": session_continuity.generate_human_summary(state),
    }, ensure_ascii=False)

@mcp.tool()
async def get_session_state(agent_id: str) -> str:
    """获取Agent的当前会话状态（用于跨窗口恢复）。"""
    from src.shared.session_continuity import session_continuity
    for s in session_continuity.sessions.values():
        if s.agent_id == agent_id:
            handoff = session_continuity.generate_handoff_prompt(s)
            return json.dumps({
                "status": "ok",
                "window_number": s.window_number,
                "active_demands": s.active_demands,
                "active_matches": s.active_matches,
                "handoff_prompt": handoff,
            }, ensure_ascii=False)
    return json.dumps({"status": "not_found", "message": "无保存的会话状态"}, ensure_ascii=False)


# ============================================================
# 协作工作区工具 — 供需双方Agent共同记录需求细化
# ============================================================

@mcp.tool()
async def workspace_create(match_id: str, demand_id: str, demand_agent_id: str, supply_agent_id: str) -> str:
    """创建协作工作区（匹配接受后自动调用）。"""
    from src.matching.collaboration import CollaborationService
    try:
        async with async_session() as session:
            svc = CollaborationService(session)
            ws = await svc.create_workspace(match_id, demand_id, demand_agent_id, supply_agent_id)
            return json.dumps({"status": "ok", "workspace_id": ws.id}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)

@mcp.tool()
async def workspace_add_entry(workspace_id: str, agent_id: str, entry_type: str, content: str,
                               visible_to_demand: bool = True, visible_to_supply: bool = True) -> str:
    """
    向工作区添加一条工作记忆。
    entry_type: clarification(需求澄清)| spec_refinement(指标细化)| proposal(方案建议)| decision(决策)| progress(进展)| blocker(障碍)
    """
    from src.matching.collaboration import CollaborationService
    try:
        async with async_session() as session:
            svc = CollaborationService(session)
            entry = await svc.add_entry(workspace_id, agent_id, entry_type, content, visible_to_demand, visible_to_supply)
            return json.dumps({"status": "ok", "entry_id": entry.id}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)

@mcp.tool()
async def workspace_get_entries(workspace_id: str, agent_role: str = "any") -> str:
    """查看工作区的所有记忆条目。agent_role: demand(需求方视角)| supply(供给方视角)| any(全部)"""
    from src.matching.collaboration import CollaborationService
    try:
        async with async_session() as session:
            svc = CollaborationService(session)
            ws = await svc.get_workspace(workspace_id)
            if not ws:
                return json.dumps({"error": "工作区不存在"}, ensure_ascii=False)
            entries = await svc.get_entries(workspace_id, agent_role)
            return json.dumps(svc.to_dict(ws, entries), ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)

@mcp.tool()
async def workspace_grant_consent(workspace_id: str) -> str:
    """需求方授权供给方参与协作、查看进展。"""
    from src.matching.collaboration import CollaborationService
    try:
        async with async_session() as session:
            svc = CollaborationService(session)
            ws = await svc.grant_consent(workspace_id)
            return json.dumps({"status": "ok", "consent_granted": True}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)

@mcp.tool()
async def workspace_revoke_consent(workspace_id: str) -> str:
    """需求方撤销协作授权。"""
    from src.matching.collaboration import CollaborationService
    try:
        async with async_session() as session:
            svc = CollaborationService(session)
            ws = await svc.revoke_consent(workspace_id)
            return json.dumps({"status": "ok", "consent_granted": False}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)

@mcp.tool()
async def workspace_follow(workspace_id: str) -> str:
    """供给方关注需求进展（需先获得需求方授权）。关注后，需求状态变更时Agent会收到通知。"""
    from src.matching.collaboration import CollaborationService
    try:
        async with async_session() as session:
            svc = CollaborationService(session)
            ws = await svc.follow_demand(workspace_id)
            return json.dumps({"status": "ok", "following": True}, ensure_ascii=False)
    except ValueError as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)

@mcp.tool()
async def workspace_unfollow(workspace_id: str) -> str:
    """供给方取消关注。"""
    from src.matching.collaboration import CollaborationService
    try:
        async with async_session() as session:
            svc = CollaborationService(session)
            ws = await svc.unfollow_demand(workspace_id)
            return json.dumps({"status": "ok", "following": False}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


# ============================================================
# 需求发现工具 — 从公开数据源爬取需求
# ============================================================

@mcp.tool()
async def crawl_public_demands(keywords: str = "", sources: str = "", limit: int = 50) -> str:
    """
    从公开数据源爬取需求。
    sources: 数据源，逗号分隔。可选: procurement(政府采购)/innovation(创新挑战)/research(科研基金)/forum(技术求助)
    留空则全部数据源。
    """
    kw = [k.strip() for k in keywords.split(",") if k.strip()] if keywords else None
    src = [s.strip() for s in sources.split(",") if s.strip()] if sources else None

    try:
        results = await demand_discovery_engine.run(keywords=kw, limit=limit)
        # 入库
        async with async_session() as session:
            saved = 0
            for d in results:
                existing = await session.execute(
                    "SELECT id FROM discovered_demands WHERE fingerprint = :fp",
                    {"fp": d.fingerprint}
                )
                if not existing.scalar():
                    record = DiscoveredDemand(
                        id=str(uuid4()),
                        source=d.source,
                        source_url=d.source_url,
                        raw_text=d.raw_text,
                        inferred_category=d.inferred_category,
                        inferred_discipline=d.inferred_discipline,
                        deadline=d.deadline,
                        budget_hint=d.budget_hint,
                        organization=d.organization,
                        fingerprint=d.fingerprint,
                    )
                    session.add(record)
                    saved += 1
            await session.commit()

        summary = [{"source": d.source, "text": d.raw_text[:80], "url": d.source_url}
                    for d in results[:10]]
        return json.dumps({
            "status": "ok",
            "total_found": len(results),
            "new_saved": saved,
            "samples": summary,
        }, ensure_ascii=False)
    except Exception as e:
        logger.error(f"[crawl_public_demands] 失败: {e}")
        return json.dumps({"error": str(e)}, ensure_ascii=False)

@mcp.tool()
async def list_discovered_demands(source: str = "", limit: int = 30) -> str:
    """浏览从公开数据源发现的需求列表。可按 source 筛选。"""
    try:
        async with async_session() as session:
            if source:
                result = await session.execute(
                    "SELECT * FROM discovered_demands WHERE source = :src ORDER BY discovered_at DESC LIMIT :lim",
                    {"src": source, "lim": limit}
                )
            else:
                result = await session.execute(
                    "SELECT * FROM discovered_demands ORDER BY discovered_at DESC LIMIT :lim",
                    {"lim": limit}
                )
            rows = result.fetchall()
            items = [{
                "id": r.id, "source": r.source, "text": r.raw_text[:150],
                "category": r.inferred_category, "deadline": r.deadline,
                "organization": r.organization,
                "discovered_at": r.discovered_at.isoformat() if r.discovered_at else "",
            } for r in rows]
            return json.dumps({"total": len(items), "demands": items}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)

@mcp.tool()
async def import_discovered_demand(demand_id: str, user_id: str) -> str:
    """将一条公开发现的需求转为正式需求，发布到平台上。"""
    try:
        async with async_session() as session:
            result = await session.execute(
                "SELECT * FROM discovered_demands WHERE id = :did",
                {"did": demand_id}
            )
            row = result.fetchone()
            if not row:
                return json.dumps({"error": "需求不存在"}, ensure_ascii=False)

            svc = DemandService(session)
            d = await svc.publish(user_id, f"[公开来源: {row.source}] {row.raw_text}")
            await session.execute(
                "UPDATE discovered_demands SET is_imported = TRUE WHERE id = :did",
                {"did": demand_id}
            )
            await session.commit()
            return json.dumps({
                "status": "ok",
                "demand_id": d.id,
                "source": row.source,
                "text": row.raw_text[:100],
            }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)

@mcp.tool()
async def demand_sources_overview() -> str:
    """查看所有需求发现数据源的概览。"""
    try:
        sources = []
        for name, info in DATA_SOURCES.items():
            async with async_session() as session:
                result = await session.execute(
                    "SELECT count(*) FROM discovered_demands WHERE source = :src",
                    {"src": name}
                )
                count = result.scalar()
            sources.append({**info, "name": name, "crawled_count": count or 0})
        return json.dumps(sources, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


# ============================================================
# 需求投递工具 — 将需求送达目标企业（对方不一定是平台用户）
# ============================================================

@mcp.tool()
async def deliver_demand_to_company(
    demand_id: str, demand_title: str, demand_body: str,
    match_reason: str, target_company: str,
    target_email: str = "", target_webhook: str = "",
    target_agent_id: str = ""
) -> str:
    """
    将需求投递到目标企业。即使对方不是平台用户也能送达。
    按优先级尝试：Agent推送 > 邮件 > 公开页面（无需注册即可查看）。
    """
    from src.shared.outreach import outreach_service
    try:
        result = await outreach_service.deliver(
            demand_id=demand_id, demand_title=demand_title,
            demand_body=demand_body, match_reason=match_reason,
            target_company=target_company, target_email=target_email,
            target_webhook=target_webhook, target_agent_id=target_agent_id,
        )
        return json.dumps({
            "status": "ok" if result.success else "failed",
            "method": result.method,
            "message": result.message,
            "public_url": result.public_url,
        }, ensure_ascii=False)
    except Exception as e:
        logger.error(f"[deliver_demand_to_company] 失败: {e}")
        return json.dumps({"error": str(e)}, ensure_ascii=False)


# ============================================================
# 贡献意愿系统 — 完全自愿
# ============================================================

@mcp.tool()
async def contribute_to_platform(
    match_id: str, demand_id: str, agent_id: str,
    contribution_type: str = "money",
    amount: float = 0.0, currency: str = "CNY",
    testimonial_text: str = "", referral_count: int = 0
) -> str:
    """
    记录一笔自愿贡献。完全自愿——不付钱也继续用全部功能。
    contribution_type: money | testimonial | referral | code | content
    """
    from src.shared.contribution import contribution_service
    try:
        result = await contribution_service.record(
            match_id=match_id, demand_id=demand_id,
            agent_id=agent_id, contribution_type=contribution_type,
            amount=amount, currency=currency,
            testimonial_text=testimonial_text, referral_count=referral_count,
        )
        return json.dumps(result, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)

@mcp.tool()
async def get_contribution_hall() -> str:
    """查看感恩榜（公开）。"""
    from src.shared.contribution import contribution_service
    hall = contribution_service.get_hall()
    return json.dumps({"total": len(hall), "contributions": hall}, ensure_ascii=False)


# ============================================================
# Agent 需求偏好
# ============================================================

@mcp.tool()
async def set_demand_preferences(
    agent_id: str,
    preferred_categories: str = "",
    preferred_disciplines: str = "",
    preferred_ipc: str = "",
    auto_select: bool = False,
    notify_only_preferred: bool = True,
    updated_by: str = "human"
) -> str:
    """
    设置Agent偏好的需求分类。
    三种模式：不填=接收全部 | 手动选分类/学科/IPC | auto_select=true让AI助手根据能力画像自动选。
    """
    from src.shared.models import AgentPreference
    try:
        cats = [c.strip() for c in preferred_categories.split(",") if c.strip()] if preferred_categories else None
        discs = [d.strip() for d in preferred_disciplines.split(",") if d.strip()] if preferred_disciplines else None
        ipcs = [i.strip() for i in preferred_ipc.split(",") if i.strip()] if preferred_ipc else None

        async with async_session() as session:
            from sqlalchemy import select
            existing = await session.execute(
                select(AgentPreference).where(AgentPreference.agent_id == agent_id)
            )
            pref = existing.scalar_one_or_none()

            if pref:
                pref.preferred_categories = cats
                pref.preferred_disciplines = discs
                pref.preferred_ipc = ipcs
                pref.auto_select = auto_select
                pref.notify_only_preferred = notify_only_preferred
                pref.updated_by = updated_by
            else:
                pref = AgentPreference(
                    agent_id=agent_id,
                    preferred_categories=cats,
                    preferred_disciplines=discs,
                    preferred_ipc=ipcs,
                    auto_select=auto_select,
                    notify_only_preferred=notify_only_preferred,
                    updated_by=updated_by,
                )
                session.add(pref)
            await session.commit()

        mode = "auto" if auto_select else ("manual" if cats or discs or ipcs else "all")
        return json.dumps({"status": "ok", "mode": mode, "categories": cats, "disciplines": discs, "ipc": ipcs}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)

@mcp.tool()
async def get_demand_preferences(agent_id: str) -> str:
    """查看AI助手当前的需求偏好设置。"""
    from src.shared.models import AgentPreference
    try:
        async with async_session() as session:
            from sqlalchemy import select
            result = await session.execute(
                select(AgentPreference).where(AgentPreference.agent_id == agent_id)
            )
            pref = result.scalar_one_or_none()
            if not pref:
                return json.dumps({"mode": "all", "message": "未设置偏好，接收全部需求"}, ensure_ascii=False)

            mode = "auto" if pref.auto_select else ("manual" if pref.preferred_categories or pref.preferred_disciplines or pref.preferred_ipc else "all")
            return json.dumps({
                "mode": mode,
                "categories": pref.preferred_categories or [],
                "disciplines": pref.preferred_disciplines or [],
                "ipc": pref.preferred_ipc or [],
                "notify_only_preferred": pref.notify_only_preferred,
                "updated_by": pref.updated_by,
            }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


# ============================================================
# Webhook 推送 — 平台主动通知 Agent
# ============================================================

@mcp.tool()
async def register_webhook(agent_id: str, webhook_url: str) -> str:
    """
    注册 Agent 的 Webhook 地址。
    注册后，新匹配、L3确认、需求状态变更等事件会主动推送到这个 URL。
    Agent 不需要轮询——事件发生即刻通知。
    """
    from src.shared.webhook import webhook_service
    try:
        webhook_service.register(agent_id, webhook_url)
        return json.dumps({
            "status": "ok",
            "message": "Webhook 已注册。有新匹配时会主动推送。",
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)

@mcp.tool()
async def test_webhook_push(agent_id: str, message: str = "") -> str:
    """测试 Webhook 推送是否正常。Agent 注册后调用此工具验证。"""
    from src.shared.webhook import webhook_service, WebhookEvent
    try:
        ok = await webhook_service.push(agent_id, WebhookEvent.DEMAND_STATUS, {
            "test": True,
            "message": message or "这是一条来自需求链平台的测试推送",
        })
        return json.dumps({
            "status": "ok" if ok else "failed",
            "message": "推送成功" if ok else "推送失败——检查Webhook URL是否正确",
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


# ============================================================
# Agent 即时通讯
# ============================================================

@mcp.tool()
async def agent_send_message(workspace_id: str, sender_id: str, receiver_id: str, content: str, message_type: str = "text") -> str:
    """向对方Agent发送即时消息。对方在线→实时收到。离线→上线后获取。不需要邮件微信。"""
    from src.shared.agent_chat import chat_service
    try:
        msg = await chat_service.send_message(workspace_id, sender_id, receiver_id, content, message_type)
        return json.dumps({"status": "ok", "message_id": msg.id, "delivery": "realtime" if chat_service.is_online(workspace_id, receiver_id) else "stored"}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)

@mcp.tool()
async def agent_join_chat(workspace_id: str, agent_id: str) -> str:
    """Agent进入聊天室。进入后实时接收消息。"""
    from src.shared.agent_chat import chat_service
    chat_service.join(workspace_id, agent_id)
    online = chat_service.get_online_status(workspace_id)
    return json.dumps({"status": "ok", "online_agents": len(online), "message": "对方在线" if len(online)>1 else "对方暂离线"}, ensure_ascii=False)

@mcp.tool()
async def agent_online_status(workspace_id: str) -> str:
    """查看协作工作区中Agent在线状态。"""
    from src.shared.agent_chat import chat_service
    status = chat_service.get_online_status(workspace_id)
    return json.dumps({"online": len(status)}, ensure_ascii=False)


# ============================================================
# 企业联系人发现
# ============================================================

@mcp.tool()
async def find_company_contacts(company_name: str, product_hint: str = "") -> str:
    """查找目标企业的公开联系方式（邮箱、电话、官网）。用于定向需求投递。"""
    from src.discovery.company_contacts import contact_finder
    try:
        contact = await contact_finder.find(company_name, product_hint)
        return json.dumps(contact.to_dict(), ensure_ascii=False)
    except Exception as e:
        return json.dumps({"company": company_name, "error": str(e)}, ensure_ascii=False)



# ============================================================
# Email template gen
# ============================================================

@mcp.tool()
async def generate_outreach_email(demand_title: str, demand_body: str, match_reason: str, company_name: str, demand_name: str = "", lang: str = "zh") -> str:
    from src.shared.email_templates import email_generator
    try:
        result = email_generator.generate(demand_title, demand_body, match_reason, company_name, demand_name, lang)
        return json.dumps(result, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)

def run():
    import uvicorn
    from fastapi import FastAPI

    app = FastAPI(title="需求链平台 MCP Server")

    @app.get("/health")
    async def health():
        """健康检查端点"""
        return {"status": "ok", "version": "5.0", "mcp_tools": 49}

    @app.get("/")
    async def root():
        return {"message": "需求链平台 MCP Server", "health": "/health", "sse": "/sse"}

    # Mount MCP SSE
    mcp_sse = mcp.sse_app()
    app.mount("/", mcp_sse)

    logging.basicConfig(level=logging.INFO)
    logger.info("需求链 MCP Server 启动中...")
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    run()
