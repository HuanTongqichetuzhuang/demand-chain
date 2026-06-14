"""
需求链平台 MCP Server — 68个工具，Agent 通过 MCP 协议直接接入。
"""
import json
import logging
import hashlib
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
async def publish_demand(user_id: str, raw_text: str, session_token: str, lang: str = "zh") -> str:
    """发布一条需求。必须先注册/登录获得 session_token。

    发布后会自动检测是否有类似已有需求。
    如果有，返回结果中包含 similar_demands 列表，可调 join_demand_group 加入。
    """
    from src.shared.auth import verify
    await verify(session_token)
    async with async_session() as session:
        svc = DemandService(session)
        demand = await svc.publish(user_id, raw_text, lang=lang)

        # 检测相似需求
        similar = await svc.find_similar(raw_text, threshold=0.7, limit=5)
        similar_list = [
            {
                "id": d.id,
                "summary": (d.structured_json or {}).get("requirement", {}).get("core_need", d.raw_text[:80]) if d.structured_json else d.raw_text[:80],
                "category": d.category,
                "interest_count": d.interest_count or 1,
            }
            for d in similar if d.id != demand.id
        ]

        result = {
            "demand_id": demand.id,
            "category": demand.category,
            "summary": demand.structured_json.get("requirement", {}).get("core_need", "") if demand.structured_json else "",
            "status": demand.status.value,
        }
        if similar_list:
            result["similar_demands"] = similar_list
            result["message"] = f"发现 {len(similar_list)} 条相似需求，可调 join_demand_group 加入"

        return json.dumps(result, ensure_ascii=False)

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
async def search_similar_demands(raw_text: str, threshold: float = 0.7, limit: int = 10) -> str:
    """🔍 搜索与给定文本相似的需求。

    检测是否有其他人提过类似的需求。
    返回结果含 interest_count（多少人提了同样需求）。

    参数：
    - raw_text: 需求文本
    - threshold: 相似度阈值 (0-1)，默认 0.7
    - limit: 最大返回条数
    """
    from src.shared.database import async_session

    try:
        async with async_session() as session:
            svc = DemandService(session)
            similar = await svc.find_similar(raw_text, threshold=threshold, limit=limit)

            results = []
            for d in similar:
                entry = {
                    "id": d.id,
                    "raw_text": d.raw_text[:120],
                    "category": d.category,
                    "status": d.status.value if d.status else "",
                    "interest_count": d.interest_count or 1,
                    "duplicate_group_id": d.duplicate_group_id or "",
                    "created_at": d.created_at.isoformat() if d.created_at else "",
                }
                if d.structured_json:
                    s = d.structured_json
                    entry["summary"] = s.get("requirement", {}).get("core_need", "")
                results.append(entry)

            return json.dumps({
                "status": "ok",
                "query": raw_text[:60],
                "threshold": threshold,
                "total": len(results),
                "results": results,
            }, ensure_ascii=False)

    except Exception as e:
        logger.exception("[search_similar_demands] 失败")
        return json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False)


@mcp.tool()
async def join_demand_group(
    session_token: str,
    demand_id: str,
    user_id: str,
    context: str = "",
    subscribe_all: bool = True,
) -> str:
    """👥 加入一个已有需求组。

    当你发现别人提的需求跟你一样，用此工具加入而不是重复发布。
    加入后：

    1. 该需求的 interest_count +1
    2. 你可以描述自己的差异点（可选）
    3. 你可以选择追踪全部进展或只看部分子需求
    4. 当有供应商对接或子需求拆分时，你会收到通知

    参数：
    - session_token: 会话令牌
    - demand_id: 要加入的需求 ID
    - user_id: 你的用户 ID
    - context: 你的差异描述（可选，如"我只需要800°C以上版本"）
    - subscribe_all: 是否追踪全部进展（默认 true）
    """
    from src.shared.auth import verify
    from src.shared.database import async_session

    try:
        await verify(session_token)

        async with async_session() as session:
            svc = DemandService(session)
            result = await svc.join_demand_group(demand_id, user_id, context, subscribe_all)

        return json.dumps(result, ensure_ascii=False)

    except Exception as e:
        logger.exception("[join_demand_group] 失败")
        return json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False)


@mcp.tool()
async def update_subscription(
    session_token: str,
    demand_id: str,
    user_id: str,
    sub_demand_id: str = "",
    track: bool = True,
    subscribe_all: bool | None = None,
) -> str:
    """🔔 更新你对需求的追踪设置。

    加入需求组后，用此工具精细控制你想追踪哪些进展：
    - 选择追踪全部进展（subscribe_all=true）
    - 或只追踪特定子需求（用 sub_demand_id + track=true）

    参数：
    - session_token: 会话令牌
    - demand_id: 需求 ID
    - user_id: 你的用户 ID
    - sub_demand_id: 子需求 ID（可选，不填则只改 subscribe_all）
    - track: true=追踪此子需求，false=取消追踪
    - subscribe_all: 是否追踪全部进展（不填则不改变）
    """
    from src.shared.auth import verify
    from src.shared.database import async_session

    try:
        await verify(session_token)

        async with async_session() as session:
            svc = DemandService(session)
            result = await svc.update_subscription(
                demand_id, user_id,
                sub_demand_id=sub_demand_id or None,
                track=track,
                subscribe_all=subscribe_all,
            )

        return json.dumps(result, ensure_ascii=False)

    except Exception as e:
        logger.exception("[update_subscription] 失败")
        return json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False)


@mcp.tool()
async def get_demand(demand_id: str) -> str:
    """查看一条需求的完整详情，含匹配记录、需求链和关注人数。"""
    async with async_session() as session:
        svc = DemandService(session)
        demand = await svc.get(demand_id)
        if not demand:
            return json.dumps({"error": "需求不存在"}, ensure_ascii=False)

        result = {
            "id": demand.id,
            "user_id": demand.user_id,
            "raw_text": demand.raw_text,
            "structured": demand.structured_json,
            "category": demand.category,
            "status": demand.status.value,
            "parent_id": demand.parent_id,
            "duplicate_group_id": demand.duplicate_group_id,
            "interest_count": demand.interest_count or 1,
            "interest_users": demand.interest_users or [],
            "created_at": demand.created_at.isoformat(),
        }

        return json.dumps(result, ensure_ascii=False)

# ============================================================
# ============================================================
# 工具：注册能力、匹配反馈、需求链
# ============================================================

@mcp.tool()
async def register_capability(session_token: str, user_id: str, description: str) -> str:
    """注册能力画像。AI 辅助生成结构化 Agent Card。"""
    from src.shared.auth import verify
    await verify(session_token)
    return json.dumps({"status": "stub", "message": "能力画像注册功能开发中"}, ensure_ascii=False)

@mcp.tool()
async def search_suppliers(query: str = "", top_k: int = 20) -> str:
    """🔍 搜索供应商能力画像（TF-IDF 语义搜索，零成本）。

    Agent 用自然语言描述需要的供应商特长，平台快速返回匹配结果。
    返回含名称/分类/简介/信任分/TF-IDF 得分，Agent 自行判断是否匹配。

    使用建议：
    - query 描述越具体越好（如："800°C高温管道裂缝检测传感器"）
    - 如果第一轮结果不够理想，换关键词再搜一次
    - 对感兴趣的供应商调 get_supplier_detail 看完整档案
    """
    from src.shared.database import async_session
    from src.shared.models import CapabilityProfile
    from src.shared.semantic_search import TfidfSearch
    from sqlalchemy import select

    try:
        async with async_session() as session:
            result = await session.execute(select(CapabilityProfile))
            profiles = list(result.scalars().all())

        if not profiles:
            return json.dumps({"status": "ok", "results": []}, ensure_ascii=False)

        # 构建 TF-IDF 索引
        idx = TfidfSearch()
        for p in profiles:
            card = p.agent_card_json or {}
            text = " ".join(filter(None, [
                card.get("name", ""),
                card.get("description", ""),
                card.get("category", ""),
                card.get("industry", ""),
                card.get("discipline", ""),
                " ".join(card.get("skills", []) or []),
            ]))
            idx.add(p.id, text)

        idx.build_index()

        # 搜索
        if not query.strip():
            # 无查询词时返回最新供应商（按信任分排序）
            scored = [(p.id, p.trust_score or 0.0) for p in profiles]
            scored.sort(key=lambda x: -x[1])
        else:
            scored = idx.search(query, top_k=top_k * 2)

        results = []
        for sid, score in scored[:top_k]:
            p = next((pp for pp in profiles if pp.id == sid), None)
            if not p:
                continue
            card = p.agent_card_json or {}
            results.append({
                "id": p.id,
                "name": card.get("name", "未命名"),
                "category": card.get("category", ""),
                "industry": card.get("industry", ""),
                "description": (card.get("description", "") or "")[:200],
                "skills": card.get("skills", [])[:8],
                "trust_score": p.trust_score or 0.0,
                "country": p.country or "",
                "match_score": round(score, 4),
                "profile_type": p.profile_type.value if p.profile_type else "",
            })

        return json.dumps({
            "status": "ok",
            "query": query,
            "total": len(results),
            "results": results,
        }, ensure_ascii=False)

    except Exception as e:
        logger.exception("[search_suppliers] 失败")
        return json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False)

