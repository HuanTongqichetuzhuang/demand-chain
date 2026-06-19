"""
数据飞轮引擎 — 匹配结果反哺算法，自动调整权重。
每次匹配→联系→成功/失败的结果都会影响后续匹配的排序。
"""
import logging
from datetime import datetime, timezone, timedelta
from uuid import uuid4

from sqlalchemy import select, func, and_, or_, update

from src.shared.database import async_session
from src.shared.models import (
    MatchOutcome, OutcomeStatus, CategoryWeight,
    CapabilityProfile, Match, MatchStatus,
)

logger = logging.getLogger(__name__)

# ── 信任分调整常量 ──────────────────────────────────────────

TRUST_DELTA_SUCCESS = 0.15     # 合作成功 → trust_score +0.15
TRUST_DELTA_FAILED = -0.10     # 匹配失败 → trust_score -0.10
TRUST_DELTA_CONTACTED = 0.05   # 已联系 → trust_score +0.05
TRUST_DELTA_NEGOTIATING = 0.10 # 谈判中 → trust_score +0.10
TRUST_SCORE_MAX = 2.0          # trust_score 上限
TRUST_SCORE_MIN = 0.0          # trust_score 下限

CATEGORY_WEIGHT_DELTA_SUCCESS = 0.08   # 成功 → 分类权重 +0.08
CATEGORY_WEIGHT_DELTA_FAILED = -0.05   # 失败 → 分类权重 -0.05
CATEGORY_WEIGHT_MAX = 1.0             # 权重上限
CATEGORY_WEIGHT_MIN = 0.0             # 权重下限
CATEGORY_WEIGHT_DEFAULT = 0.5         # 默认权重


# ── 信任分更新 ──────────────────────────────────────────────

async def update_trust_score(supplier_id: str, delta: float) -> float:
    """更新供应商信任分，返回更新后的值。"""
    async with async_session() as session:
        r = await session.execute(
            select(CapabilityProfile).where(CapabilityProfile.id == supplier_id)
        )
        profile = r.scalar_one_or_none()
        if not profile:
            logger.warning(f"[Flywheel] supplier {supplier_id} not found, skipping trust update")
            return 0.0

        new_score = profile.trust_score + delta
        new_score = max(TRUST_SCORE_MIN, min(TRUST_SCORE_MAX, new_score))
        profile.trust_score = new_score
        await session.commit()
        logger.info(f"[Flywheel] trust_score {supplier_id}: {profile.trust_score:.2f} → {new_score:.2f} (Δ={delta:+.2f})")
        return new_score


async def update_trust_by_outcome(outcome: MatchOutcome):
    """根据结果状态自动调整信任分。"""
    delta = {
        "success": TRUST_DELTA_SUCCESS,
        "failed": TRUST_DELTA_FAILED,
        "contacted": TRUST_DELTA_CONTACTED,
        "negotiating": TRUST_DELTA_NEGOTIATING,
    }.get(outcome.status, 0.0)

    if delta != 0.0:
        await update_trust_score(outcome.supplier_id, delta)


# ── 分类交叉权重更新 ──────────────────────────────────────────

async def _get_category_pair(outcome: MatchOutcome) -> tuple[str, str] | None:
    """从 outcome 获取需求分类和供应商分类。"""
    from src.shared.models import Demand, CapabilityProfile
    async with async_session() as session:
        r = await session.execute(select(Demand).where(Demand.id == outcome.demand_id))
        demand = r.scalar_one_or_none()
        r = await session.execute(select(CapabilityProfile).where(CapabilityProfile.id == outcome.supplier_id))
        profile = r.scalar_one_or_none()

    if not demand or not profile:
        return None
    dcat = (demand.category or "").strip().lower()
    scat = (profile.agent_card_json or {}).get("category", "").strip().lower()
    if not dcat or not scat:
        return None
    return (dcat, scat)


async def adjust_category_weight(demand_category: str, supplier_category: str, delta: float):
    """调整两个分类之间的交叉权重。"""
    dcat = demand_category.strip().lower()
    scat = supplier_category.strip().lower()
    if not dcat or not scat:
        return

    async with async_session() as session:
        r = await session.execute(
            select(CategoryWeight).where(
                CategoryWeight.demand_category == dcat,
                CategoryWeight.supplier_category == scat,
            )
        )
        cw = r.scalar_one_or_none()

        if cw:
            new_weight = cw.weight + delta
            new_weight = max(CATEGORY_WEIGHT_MIN, min(CATEGORY_WEIGHT_MAX, new_weight))
            cw.weight = new_weight
        else:
            new_weight = max(CATEGORY_WEIGHT_MIN, min(CATEGORY_WEIGHT_MAX, CATEGORY_WEIGHT_DEFAULT + delta))
            cw = CategoryWeight(
                id=str(uuid4()),
                demand_category=dcat,
                supplier_category=scat,
                weight=new_weight,
            )
            session.add(cw)

        await session.commit()
        logger.info(f"[Flywheel] category weight ({dcat}×{scat}): {cw.weight:.2f} (Δ={delta:+.2f})")


