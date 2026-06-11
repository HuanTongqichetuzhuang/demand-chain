"""
匹配引擎 — 将需求与供应商能力档案进行匹配，生成 Match 记录。
使用 TF-IDF + 分类重叠度计算匹配分数。
"""
import asyncio, json, logging, os, sys
from datetime import datetime, timezone
from uuid import uuid4

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.shared.database import async_session
from src.shared.models import (
    Demand, DemandStatus, CapabilityProfile, Match, MatchStatus
)
from src.shared.semantic_search import TfidfSearch, demand_search
from sqlalchemy import select

logger = logging.getLogger(__name__)


async def build_supplier_index() -> tuple[dict[str, CapabilityProfile], TfidfSearch]:
    """构建供应商 TF-IDF 索引"""
    async with async_session() as session:
        result = await session.execute(select(CapabilityProfile).limit(500))
        profiles = list(result.scalars().all())

    idx = TfidfSearch()
    id_to_profile = {}
    for p in profiles:
        text = ""
        card = p.agent_card_json or {}
        text += (card.get("name", "") or "") + " "
        text += (card.get("description", "") or "") + " "
        text += (card.get("category", "") or "") + " "
        text += (card.get("industry", "") or "") + " "
        text += (card.get("discipline", "") or "") + " "
        text += " ".join(card.get("skills", []) or []) + " "
        idx.add(p.id, text)
        id_to_profile[p.id] = p

    idx.build_index()
    return id_to_profile, idx


def _category_overlap(demand_cat: str, supplier_cat: str) -> float:
    """计算分类重叠度"""
    if not demand_cat or not supplier_cat:
        return 0.0
    d = demand_cat.lower().strip()
    s = supplier_cat.lower().strip()
    if d == s:
        return 1.0
    if d in s or s in d:
        return 0.6
    return 0.0


async def match_one_demand(
    demand: Demand,
    supplier_index: TfidfSearch,
    id_to_profile: dict[str, CapabilityProfile],
    top_k: int = 5,
) -> list[dict]:
    """为单条需求找最佳匹配供应商"""
    # Build query text
    query = (demand.raw_text or "")[:500]
    if demand.structured_json:
        s = demand.structured_json
        query += " " + (s.get("summary", "") or "")
        query += " " + " ".join(s.get("tags", []))
    if demand.search_text:
        query += " " + demand.search_text

    results = supplier_index.search(query, top_k=top_k * 2)

    matches = []
    for sid, tfidf_score in results:
        profile = id_to_profile.get(sid)
        if not profile:
            continue

        cat_score = 0.0
        card = profile.agent_card_json or {}
        scat = card.get("category", "") or card.get("industry", "")
        dcat = demand.category or ""
        cat_score = _category_overlap(dcat, scat)

        # Final score: 60% text match + 30% category + 10% trust
        final = (
            tfidf_score * 0.6
            + cat_score * 0.3
            + (profile.trust_score or 0.0) * 0.1
        )

        matches.append({
            "profile_id": sid,
            "score": round(final, 4),
            "tfidf_score": round(tfidf_score, 4),
            "cat_score": round(cat_score, 4),
            "supplier_name": card.get("name", "Unknown"),
            "supplier_category": scat,
        })

    # Sort and dedup
    matches.sort(key=lambda x: -x["score"])
    seen_names = set()
    deduped = []
    for m in matches:
        if m["supplier_name"] not in seen_names:
            seen_names.add(m["supplier_name"])
            deduped.append(m)
    return deduped[:top_k]


async def run_matching(dry_run: bool = False) -> dict:
    """对全部 OPEN 需求执行匹配"""
    async with async_session() as session:
        result = await session.execute(
            select(Demand)
            .where(Demand.status == DemandStatus.OPEN)
            .order_by(Demand.created_at.desc())
        )
        demands = list(result.scalars().all())

    if not demands:
        return {"matched": 0, "total": 0, "message": "没有 OPEN 需求"}

    print(f"需求: {len(demands)} 条 OPEN")
    id_to_profile, sidx = await build_supplier_index()
    print(f"供应商: {len(id_to_profile)} 家已索引")

    results = []
    for i, demand in enumerate(demands):
        matches = await match_one_demand(demand, sidx, id_to_profile)
        results.append({"demand_id": demand.id, "demand_title": (demand.raw_text or demand.id)[:60], "matches": matches})

        if not dry_run and matches:
            async with async_session() as session:
                for m in matches[:3]:
                    # Check existing match
                    existing = await session.execute(
                        select(Match).where(
                            Match.demand_id == demand.id,
                            Match.profile_id == m["profile_id"],
                        )
                    )
                    if existing.scalar_one_or_none():
                        continue
                    match = Match(
                        id=str(uuid4()),
                        demand_id=demand.id,
                        profile_id=m["profile_id"],
                        score=m["score"],
                        status=MatchStatus.PENDING,
                    )
                    session.add(match)
                await session.commit()

        print(f"[{i+1}/{len(demands)}] {demand.raw_text[:50]}... → {len(matches)} 候选")

    total_matches = sum(len(r["matches"]) for r in results)
    return {"matched": total_matches, "total": len(demands), "results": results}


async def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true", help="不写入数据库")
    args = p.parse_args()

    dry = args.dry_run
    if dry:
        print("=== 试运行模式（不写入数据库）===\n")

    result = await run_matching(dry_run=dry)
    print(f"\n{'='*50}")
    print(f"完成: {result['total']} 条需求, 共 {result['matched']} 条匹配候选")

    if dry and result.get("results"):
        print("\n--- 前 3 条需求的匹配结果 ---")
        for r in result["results"][:3]:
            print(f"\n需求: {r['demand_title']}")
            for m in r["matches"][:3]:
                print(f"  {m['supplier_name']} (得分: {m['score']:.3f}, 分类: {m['supplier_category']})")


if __name__ == "__main__":
    asyncio.run(main())