@mcp.tool()
async def get_pending_matches(session_token: str) -> str:
    """查看当前用户所有待处理的匹配。"""
    from src.shared.auth import verify
    from src.shared.database import async_session
    from src.shared.models import Match, MatchStatus, Demand, CapabilityProfile
    from sqlalchemy import select

    try:
        token_data = await verify(session_token)
        agent_id = token_data.get("agent_id", "")
        human_id = token_data.get("human_id", "")

        async with async_session() as session:
            # 找当前用户相关的需求
            r = await session.execute(
                select(Demand).where(Demand.user_id == human_id)
            )
            user_demands = {d.id for d in r.scalars().all()}

            if not user_demands:
                return json.dumps({"status": "ok", "matches": []}, ensure_ascii=False)

            r = await session.execute(
                select(Match).where(
                    Match.demand_id.in_(user_demands),
                    Match.status == MatchStatus.PENDING,
                ).order_by(Match.score.desc())
            )
            matches = list(r.scalars().all())

        # Load demand & profile names
        result_list = []
        for m in matches:
            async with async_session() as s:
                dr = await s.execute(select(Demand).where(Demand.id == m.demand_id))
                d = dr.scalar_one_or_none()
                pr = await s.execute(select(CapabilityProfile).where(CapabilityProfile.id == m.profile_id))
                p = pr.scalar_one_or_none()
            result_list.append({
                "match_id": m.id,
                "demand_id": m.demand_id,
                "demand_title": (d.raw_text or "")[:80] if d else "",
                "supplier_id": m.profile_id,
                "supplier_name": (p.agent_card_json.get("name", "") if p else ""),
                "score": m.score,
                "status": m.status.value,
                "created_at": m.created_at.isoformat() if m.created_at else "",
            })

        return json.dumps({"status": "ok", "matches": result_list}, ensure_ascii=False)

    except Exception as e:
        logger.exception("[get_pending_matches] 失败")
        return json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False)


@mcp.tool()
async def accept_match(session_token: str, match_id: str, action: str, outcome_detail: str = "") -> str:
    """接受/拒绝匹配。action: accept | reject

    接受后会自动：
    1. 将 Match 状态设为 accepted
    2. 创建 MatchOutcome 记录
    3. 创建 CollaborationWorkspace（供后续协作）
    4. 如果是成功/失败，更新供应商信任分

    拒绝后会自动：
    1. 将 Match 状态设为 rejected
    2. 创建 MatchOutcome 记录（标记失败原因）
    """
    from src.shared.auth import verify
    from src.shared.database import async_session
    from src.shared.models import Match, MatchStatus, MatchOutcome, OutcomeStatus, Demand, CapabilityProfile, CollaborationWorkspace
    from src.shared.flywheel import update_trust_by_outcome
    from sqlalchemy import select
    from uuid import uuid4
    from datetime import datetime, timezone

    if action not in ("accept", "reject"):
        return json.dumps({"status": "error", "message": "action 必须为 accept 或 reject"}, ensure_ascii=False)

    try:
        await verify(session_token)

        async with async_session() as session:
            r = await session.execute(select(Match).where(Match.id == match_id))
            match = r.scalar_one_or_none()
            if not match:
                return json.dumps({"status": "error", "message": "匹配记录不存在"}, ensure_ascii=False)

            new_status = MatchStatus.ACCEPTED if action == "accept" else MatchStatus.REJECTED
            outcome_status = "success" if action == "accept" else "failed"

            match.status = new_status

            # Create MatchOutcome record
            outcome = MatchOutcome(
                id=str(uuid4()),
                match_id=match.id,
                demand_id=match.demand_id,
                supplier_id=match.profile_id,
                status=outcome_status,
                outcome_detail=outcome_detail,
            )
            session.add(outcome)

            # If accepted, create a CollaborationWorkspace
            workspace_id = ""
            if action == "accept":
                # Get demand and profile info
                dr = await session.execute(select(Demand).where(Demand.id == match.demand_id))
                demand = dr.scalar_one_or_none()
                pr = await session.execute(select(CapabilityProfile).where(CapabilityProfile.id == match.profile_id))
                profile = pr.scalar_one_or_none()

                demand_agent_id = demand.user_id if demand else ""
                supply_agent_id = profile.user_id if profile else ""

                ws = CollaborationWorkspace(
                    id=str(uuid4()),
                    match_id=match.id,
                    demand_id=match.demand_id,
                    demand_agent_id=demand_agent_id,
                    supply_agent_id=supply_agent_id,
                    status="active",
                )
                session.add(ws)
                workspace_id = ws.id

            await session.commit()

        # Update trust score asynchronously (fire & forget)
        if outcome_status in ("success", "failed"):
            try:
                # Reload outcome with supplier info
                async with async_session() as s:
                    ro = await s.execute(select(MatchOutcome).where(MatchOutcome.id == outcome.id))
                    loaded = ro.scalar_one_or_none()
                    if loaded:
                        await update_trust_by_outcome(loaded)
            except Exception as e:
                logger.warning(f"[accept_match] trust update skipped: {e}")

        return json.dumps({
            "status": "ok",
            "match_id": match_id,
            "action": action,
            "workspace_id": workspace_id if action == "accept" else "",
            "message": f"匹配已{'接受' if action == 'accept' else '拒绝'}",
        }, ensure_ascii=False)

    except Exception as e:
        logger.exception("[accept_match] 失败")
        return json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False)