async def update_category_weight_by_outcome(outcome: MatchOutcome):
    """根据结果调整需求-供应商分类交叉权重。"""
    pair = await _get_category_pair(outcome)
    if not pair:
        return

    delta = {
        "success": CATEGORY_WEIGHT_DELTA_SUCCESS,
        "failed": CATEGORY_WEIGHT_DELTA_FAILED,
    }.get(outcome.status.value if hasattr(outcome.status, 'value') else outcome.status, 0.0)

    if delta != 0.0:
        await adjust_category_weight(pair[0], pair[1], delta)


# ── 学习周期 ──────────────────────────────────────────────────

async def run_learning_cycle(batch_size: int = 100) -> dict:
    """批量处理未学习过的 match_outcomes，更新信任分和分类权重。

    每个 outcome 只会被处理一次（processing_flag 通过 updated_at 判断）。
    返回本次处理的统计。
    """
    stats = {"processed": 0, "trust_updated": 0, "weight_updated": 0, "errors": 0}

    async with async_session() as session:
        # 找最近未处理的 outcomes（按 updated_at 判断，只有刚更新的才是未处理过的）
        # 实际用 cutoff：处理 updated_at == created_at 的记录（刚创建，未被学习周期碰过）
        r = await session.execute(
            select(MatchOutcome).where(
                MatchOutcome.updated_at == MatchOutcome.created_at,
            ).order_by(MatchOutcome.created_at.asc()).limit(batch_size)
        )
        outcomes = list(r.scalars().all())

    for outcome in outcomes:
        try:
            # 更新信任分
            await update_trust_by_outcome(outcome)
            stats["trust_updated"] += 1

            # 对 success/failed 额外调整分类权重
            st = outcome.status.value if hasattr(outcome.status, 'value') else outcome.status
            if st in ("success", "failed"):
                await update_category_weight_by_outcome(outcome)
                stats["weight_updated"] += 1

            # 标记已处理：更新 updated_at
            async with async_session() as session:
                await session.execute(
                    update(MatchOutcome)
                    .where(MatchOutcome.id == outcome.id)
                    .values(updated_at=datetime.utcnow())
                )
                await session.commit()

            stats["processed"] += 1

        except Exception as e:
            stats["errors"] += 1
            logger.error(f"[Flywheel] Error processing outcome {outcome.id}: {e}")

    logger.info(f"[Flywheel] Learning cycle done: {stats}")
    return stats


# ── 获取交叉权重（供匹配引擎调用） ──────────────────────────────

async def get_category_weight(demand_category: str, supplier_category: str) -> float:
    """获取两个分类之间的交叉权重，不存在则返回默认值 0.5。"""
    dcat = demand_category.strip().lower()
    scat = supplier_category.strip().lower()
    if not dcat or not scat:
        return CATEGORY_WEIGHT_DEFAULT

    async with async_session() as session:
        r = await session.execute(
            select(CategoryWeight.weight).where(
                CategoryWeight.demand_category == dcat,
                CategoryWeight.supplier_category == scat,
            )
        )
        weight = r.scalar_one_or_none()
    return weight if weight is not None else CATEGORY_WEIGHT_DEFAULT


# ── 统计查询（供仪表盘 API 使用） ──────────────────────────────

async def get_flywheel_stats() -> dict:
    """返回飞轮运行的关键指标。"""
    async with async_session() as session:
        # 各阶段计数
        status_counts = {}
        for val in ("matched", "contacted", "negotiating", "success", "failed"):
            r = await session.execute(
                select(func.count(MatchOutcome.id)).where(MatchOutcome.status == val)
            )
            status_counts[val] = r.scalar() or 0

        # 成功率
        total_resolved = status_counts.get("success", 0) + status_counts.get("failed", 0)
        success_rate = round(status_counts.get("success", 0) / total_resolved * 100, 1) if total_resolved > 0 else 0.0

        # 权重分布
        r = await session.execute(select(func.count(CategoryWeight.id)))
        weight_count = r.scalar() or 0

        # trust_score 分布
        r = await session.execute(
            select(
                func.avg(CapabilityProfile.trust_score),
                func.min(CapabilityProfile.trust_score),
                func.max(CapabilityProfile.trust_score),
            )
        )
        row = r.one()
        trust_stats = {
            "avg": round(row[0], 4) if row[0] else 0,
            "min": round(row[1], 4) if row[1] else 0,
            "max": round(row[2], 4) if row[2] else 0,
        }

        # 今日新增
        today = datetime.utcnow().date()
        r = await session.execute(
            select(func.count(MatchOutcome.id)).where(
                func.date(MatchOutcome.created_at) == today
            )
        )
        today_count = r.scalar() or 0

    return {
        "total_outcomes": sum(status_counts.values()),
        "status_breakdown": status_counts,
        "success_rate": success_rate,
        "category_weights_count": weight_count,
        "trust_score": trust_stats,
        "today_new": today_count,
    }


async def get_weight_matrix() -> list[dict]:
    """返回完整的权重矩阵（前 100 条）。"""
    async with async_session() as session:
        r = await session.execute(
            select(CategoryWeight).order_by(CategoryWeight.weight.desc()).limit(100)
        )
        weights = list(r.scalars().all())
    return [{
        "demand_category": w.demand_category,
        "supplier_category": w.supplier_category,
        "weight": w.weight,
    } for w in weights]

