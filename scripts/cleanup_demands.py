"""
清理脚本：1) 删除 GitHub Issues 功能需求 2) 英文需求翻译为中文
"""
import asyncio, sys, re
sys.path.insert(0, '/app')

from src.shared.database import async_session
from src.shared.models import Demand
from sqlalchemy import select, func, delete

# GitHub Issues 的识别标记
GITHUB_ISSUE_PATTERNS = [
    "### 🚀 The feature, motivation and pitch",
    "<!-- Please target the `master` branch",
    "<!--\nPlease target the `master` branch",
    "repo:pytorch/pytorch",
    "repo:kubernetes/kubernetes",
    "repo:rust-lang/rust",
    "repo:golang/go",
    "repo:microsoft/vscode",
    "repo:home-assistant/core",
    "repo:opencv/opencv",
    "repo:godotengine/godot",
    "Provide shutdown() method for ProcessGroupGloo",
    "extend torch.distributed",
    "pytorch should allow setuptools",
]


def is_english(text):
    if not text or len(text.strip()) < 20:
        return False
    cjk = sum(1 for c in text if '\u4e00' <= c <= '\u9fff' or '\u3400' <= c <= '\u4dbf')
    total = max(len(text.strip()), 1)
    return (cjk / total) < 0.1  # 少于10%中文字符


async def delete_github_issues():
    async with async_session() as s:
        # Find all GitHub Issues demands
        all_crawler = await s.execute(
            select(Demand).where(Demand.user_id == 'crawler')
        )
        to_delete = []
        for d in all_crawler.scalars().all():
            text = d.raw_text or ""
            for pat in GITHUB_ISSUE_PATTERNS:
                if pat in text:
                    to_delete.append(d.id)
                    break
        
        if to_delete:
            # First delete related matches and match_outcomes
            from src.shared.models import Match, MatchOutcome
            await s.execute(delete(Match).where(Match.demand_id.in_(to_delete)))
            await s.execute(delete(MatchOutcome).where(MatchOutcome.demand_id.in_(to_delete)))
            # Then delete the demands
            await s.execute(delete(Demand).where(Demand.id.in_(to_delete)))
            await s.commit()
            print(f"已删除 {len(to_delete)} 条 GitHub Issues 需求")
        else:
            print("未找到 GitHub Issues 数据")
        return to_delete


async def translate_english():
    """将数据库中英文需求翻译为中文，使用 DeepSeek API"""
    from src.adapters.llm_client import get_llm
    
    async with async_session() as s:
        r = await s.execute(select(Demand).where(Demand.user_id == 'crawler').order_by(Demand.created_at.desc()))
        demands = list(r.scalars().all())
    
    english_demands = [d for d in demands if is_english(d.raw_text)]
    print(f"\n待翻译的英文需求: {len(english_demands)} 条")
    
    llm = get_llm()
    translated = 0
    
    for d in english_demands[:20]:  # 一次最多20条
        prompt = f"""将以下英文技术需求翻译为中文。要求：
1. 专业术语保留英文原文（如 GPU、API、Python）
2. 保持技术准确性
3. 不要添加额外解释

原文：
{d.raw_text[:800]}"""
        
        try:
            result = await llm.chat("你是一个专业的技术翻译。只输出翻译结果，不要加说明。", prompt)
            result = result.strip()
            if result:
                async with async_session() as s2:
                    d2 = await s2.get(Demand, d.id)
                    if d2:
                        d2.raw_text = result[:1000]
                        await s2.commit()
                        translated += 1
                        print(f"  ✅ [{translated}/{len(english_demands)}] {d.id[:8]}")
        except Exception as e:
            print(f"  ❌ {d.id[:8]}: {e}")
    
    print(f"翻译完成: {translated} 条")


async def main():
    print("=" * 50)
    print("需求数据清理脚本 — 第1步：删除GitHub Issues")
    print("=" * 50)
    
    deleted = await delete_github_issues()
    print(f"\n第1步完成，删除了 {len(deleted)} 条")
    
    print("\n第2步：统计待翻译的英文需求")
    async with async_session() as s:
        r = await s.execute(select(Demand).where(Demand.user_id == 'crawler'))
        remaining = list(r.scalars().all())
    english = [d for d in remaining if is_english(d.raw_text)]
    print(f"剩余 crawler 需求: {len(remaining)} 条")
    print(f"其中英文: {len(english)} 条")
    for d in english:
        print(f"  [{d.category}] {d.raw_text[:80]}...")

if __name__ == '__main__':
    asyncio.run(main())