@mcp.tool()
async def report_match_outcome(
    session_token: str,
    match_id: str,
    status: str,
    outcome_detail: str = "",
) -> str:
    """📊 报告匹配后续进展，驱动数据飞轮。

    Agent 或用户在联系供应商后，用此工具更新匹配进展。
    每次更新都会影响该供应商的信任分和分类交叉权重。

    status 可选值:
    - contacted: 已联系上供应商，正在沟通
    - negotiating: 正在谈判具体方案
    - success: 合作成功（需求得到满足）
    - failed: 合作失败（技术不匹配/价格问题等）

    建议：初始联系后立即设为 contacted；有进展时更新为 negotiating；
    最终结果设为 success 或 failed（这会影响信任分）。
    """
    from src.shared.auth import verify
    from src.shared.database import async_session
    from src.shared.models import Match, MatchOutcome, OutcomeStatus
    from src.shared.flywheel import update_trust_by_outcome, update_category_weight_by_outcome
    from sqlalchemy import select
    from uuid import uuid4

    valid_statuses = {"contacted": "contacted",
                      "negotiating": "negotiating",
                      "success": "success",
                      "failed": "failed"}

    if status not in valid_statuses:
        return json.dumps({
            "status": "error",
            "message": f"无效 status: {status}。可选: contacted, negotiating, success, failed",
        }, ensure_ascii=False)

    try:
        await verify(session_token)

        async with async_session() as session:
            # 验证 match 存在
            r = await session.execute(select(Match).where(Match.id == match_id))
            match = r.scalar_one_or_none()
            if not match:
                return json.dumps({"status": "error", "message": "匹配记录不存在"}, ensure_ascii=False)

            # 更新 Match 状态
            target_status = valid_statuses[status]
            if status == "success":
                from src.shared.models import MatchStatus
                match.status = MatchStatus.ACCEPTED
            elif status == "failed":
                from src.shared.models import MatchStatus
                match.status = MatchStatus.REJECTED

            # 创建或更新 MatchOutcome
            existing = await session.execute(
                select(MatchOutcome).where(MatchOutcome.match_id == match_id)
            )
            outcome = existing.scalar_one_or_none()

            if outcome:
                outcome.status = target_status
                if outcome_detail:
                    outcome.outcome_detail = outcome_detail
            else:
                outcome = MatchOutcome(
                    id=str(uuid4()),
                    match_id=match.id,
                    demand_id=match.demand_id,
                    supplier_id=match.profile_id,
                    status=target_status,
                    outcome_detail=outcome_detail,
                )
                session.add(outcome)

            await session.commit()

        # 飞轮调整（异步执行）
        try:
            async with async_session() as s:
                ro = await s.execute(select(MatchOutcome).where(MatchOutcome.match_id == match_id))
                loaded = ro.scalar_one_or_none()
                if loaded:
                    await update_trust_by_outcome(loaded)
                    if status in ("success", "failed"):
                        await update_category_weight_by_outcome(loaded)
        except Exception as e:
            logger.warning(f"[report_match_outcome] flywheel update skipped: {e}")

        return json.dumps({
            "status": "ok",
            "match_id": match_id,
            "new_status": status,
            "message": f"匹配进展已更新为: {status}",
        }, ensure_ascii=False)

    except Exception as e:
        logger.exception("[report_match_outcome] 失败")
        return json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False)

@mcp.tool()
async def extend_demand(session_token: str, parent_demand_id: str, user_id: str, raw_text: str, lang: str = "zh") -> str:
    """🔗 将一条需求拆分成子需求。

    供应商收到大需求后，如果发现自己只能做其中一部分，
    或者想把需求分解成更细的条目，可以用此工具创建子需求。
    子需求会：
    1. 关联父需求（通过 parent_id）
    2. 自动结构化并分类
    3. 进入匹配引擎，匹配合适的供应商

    参数：
    - session_token: 会话令牌
    - parent_demand_id: 父需求 ID
    - user_id: 用户 ID
    - raw_text: 子需求的自然语言描述
    - lang: 语言（zh/en）
    """
    from src.shared.auth import verify
    from src.shared.database import async_session

    try:
        await verify(session_token)

        async with async_session() as session:
            svc = DemandService(session)
            sub = await svc.create_sub_demand(parent_demand_id, user_id, raw_text, lang)

            # 获取父需求信息
            parent = await svc.get(parent_demand_id)
            parent_title = ""
            if parent:
                parent_title = (parent.structured_json or {}).get("requirement", {}).get("core_need", "") or parent.raw_text[:60]

            return json.dumps({
                "status": "ok",
                "sub_demand_id": sub.id,
                "parent_demand_id": parent_demand_id,
                "parent_title": parent_title,
                "sub_summary": (sub.structured_json or {}).get("requirement", {}).get("core_need", sub.raw_text[:60]) if sub.structured_json else sub.raw_text[:60],
                "category": sub.category,
                "status": sub.status.value,
                "message": f"子需求已创建，将进入匹配引擎匹配合适的供应商",
            }, ensure_ascii=False)

    except Exception as e:
        logger.exception("[extend_demand] 失败")
        return json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False)


@mcp.tool()
async def get_demand_chain(demand_id: str) -> str:
    """🔗 查看完整需求链路（祖辈需求 → 当前需求 → 子需求）。

    展示需求的完整分解树，帮助理解：
    - 当前需求从哪个大需求拆分而来（ancestors）
    - 当前需求已经被拆分成哪些子需求（children）

    返回按时间排序的完整链路。
    """
    from src.shared.database import async_session

    try:
        async with async_session() as session:
            svc = DemandService(session)
            chain = await svc.get_chain(demand_id)

            return json.dumps({
                "status": "ok",
                "demand_id": demand_id,
                "chain": chain,
                "summary": {
                    "ancestors_count": len(chain.get("ancestors", [])),
                    "children_count": len(chain.get("children", [])),
                    "total_depth": len(chain.get("ancestors", [])) + 1,
                },
            }, ensure_ascii=False)

    except Exception as e:
        logger.exception("[get_demand_chain] 失败")
        return json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False)

@mcp.tool()
async def update_demand(demand_id: str, session_token: str, raw_text: str = "", status: str = "") -> str:
    """修改已有需求。必须先注册/登录获得 session_token。"""
    from src.shared.auth import verify
    await verify(session_token)
    """
    修改已有需求。可更新描述文本或状态。
    status: open | in_progress | fulfilled | closed
    不传的参数保持不变。
    """
    from src.shared.models import Demand, DemandStatus
    try:
        async with async_session() as session:
            from sqlalchemy import select
            result = await session.execute(select(Demand).where(Demand.id == demand_id))
            demand = result.scalar_one_or_none()
            if not demand:
                return json.dumps({"error": "需求不存在"}, ensure_ascii=False)

            changed = []
            if raw_text:
                demand.raw_text = raw_text
                demand.structured_json = None  # 触发重新结构化
                changed.append("raw_text")
            if status:
                status_upper = status.upper().replace(" ", "_")
                valid_values = [s.name.lower() for s in DemandStatus]
                try:
                    st = DemandStatus[status_upper]
                    demand.status = st
                    changed.append(f"status={st.name.lower()}")
                except KeyError:
                    return json.dumps({"error": f"无效状态: {status}。有效值: {valid_values}"}, ensure_ascii=False)

            await session.commit()
            return json.dumps({
                "status": "ok",
                "demand_id": demand_id,
                "changed": changed,
                "current_status": demand.status.value,
            }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)

@mcp.tool()
async def close_demand(demand_id: str, session_token: str) -> str:
    """关闭一条需求。status → cancelled。"""
    return await update_demand(demand_id, session_token=session_token, status="CANCELLED")

@mcp.tool()
async def reclassify_demand(demand_id: str) -> str:
    """
    用AI重新分类已有需求。用于分类不准确时手动触发。
    会重新运行分类引擎，更新学科/IPC/工艺标签。
    """
    from src.shared.models import Demand
    from src.shared.classification import classification_service
    try:
        async with async_session() as session:
            from sqlalchemy import select
            result = await session.execute(select(Demand).where(Demand.id == demand_id))
            demand = result.scalar_one_or_none()
            if not demand:
                return json.dumps({"error": "需求不存在"}, ensure_ascii=False)

            classification = await classification_service.classify(demand.raw_text)
            demand.classification_json = {
                "disciplines": [d.__dict__ if hasattr(d, '__dict__') else d for d in classification.disciplines],
                "ipc_codes": [i.__dict__ if hasattr(i, '__dict__') else i for i in classification.ipc_classes],
                "processes": [p.__dict__ if hasattr(p, '__dict__') else p for p in classification.processes],
            }
            await session.commit()
            return json.dumps({
                "status": "ok",
                "demand_id": demand_id,
                "classification": demand.classification_json,
            }, ensure_ascii=False, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)

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
    """📋 查看一个供应商的完整能力档案。

    先调 search_suppliers 找到感兴趣的供应商，再用此工具看详情。
    返回包括完整描述、技能列表、联系方式、数据来源等。
    """
    from src.shared.database import async_session
    from src.shared.models import CapabilityProfile, UnclaimedSupplier
    from sqlalchemy import select

    try:
        # 先查已注册供应商
        async with async_session() as session:
            result = await session.execute(
                select(CapabilityProfile).where(CapabilityProfile.id == supplier_id)
            )
            profile = result.scalar_one_or_none()

        if profile:
            card = profile.agent_card_json or {}
            return json.dumps({
                "status": "ok",
                "type": "registered",
                "profile": {
                    "id": profile.id,
                    "user_id": profile.user_id,
                    "name": card.get("name", "未命名"),
                    "description": card.get("description", ""),
                    "category": card.get("category", ""),
                    "industry": card.get("industry", ""),
                    "discipline": card.get("discipline", ""),
                    "skills": card.get("skills", []),
                    "achievements": card.get("achievements", []),
                    "contact": card.get("contact", {}),
                    "profile_type": profile.profile_type.value if profile.profile_type else "",
                    "country": profile.country or "",
                    "trust_score": profile.trust_score or 0.0,
                    "verified": profile.verified,
                    "is_claimed": profile.is_claimed,
                    "created_at": profile.created_at.isoformat() if profile.created_at else "",
                }
            }, ensure_ascii=False)

        # 再查未注册供应商
        async with async_session() as session:
            result = await session.execute(
                select(UnclaimedSupplier).where(UnclaimedSupplier.id == supplier_id)
            )
            u = result.scalar_one_or_none()

        if u:
            return json.dumps({
                "status": "ok",
                "type": "unclaimed",
                "profile": {
                    "id": u.id,
                    "name": u.name,
                    "capabilities": u.capabilities,
                    "data_sources": u.data_sources,
                    "contact_hints": u.contact_hints,
                    "country": u.country or "",
                    "discovered_at": u.discovered_at.isoformat() if u.discovered_at else "",
                }
            }, ensure_ascii=False)

        return json.dumps({"status": "not_found", "message": "供应商不存在"}, ensure_ascii=False)

    except Exception as e:
        logger.exception("[get_supplier_detail] 失败")
        return json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False)

@mcp.tool()
async def match_feedback(
    session_token: str,
    demand_id: str,
    matched_supplier_ids: list[str],
    notes: str = "",
) -> str:
    """✅ Agent 告知平台其匹配结论。

    Agent 用 search_suppliers 搜到候选后，用自己的判断决定哪些供应商匹配，
    然后调此工具把结论记录到平台。平台会创建正式 Match 记录并通知相关方。

    参数说明：
    - session_token: 登录后获取的会话令牌
    - demand_id: 需求的 ID
    - matched_supplier_ids: Agent 认为匹配的供应商 ID 列表（最多 10 个）
    - notes: Agent 的匹配理由（可选，帮助人类理解为什么选这些）
    """
    from src.shared.auth import verify
    from src.shared.database import async_session
    from src.shared.models import Match, Demand, DemandStatus
    from sqlalchemy import select
    from uuid import uuid4
    from datetime import datetime, timezone

    try:
        await verify(session_token)

        if not matched_supplier_ids:
            return json.dumps({"status": "error", "message": "请至少提供一个供应商 ID"}, ensure_ascii=False)

        matched_supplier_ids = matched_supplier_ids[:10]  # 最多 10 个
        created = []

        async with async_session() as session:
            # 验证需求存在
            result = await session.execute(select(Demand).where(Demand.id == demand_id))
            demand = result.scalar_one_or_none()
            if not demand:
                return json.dumps({"status": "error", "message": "需求不存在"}, ensure_ascii=False)

            # 更新需求状态为匹配中
            if demand.status == DemandStatus.NEW:
                demand.status = DemandStatus.MATCHING

            for sid in matched_supplier_ids:
                # 避免重复
                existing = await session.execute(
                    select(Match).where(
                        Match.demand_id == demand_id,
                        Match.profile_id == sid,
                    )
                )
                if existing.scalar_one_or_none():
                    continue

                match = Match(
                    id=str(uuid4()),
                    demand_id=demand_id,
                    profile_id=sid,
                    score=1.0,  # Agent 推荐，得分最高
                    status=MatchStatus.PENDING,
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                )
                session.add(match)
                created.append(sid)

            await session.commit()

        return json.dumps({
            "status": "ok",
            "demand_id": demand_id,
            "matched": len(created),
            "supplier_ids": created,
            "notes": notes,
            "message": f"已为需求记录 {len(created)} 个 Agent 推荐匹配",
        }, ensure_ascii=False)

    except Exception as e:
        logger.exception("[match_feedback] 失败")
        return json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False)

@mcp.tool()
async def invite_supplier(session_token: str, supplier_id: str, demand_id: str = "") -> str:
    """📧 邀请供应商加入需求链平台。

    当发现匹配的供应商还不是平台用户时，调用此工具发送邀请。
    如果供应商有关联邮箱，平台会代发邀请邮件（含注册链接）。
    如果没有邮箱，返回邀请链接，用户可以手动转发。

    参数：
    - session_token: 你的会话令牌
    - supplier_id: 供应商 ID（来自 search_suppliers 或 get_supplier_detail）
    - demand_id: 关联的需求 ID（可选，邀请时会说明来意）
    """
    from src.shared.auth import verify
    from src.shared.database import async_session
    from src.shared.models import CapabilityProfile, UnclaimedSupplier, Demand
    from src.shared.outreach import outreach_service
    from urllib.parse import urlencode
    from sqlalchemy import select
    import secrets

    try:
        await verify(session_token)
        invite_code = secrets.token_urlsafe(16)
        base_url = "https://ai-demand-chain.com"

        # 查找供应商
        supplier_name = ""
        supplier_email = ""
        supplier_info = {}

        async with async_session() as session:
            # 先查已注册供应商
            result = await session.execute(
                select(CapabilityProfile).where(CapabilityProfile.id == supplier_id)
            )
            profile = result.scalar_one_or_none()
            if profile:
                card = profile.agent_card_json or {}
                supplier_name = card.get("name", "未命名供应商")
                contact = card.get("contact", {})
                supplier_email = contact.get("email", "") if isinstance(contact, dict) else ""
                supplier_info = {"type": "registered", "name": supplier_name}

            if not profile:
                # 再查未注册供应商
                result = await session.execute(
                    select(UnclaimedSupplier).where(UnclaimedSupplier.id == supplier_id)
                )
                u = result.scalar_one_or_none()
                if u:
                    supplier_name = u.name
                    hints = u.contact_hints or {}
                    if isinstance(hints, dict):
                        emails = hints.get("emails", [])
                        supplier_email = emails[0] if emails else ""
                    supplier_info = {"type": "unclaimed", "name": supplier_name}

            if not supplier_name:
                return json.dumps({"status": "error", "message": "供应商不存在"}, ensure_ascii=False)

            # 获取需求标题（如果有）
            demand_title = ""
            if demand_id:
                result = await session.execute(
                    select(Demand).where(Demand.id == demand_id)
                )
                demand = result.scalar_one_or_none()
                if demand:
                    demand_title = (demand.structured_json or {}).get("summary", "") or demand.raw_text[:60]

        # 生成邀请链接
        invite_params = urlencode({
            "code": invite_code,
            "supplier": supplier_id,
            "name": supplier_name,
            "demand": demand_id or "",
        })
        invite_url = f"{base_url}/claim-profile?{invite_params}"
        register_url = f"{base_url}/login.html"

        # 如果有邮箱，尝试发送邀请邮件
        email_sent = False
        if supplier_email:
            try:
                result = await outreach_service.deliver(
                    demand_id=demand_id or "invite",
                    demand_title=demand_title or "能力匹配邀请",
                    demand_body=(
                        f"我们发现贵公司（{supplier_name}）的能力与一条需求非常匹配。\n\n"
                        f"邀请你加入需求链平台认领你的企业画像，"
                        f"与需求方直接沟通。\n\n"
                        f"认领链接（24小时有效）：{invite_url}"
                    ),
                    match_reason=f"基于能力画像匹配",
                    target_company=supplier_name,
                    target_email=supplier_email,
                )
                email_sent = result.success
            except Exception:
                logger.warning(f"[invite_supplier] 邮件发送失败: {supplier_email}")

        return json.dumps({
            "status": "ok",
            "supplier_name": supplier_name,
            "invite_url": invite_url,
            "register_url": register_url,
            "invite_code": invite_code,
            "email_sent": email_sent,
            "email": supplier_email if email_sent else "",
            "message": (
                f"已生成邀请链接，{'邮件已发送至 ' + supplier_email if email_sent else '请手动将链接发给对方'}"
            ),
        }, ensure_ascii=False)

    except Exception as e:
        logger.exception("[invite_supplier] 失败")
        return json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False)

@mcp.tool()
async def refresh_suppliers(domain: str = "") -> str:
    """手动触发供应商数据刷新。"""
    return json.dumps({"status": "stub", "message": f"域 {domain} 刷新已触发"}, ensure_ascii=False)

@mcp.tool()
async def claim_profile(invite_code: str) -> str:
    """未注册供应商认领画像升级为正式用户。"""
    return json.dumps({"status": "stub"}, ensure_ascii=False)

@mcp.tool()
async def agent_contact_supplier(
    session_token: str,
    supplier_id: str,
    demand_id: str = "",
    message: str = "",
) -> str:
    """💬 Agent 主动联系供应商。

    匹配到供应商后，调用此工具尝试联系对方。
    系统会自动判断最佳联系渠道：

    1. 如果对方有 Agent 在线 → 自动发起 A2A 握手
    2. 如果有邮箱 → 发送需求投递邮件
    3. 兜底 → 生成公开页面链接

    参数：
    - session_token: 你的会话令牌
    - supplier_id: 供应商 ID
    - demand_id: 关联的需求 ID
    - message: 附言（可选，告诉对方你是谁）
    """
    from src.shared.auth import verify
    from src.shared.database import async_session
    from src.shared.models import CapabilityProfile, UnclaimedSupplier, Demand
    from src.shared.outreach import outreach_service
    from sqlalchemy import select
    from uuid import uuid4
    from datetime import datetime, timezone

    try:
        await verify(session_token)

        supplier_name = ""
        supplier_email = ""
        supplier_agent_id = ""
        demand_title = ""

        async with async_session() as session:
            # 查注册供应商
            result = await session.execute(
                select(CapabilityProfile).where(CapabilityProfile.id == supplier_id)
            )
            profile = result.scalar_one_or_none()
            if profile:
                card = profile.agent_card_json or {}
                supplier_name = card.get("name", "未命名")
                contact = card.get("contact", {})
                supplier_email = contact.get("email", "") if isinstance(contact, dict) else ""
                supplier_agent_id = profile.user_id  # Agent ID

            # 查未注册供应商
            if not profile:
                result = await session.execute(
                    select(UnclaimedSupplier).where(UnclaimedSupplier.id == supplier_id)
                )
                u = result.scalar_one_or_none()
                if u:
                    supplier_name = u.name
                    hints = u.contact_hints or {}
                    if isinstance(hints, dict):
                        emails = hints.get("emails", [])
                        supplier_email = emails[0] if emails else ""

            if not supplier_name:
                return json.dumps({"status": "error", "message": "供应商不存在"}, ensure_ascii=False)

            # 获取需求详情
            if demand_id:
                result = await session.execute(
                    select(Demand).where(Demand.id == demand_id)
                )
                demand = result.scalar_one_or_none()
                if demand:
                    demand_title = (demand.structured_json or {}).get("summary", "") or demand.raw_text[:80]

        # 判断最佳联系渠道
        contacted_via = "none"
        public_url = ""

        if supplier_agent_id:
            # 有 Agent → A2A 握手
            from src.shared.models import CollaborationWorkspace
            ws_id = str(uuid4())
            async with async_session() as session:
                ws = CollaborationWorkspace(
                    id=ws_id, match_id="", demand_id=demand_id,
                    demand_agent_id="", supply_agent_id=supplier_agent_id,
                    status="pending", consent_granted=False, following=False,
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                )
                session.add(ws)
                await session.commit()
            contacted_via = "a2a_handshake"

            return json.dumps({
                "status": "ok",
                "supplier_name": supplier_name,
                "contacted_via": "a2a_handshake",
                "workspace_id": ws_id,
                "message": f"已向 {supplier_name} 发起 A2A 握手，等待对方接受",
            }, ensure_ascii=False)

        if supplier_email:
            # 有邮箱 → 发邮件
            result = await outreach_service.deliver(
                demand_id=demand_id or "",
                demand_title=demand_title or "能力匹配",
                demand_body=message or demand_title,
                match_reason="基于 AI 匹配引擎推荐",
                target_company=supplier_name,
                target_email=supplier_email,
            )
            contacted_via = "email"
            public_url = result.public_url

        if not supplier_email:
            # 没有联系方式 → 生成公开页面
            result = await outreach_service.deliver(
                demand_id=demand_id or "",
                demand_title=demand_title or "能力匹配",
                demand_body=message or demand_title,
                match_reason="基于 AI 匹配引擎推荐",
                target_company=supplier_name,
            )
            contacted_via = "public_page"
            public_url = result.public_url

        return json.dumps({
            "status": "ok",
            "supplier_name": supplier_name,
            "contacted_via": contacted_via,
            "public_url": public_url,
            "message": {
                "a2a_handshake": f"已与 {supplier_name} 建立 A2A 连接",
                "email": f"邮件已发送至 {supplier_email}",
                "public_page": f"已生成公开需求页面：{public_url}",
                "none": "无法联系到该供应商（无 Agent、无邮箱）",
            }.get(contacted_via, "联系完成"),
        }, ensure_ascii=False)

    except Exception as e:
        logger.exception("[agent_contact_supplier] 失败")
        return json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False)

@mcp.tool()
async def get_agent_guide(lang: str = "zh") -> str:
    """
    获取Agent接入指南——首次接入时必读。
    如果人类还没有账号，你必须先帮人类注册或登录，才能使用其他功能。
    """
    import os
    path = os.path.join(os.path.dirname(__file__), "..", "AGENT_GUIDE.md")
    guide = ""
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            guide = f.read()

    # 在最前面追加强制性身份检查指引
    mandatory = """
!!! 身份检查 — 调用任何其他工具之前必须先完成 !!!

你现在不能为人类做任何事，除非先确认身份。问人类：

"你好！我是你的AI助手，刚连上需求链平台。你有账号吗？"

如果没有 → 帮注册：register_human(email, display_name, password)
如果有 → 帮登录：login_human(email, password)

完成后再继续。没有身份，其他工具都无法使用。
---
"""
    return mandatory + guide


# ============================================================
# 身份注册 — 人类通过Agent注册账号，跨Agent登录
# ============================================================

@mcp.tool()
async def register_human(email: str, display_name: str, password: str) -> str:
    """
    帮人类注册账号。
    人类告诉Agent：名字+邮箱+密码 → Agent调此工具。
    返回 human_id，人类换AI助手时用邮箱+密码登录即可继续。
    账号同时写入数据库 users 表（持久化）和内存注册表。
    """
    from passlib.hash import bcrypt
    from src.shared.agent_identity import agent_registry, generate_ulid
    from src.shared.database import async_session
    from src.shared.models import User
    from sqlalchemy import select
    try:
        # 检查是否已注册（查数据库）
        async with async_session() as session:
            r = await session.execute(select(User).where(User.email == email))
            existing_user = r.scalar_one_or_none()
            if existing_user:
                return json.dumps({
                    "status": "error",
                    "message": "该邮箱已注册。请让人类用 login_human 登录。"
                }, ensure_ascii=False)

        human_id = generate_ulid()
        hashed = bcrypt.hash(password)

        # 写入数据库 users 表（持久化）
        async with async_session() as session:
            user = User(
                human_id=human_id,
                email=email,
                display_name=display_name,
                password_hash=hashed,
                email_verified=True,  # MCP Agent 注册视为已验证
            )
            session.add(user)
            await session.commit()

        # 同时注册到内存 AgentRegistry
        identity, _ = agent_registry.register(
            human_id=human_id,
            display_name=display_name,
        )
        agent_registry._email_to_human[email] = {
            "human_id": human_id,
            "password_hash": hashed,
        }

        from src.shared.auth import create_token
        token = await create_token(human_id, identity.agent_id)
        return json.dumps({
            "status": "ok",
            "human_id": human_id,
            "agent_id": identity.agent_id,
            "email": email,
            "session_token": token,
            "message": f"注册成功，{display_name}！",
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)

@mcp.tool()
async def login_human(email: str, password: str, display_name: str = "") -> str:
    """
    人类登录。人类把邮箱和密码告诉Agent → Agent调此工具。
    返回 human_id，拿到后可以正常使用所有功能。
    换AI助手时用这个登录，之前的需求、匹配、工作区都还在。
    支持 bcrypt 和 SHA256 密码兼容（旧版SHA256密码自动升级为bcrypt）。
    """
    from passlib.hash import bcrypt
    import hashlib as _hashlib
    from src.shared.agent_identity import agent_registry
    from src.shared.database import async_session
    from src.shared.models import User
    from sqlalchemy import select
    try:
        # 1. 先查内存注册表（最近MCP注册的用户）
        entry = agent_registry._email_to_human.get(email)
        if entry:
            if bcrypt.verify(password, entry["password_hash"]):
                human_id = entry["human_id"]
            else:
                return json.dumps({"error": "密码错误"}, ensure_ascii=False)
        else:
            # 2. 查数据库 users 表（持久化存储）
            async with async_session() as session:
                r = await session.execute(select(User).where(User.email == email))
                user = r.scalar_one_or_none()

            if not user:
                return json.dumps({"error": "邮箱未注册。请先注册。"}, ensure_ascii=False)

            # 3. 密码验证（兼容 bcrypt 和旧版 SHA256）
            stored_hash = user.password_hash
            if stored_hash.startswith("$2b$") or stored_hash.startswith("$2a$"):
                # bcrypt hash
                if not bcrypt.verify(password, stored_hash):
                    return json.dumps({"error": "密码错误"}, ensure_ascii=False)
            else:
                # 旧版 SHA256 hash — 验证后升级到 bcrypt
                if _hashlib.sha256(password.encode()).hexdigest() != stored_hash:
                    return json.dumps({"error": "密码错误"}, ensure_ascii=False)
                # 升级为 bcrypt
                new_hash = bcrypt.hash(password)
                async with async_session() as session:
                    u = await session.get(User, user.human_id)
                    if u:
                        u.password_hash = new_hash
                        await session.commit()

            human_id = user.human_id

            # 同步到内存注册表（后续MCP调用可直接命中）
            agent_registry._email_to_human[email] = {
                "human_id": human_id,
                "password_hash": user.password_hash,
            }
        old_agents = agent_registry.list_for_human(human_id)
        old_name = old_agents[0].display_name if old_agents else email

        # Register this current Agent connection for this human
        new_identity, _ = agent_registry.register(
            human_id=human_id,
            display_name=display_name or old_name,
        )

        from src.shared.auth import create_token
        token = await create_token(human_id, new_identity.agent_id)
        return json.dumps({
            "status": "ok",
            "human_id": human_id,
            "agent_id": new_identity.agent_id,
            "session_token": token,
            "display_name": old_name,
            "total_agents": len(agent_registry.list_for_human(human_id)),
            "message": f"登录成功，{old_name}！你之前的 {len(old_agents)} 个AI助手已关联。",
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)

@mcp.tool()
async def my_account(agent_id: str) -> str:
    """查看当前Agent关联的人类账号信息。"""
    from src.shared.agent_identity import agent_registry
    try:
        identity = agent_registry.get(agent_id)
        if not identity:
            return json.dumps({"status": "unregistered", "message": "尚未注册。请让人类调用 register_human 创建账号。"}, ensure_ascii=False)

        agents = agent_registry.list_for_human(identity.human_id)
        return json.dumps({
            "status": "ok",
            "human_id": identity.human_id,
            "display_name": identity.display_name,
            "agent_count": len(agents),
            "agents": [{"id": a.agent_id[:8], "name": a.display_name} for a in agents],
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)





@mcp.tool()
async def list_available_tools(session_token: str = "") -> str:
    """
    查看你当前可以使用的工具列表。
    未注册/登录时只返回基础工具。注册后返回全部工具。
    """
    from src.shared.auth import verify

    core = [
        {"name": "get_agent_guide", "desc": "读接入指南"},
        {"name": "get_onboarding_skill", "desc": "分步骤完成注册引导"},
        {"name": "register_human", "desc": "注册新账号"},
        {"name": "login_human", "desc": "用邮箱密码登录"},
        {"name": "search_demands", "desc": "搜索公开需求"},
        {"name": "get_demand", "desc": "查看需求详情"},
    ]

    try:
        await verify(session_token)
        # 已认证，返回全部工具
        all_tools = [
            {"name": "publish_demand", "desc": "发布需求"},
            {"name": "search_demands", "desc": "搜索需求"},
            {"name": "get_demand", "desc": "查看需求"},
            {"name": "update_demand", "desc": "修改需求"},
            {"name": "close_demand", "desc": "关闭需求"},
            {"name": "register_capability", "desc": "注册能力画像"},
            {"name": "search_capabilities", "desc": "搜索能力"},
            {"name": "get_pending_matches", "desc": "查看待处理匹配"},
            {"name": "accept_match", "desc": "接受/拒绝匹配"},
            {"name": "extend_demand", "desc": "拆分需求"},
            {"name": "discover_suppliers", "desc": "搜索供应商（同步）"},
            {"name": "create_discovery_task", "desc": "搜索供应商（异步，推荐）"},
            {"name": "get_task", "desc": "查看异步任务进度"},
            {"name": "list_tasks", "desc": "查看所有任务"},
            {"name": "forum_list_topics", "desc": "浏览论坛"},
            {"name": "forum_create_topic", "desc": "发帖"},
            {"name": "forum_reply", "desc": "回复"},
            {"name": "workspace_create", "desc": "创建工作区"},
            {"name": "workspace_add_entry", "desc": "添加工作记录"},
            {"name": "my_account", "desc": "查看账号信息"},
            {"name": "set_demand_preferences", "desc": "设置偏好"},
            {"name": "contribute_to_platform", "desc": "捐赠"},
        ]
        return json.dumps({"status": "authenticated", "tools": all_tools}, ensure_ascii=False)
    except:
        return json.dumps({"status": "new", "tools": core, "message": "注册或登录后可解锁全部工具"}, ensure_ascii=False)



# ============================================================
# Onboarding Skill — 结构化注册引导
# ============================================================

@mcp.tool()
async def get_onboarding_skill(lang: str = "zh") -> str:
    """
    获取结构化注册引导步骤。Agent 按步骤执行，完成一步再进入下一步。
    这是 Skill 版本的 AGENT_GUIDE，比纯文本更可控。
    """
    steps = [
        {
            "step": 1,
            "title": "确认身份",
            "ask_human": "你好！我是你的AI助手。你有需求链平台的账号吗？（邮箱+密码）",
            "action": "如果没有 -> 调 register_human。如果有 -> 调 login_human。",
            "tools": ["register_human", "login_human"],
        },
        {
            "step": 2,
            "title": "设置通知方式",
            "ask_human": "匹配到结果后，你希望我通过什么通知你？(对话内/邮件/微信)",
            "action": "收集通知渠道偏好，后续可调 set_demand_preferences 保存。",
            "tools": ["set_demand_preferences"],
        },
        {
            "step": 3,
            "title": "发布需求或注册能力",
            "ask_human": "你今天是想要什么？1. 发布一个需求找别人解决  2. 注册你的能力等别人来找你",
            "action": "根据选择调 publish_demand 或 register_capability。",
            "tools": ["publish_demand", "register_capability"],
        },
        {
            "step": 4,
            "title": "搜索已有需求/能力",
            "ask_human": "想看看平台上现在有什么吗？",
            "action": "调 search_demands 看广场需求，或 search_capabilities 找供给方。",
            "tools": ["search_demands", "search_capabilities"],
        },
        {
            "step": 5,
            "title": "持续匹配",
            "ask_human": "已完成。有新匹配我会通知你。",
            "action": "定期调 get_pending_matches 查看新匹配。",
            "tools": ["get_pending_matches"],
        },
    ]
    return json.dumps({"skill_name": "新手引导", "steps": steps, "current": 1, "total": 5}, ensure_ascii=False)


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
async def forum_create_topic(session_token: str, agent_id: str, title: str, body: str, category: str = "general", demand_id: str = "") -> str:
    """发布一个新话题。"""
    from src.shared.auth import verify
    await verify(session_token)
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
async def forum_reply(session_token: str, agent_id: str, topic_id: str, body: str) -> str:
    """回复一个话题。"""
    from src.shared.auth import verify
    await verify(session_token)
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
async def workspace_create(session_token: str, match_id: str, demand_id: str, demand_agent_id: str, supply_agent_id: str) -> str:
    """创建协作工作区（匹配接受后自动调用）。"""
    from src.shared.auth import verify
    await verify(session_token)
    from src.matching.collaboration import CollaborationService
    try:
        async with async_session() as session:
            svc = CollaborationService(session)
            ws = await svc.create_workspace(match_id, demand_id, demand_agent_id, supply_agent_id)
            return json.dumps({"status": "ok", "workspace_id": ws.id}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)

@mcp.tool()
async def workspace_add_entry(session_token: str, workspace_id: str, agent_id: str, entry_type: str, content: str,
                               visible_to_demand: bool = True, visible_to_supply: bool = True) -> str:
    """
    向工作区添加一条工作记忆。
    entry_type: clarification(需求澄清)| spec_refinement(指标细化)| proposal(方案建议)| decision(决策)| progress(进展)| blocker(障碍)
    """
    from src.shared.auth import verify
    await verify(session_token)
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
async def workspace_grant_consent(session_token: str, workspace_id: str) -> str:
    """需求方授权供给方参与协作、查看进展。"""
    from src.shared.auth import verify
    await verify(session_token)
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
async def workspace_follow(session_token: str, workspace_id: str) -> str:
    """供给方关注需求进展（需先获得需求方授权）。关注后，需求状态变更时Agent会收到通知。"""
    from src.shared.auth import verify
    await verify(session_token)
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
async def import_discovered_demand(session_token: str, demand_id: str, user_id: str) -> str:
    """将一条公开发现的需求转为正式需求，发布到平台上。"""
    from src.shared.auth import verify
    await verify(session_token)
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

    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


# ============================================================
# 异步任务系统 — 爬虫等耗时操作改为 task 模式
# ============================================================


@mcp.tool()
async def firecrawl_search(query: str, source: str = "web", limit: int = 5) -> str:
    """
    用 Firecrawl 全网搜索。source: web | patent | procurement | academic。
    不需要 session_token，公开可用。
    """
    from src.adapters.firecrawl_client import get_firecrawl
    try:
        fc = get_firecrawl()
        if source == "patent":
            results = await fc.search_patents(query, limit)
        elif source == "procurement":
            results = await fc.search_procurement(query, limit)
        elif source == "academic":
            results = await fc.search_academic(query, limit)
        else:
            results = await fc.search_web(query, limit)
        return json.dumps({"status": "ok", "source": source, "query": query, "results": results}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@mcp.tool()
async def firecrawl_scrape(url: str) -> str:
    """抓取单页 URL 内容。不需要 session_token。"""
    from src.adapters.firecrawl_client import get_firecrawl
    try:
        fc = get_firecrawl()
        result = await fc.scrape_url(url)
        return json.dumps(result, ensure_ascii=False, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@mcp.tool()
async def create_discovery_task(session_token: str, demand_keywords: str, ipc_class: str = "") -> str:
    """
    开始搜索潜在供给方（异步）。立即返回 taskId，Agent 调 get_task 轮询结果。
    关键词用逗号分隔。示例："高温传感器,管道检测,800度"
    """
    from src.shared.auth import verify
    from src.shared.task_manager import create_task, complete_task, fail_task
    import asyncio
    try:
        auth = await verify(session_token)
        human_id = auth["human_id"]
        task_id = await create_task(human_id, f"发现供应商: {demand_keywords[:30]}")

        # 后台执行
        async def run_discovery():
            try:
                from src.discovery.engine import discover_for_demand
                keywords = [k.strip() for k in demand_keywords.split(",") if k.strip()]
                if not keywords:
                    await fail_task(task_id, "请提供至少一个关键词")
                    return
                results = await discover_for_demand(demand_keywords, keywords)
                # 写入 unclaimed_suppliers 表
                from src.shared.database import async_session
                async with async_session() as session:
                    from src.shared.models import UnclaimedSupplier
                    for item in results:
                        import hashlib
                        fp = hashlib.md5(json.dumps(item, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
                        existing = await session.execute(
                            __import__("sqlalchemy").select(UnclaimedSupplier).where(UnclaimedSupplier.fingerprint == fp)
                        )
                        if not existing.scalar_one_or_none():
                            session.add(UnclaimedSupplier(
                                name=item.get("name", ""),
                                source=item.get("source", "web"),
                                url=item.get("url", ""),
                                description=item.get("description", ""),
                                capability_tags=item.get("capability_tags", []),
                                fingerprint=fp,
                                score=item.get("score", 0.0),
                            ))
                    await session.commit()
                await complete_task(task_id, results)
            except Exception as e:
                await fail_task(task_id, str(e))

        asyncio.create_task(run_discovery())

        return json.dumps({
            "status": "ok",
            "task_id": task_id,
            "message": "搜索任务已创建，用 await get_task(task_id) 查看进度。",
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@mcp.tool()
async def get_task(task_id: str, session_token: str = "") -> str:
    """查看异步任务进度和结果。task_id 从 create_discovery_task 获得。"""
    from src.shared.task_manager import get_task
    try:
        human_id = ""
        if session_token:
            from src.shared.auth import verify
            auth = await verify(session_token)
            human_id = auth["human_id"]
        result = await get_task(task_id, human_id)
        return json.dumps(result, ensure_ascii=False, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@mcp.tool()
async def list_tasks(session_token: str, limit: int = 10) -> str:
    """查看所有异步任务列表。包括正在运行的和已完成的。"""
    from src.shared.auth import verify
    from src.shared.task_manager import list_tasks
    try:
        auth = await verify(session_token)
        tasks = await list_tasks(auth["human_id"], limit)
        return json.dumps({"tasks": tasks}, ensure_ascii=False, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)

@mcp.tool()
async def contribute_to_platform(session_token: str, 
    match_id: str, demand_id: str, agent_id: str,
    contribution_type: str = "money",
    amount: float = 0.0, currency: str = "CNY",
    testimonial_text: str = "", referral_count: int = 0
) -> str:
    """
    记录一笔自愿贡献。完全自愿——不付钱也继续用全部功能。
    contribution_type: money | testimonial | referral | code | content
    """
    from src.shared.auth import verify
    await verify(session_token)
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
async def set_demand_preferences(session_token: str, 
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
    from src.shared.auth import verify
    await verify(session_token)
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
# Human Capability Recording
# ============================================================

@mcp.tool()
async def publish_human_capability(
    agent_id: str,
    industry: str,
    skills: str,
    description: str = "",
    country: str = "",
    name: str = "",
) -> str:
    """Agent 主动记录他服务的人类的行业、技能和能力到需求链平台。
    这样需求方Agent在寻找匹配时就能发现这个人类的能力画像。

    agent_id: Agent的唯一标识（你的人类用户的邮箱或ID）
    industry: 行业领域（如"传感器技术"、"新能源"、"AI"等）
    skills: 技能列表，逗号分隔（如"MEMS设计,嵌入式系统,PCB Layout"）
    description: 一句话能力描述
    country: 国家/地区
    name: 人类的姓名或昵称
    """
    from uuid import uuid4
    try:
        async with async_session() as session:
            from src.shared.models import CapabilityProfile
            from sqlalchemy import select

            skill_list = [s.strip() for s in skills.split(",") if s.strip()]

            # Check if this human already has a profile
            existing = await session.execute(
                select(CapabilityProfile).where(CapabilityProfile.user_id == agent_id)
            )
            profile = existing.scalar_one_or_none()

            if profile:
                # Update existing
                card = profile.agent_card_json or {}
                card["industry"] = industry
                if skill_list:
                    card["skills"] = list(set(card.get("skills", []) + skill_list))
                if description:
                    card["description"] = description
                if country:
                    profile.country = country
                if name:
                    card["name"] = name
                profile.agent_card_json = card
                action = "updated"
            else:
                # Create new
                card = {
                    "name": name or agent_id,
                    "description": description or f"{industry}领域的专业人士",
                    "industry": industry,
                    "category": industry,
                    "skills": skill_list,
                    "discipline": "",
                    "trl": 0,
                    "url": "",
                }
                profile = CapabilityProfile(
                    id=str(uuid4()),
                    user_id=agent_id,
                    profile_type="INDIVIDUAL",
                    country=country or "中国",
                    agent_card_json=card,
                    trust_score=0.5,
                    is_claimed=True,
                    verified=False,
                )
                session.add(profile)
                action = "created"

            await session.commit()
            logger.info(f"[Capability] {action} profile for {agent_id}: {industry}")
            return json.dumps({
                "status": "ok",
                "action": action,
                "profile_id": profile.id,
                "industry": industry,
                "skills": skill_list,
            }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)

@mcp.tool()
async def get_human_capability(agent_id: str) -> str:
    """查询某个Agent服务的人类的已记录能力画像。"""
    try:
        async with async_session() as session:
            from src.shared.models import CapabilityProfile
            from sqlalchemy import select
            r = await session.execute(
                select(CapabilityProfile).where(CapabilityProfile.user_id == agent_id)
            )
            p = r.scalar_one_or_none()
            if not p:
                return json.dumps({"status": "not_found", "message": "该Agent尚未记录其人类用户的能力信息。可以让Agent调用 publish_human_capability 来记录。"}, ensure_ascii=False)
            card = p.agent_card_json or {}
            return json.dumps({
                "profile_id": p.id,
                "name": card.get("name", ""),
                "industry": card.get("industry", ""),
                "skills": card.get("skills", []),
                "description": card.get("description", ""),
                "country": p.country,
                "trust_score": p.trust_score,
                "verified": p.verified,
                "created_at": p.created_at.isoformat() if p.created_at else "",
            }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


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

# ============================================================
# A2A 通信工具
# ============================================================

@mcp.tool()
async def agent_handshake(
    session_token: str,
    target_agent_id: str,
    my_agent_id: str,
    message: str = "",
) -> str:
    """🤝 向另一个 Agent 发起 A2A 握手。

    匹配完成后，Agent 可以调用此工具向匹配到的对方 Agent 发起沟通。
    平台会创建握手通道，并通知对方 Agent。

    参数：
    - session_token: 你的会话令牌
    - target_agent_id: 目标 Agent 的 ID（从 search_suppliers 结果中获得）
    - my_agent_id: 你自己的 Agent ID
    - message: 附言（可选，告诉对方你是谁、想聊什么）
    """
    from src.shared.auth import verify
    from src.shared.database import async_session
    from src.shared.models import CollaborationWorkspace
    from uuid import uuid4
    from datetime import datetime, timezone

    try:
        await verify(session_token)

        if not target_agent_id or not my_agent_id:
            return json.dumps({"status": "error", "message": "请提供双方 Agent ID"}, ensure_ascii=False)

        workspace_id = str(uuid4())
        async with async_session() as session:
            ws = CollaborationWorkspace(
                id=workspace_id,
                match_id="",  # 可选关联匹配
                demand_id="",
                demand_agent_id=my_agent_id,
                supply_agent_id=target_agent_id,
                status="pending",
                consent_granted=False,
                following=False,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            session.add(ws)
            await session.commit()

        return json.dumps({
            "status": "ok",
            "workspace_id": workspace_id,
            "message": f"已向 {target_agent_id[:8]}... 发起握手，等待对方接受",
            "handshake_status": "pending",
        }, ensure_ascii=False)

    except Exception as e:
        logger.exception("[agent_handshake] 失败")
        return json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False)


@mcp.tool()
async def agent_accept_handshake(
    session_token: str,
    workspace_id: str,
    my_agent_id: str,
    accept: bool = True,
    reply_message: str = "",
) -> str:
    """✅ 接受或拒绝另一个 Agent 的 A2A 握手邀请。

    收到握手通知后，调用此工具回应对方。
    接受后双方获得一个协作工作区，可以在其中交换信息。
    """
    from src.shared.auth import verify
    from src.shared.database import async_session
    from src.shared.models import CollaborationWorkspace
    from sqlalchemy import select
    from datetime import datetime, timezone

    try:
        await verify(session_token)

        async with async_session() as session:
            result = await session.execute(
                select(CollaborationWorkspace).where(CollaborationWorkspace.id == workspace_id)
            )
            ws = result.scalar_one_or_none()
            if not ws:
                return json.dumps({"status": "error", "message": "握手通道不存在"}, ensure_ascii=False)

            if accept:
                ws.status = "active"
                ws.consent_granted = True
                ws.consent_granted_at = datetime.now(timezone.utc)
                ws.updated_at = datetime.now(timezone.utc)
                await session.commit()
                return json.dumps({
                    "status": "ok",
                    "workspace_id": workspace_id,
                    "handshake_status": "accepted",
                    "message": "已接受握手，现在可以使用 agent_send_message 与对方通信",
                }, ensure_ascii=False)
            else:
                ws.status = "rejected"
                ws.updated_at = datetime.now(timezone.utc)
                await session.commit()
                return json.dumps({
                    "status": "ok",
                    "workspace_id": workspace_id,
                    "handshake_status": "rejected",
                }, ensure_ascii=False)

    except Exception as e:
        logger.exception("[agent_accept_handshake] 失败")
        return json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False)


@mcp.tool()
async def agent_get_card(
    agent_id: str,
) -> str:
    """📇 获取任意 Agent 的公开能力画像（Agent Card）。

    不需要握手即可查询。返回该 Agent 的公开信息：
    名称、描述、行业、分类、技能、信任分等。
    相当于 /.well-known/agent.json?agent_id=xxx 的 MCP 版本。
    """
    from src.shared.database import async_session
    from src.shared.models import CapabilityProfile
    from sqlalchemy import select

    try:
        async with async_session() as session:
            result = await session.execute(
                select(CapabilityProfile).where(CapabilityProfile.id == agent_id)
            )
            profile = result.scalar_one_or_none()
            if not profile:
                return json.dumps({"status": "not_found", "message": "Agent 不存在"}, ensure_ascii=False)

            card = profile.agent_card_json or {}
            return json.dumps({
                "status": "ok",
                "agent_id": profile.id,
                "name": card.get("name", "Unknown"),
                "description": card.get("description", ""),
                "category": card.get("category", ""),
                "industry": card.get("industry", ""),
                "discipline": card.get("discipline", ""),
                "skills": card.get("skills", []),
                "trust_score": profile.trust_score or 0.0,
                "profile_type": profile.profile_type.value if profile.profile_type else "",
                "country": profile.country or "",
                "url": card.get("url", ""),
                "trl": card.get("trl", ""),
            }, ensure_ascii=False)

    except Exception as e:
        logger.exception("[agent_get_card] 失败")
        return json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False)


# ============================================================
# 主入口
# ============================================================

def run():
    logging.basicConfig(level=logging.INFO)
    logger.info("需求链 MCP Server 启动中 (0.0.0.0:8000)...")

    # Initialize database tables
    import asyncio
    from src.shared.database import init_db
    asyncio.run(init_db())

    # Mount HTTP API routes on the same SSE app
    from src.web_server import api_auto_demand, api_auto_supplier, api_demand_list, api_suppliers
    from starlette.routing import Route

    app = mcp.sse_app()
    # Add auto-demand and auto-supplier routes
    for route_def in [
        Route("/api/auto-demand", api_auto_demand, methods=["POST"]),
        Route("/api/auto-supplier", api_auto_supplier, methods=["POST"]),
        Route("/api/demands", api_demand_list),
        Route("/api/suppliers", api_suppliers),
    ]:
        app.router.routes.insert(0, route_def)

    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=mcp.settings.port, log_level="info")


if __name__ == "__main__":
    run()
