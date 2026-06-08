"""
需求爬取测试 — 试跑四个数据源，评估数据量。
不存入数据库，只统计数量+估算体积。
"""
import asyncio
import json
import sys
import os

sys.path.insert(0, os.path.abspath("."))

async def test_herox():
    """HeroX — 全球创新挑战"""
    try:
        import httpx
        import xml.etree.ElementTree as ET
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get("https://www.herox.com/challenges/rss")
            if resp.status_code != 200:
                print(f"  HeroX: HTTP {resp.status_code} — 不可访问")
                return 0, 0

            root = ET.fromstring(resp.text)
            items = root.findall(".//item")
            total_chars = 0
            for item in items:
                title = item.findtext("title", "")
                desc = item.findtext("description", "")
                total_chars += len(title) + len(desc)

            print(f"  HeroX: {len(items)} 条挑战, 总计 {total_chars:,} 字符, 约 {total_chars/1024:.0f} KB")
            return len(items), total_chars
    except Exception as e:
        print(f"  HeroX: 爬取失败 — {type(e).__name__}: {str(e)[:80]}")
        return 0, 0

async def test_github():
    """GitHub Issues — 功能需求"""
    try:
        import httpx
        async with httpx.AsyncClient(timeout=15) as client:
            # 搜索 "feature request" 标签的 issue
            resp = await client.get(
                "https://api.github.com/search/issues",
                params={"q": 'label:"feature request" is:open', "per_page": 10, "sort": "created"},
                headers={"Accept": "application/vnd.github.v3+json"}
            )
            if resp.status_code == 403:
                print(f"  GitHub: API 限流 — 需要认证Token")
                return 0, 0

            data = resp.json()
            total = data.get("total_count", 0)
            items = data.get("items", [])
            print(f"  GitHub Feature Requests: {total:,} 条 (本次获取{len(items)}条)")
            return total, 0
    except Exception as e:
        print(f"  GitHub: 爬取失败 — {type(e).__name__}: {str(e)[:80]}")
        return 0, 0

async def test_stackoverflow():
    """Stack Overflow — 技术求助"""
    try:
        import httpx
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                "https://api.stackexchange.com/2.3/questions",
                params={"order": "desc", "sort": "votes", "pagesize": 5, "site": "stackoverflow"}
            )
            if resp.status_code == 400:
                print(f"  Stack Overflow: API 需要重定向（但总体可用）")
                return 0, 0

            data = resp.json()
            items = data.get("items", [])
            # Stack Exchange 每月约 30万 新问题
            print(f"  Stack Overflow: 样本{len(items)}条, 全站月新增约30万条问题")
            return 300000, 0
    except Exception as e:
        print(f"  Stack Overflow: 爬取失败 — {type(e).__name__}: {str(e)[:80]}")
        return 0, 0

async def test_ccgp():
    """中国政府采购网"""
    try:
        # ccgp.gov.cn 需要特殊处理 — Phase 1 不直接爬HTML，用估计值
        print(f"  中国政府采购网: 日均新增约200-500条采购公告, 年约7-18万条")
        # 实际爬取需要 Crawl4AI
        return 100000, 0
    except Exception as e:
        return 0, 0

async def main():
    print("=" * 55)
    print("  需求链平台 — 公开需求数据量评估")
    print("=" * 55)

    results = {}
    total_demands = 0

    sources = [
        ("HeroX (创新挑战)", test_herox),
        ("GitHub (功能需求)", test_github),
        ("Stack Overflow (技术求助)", test_stackoverflow),
        ("中国政府采购网", test_ccgp),
    ]

    for name, fn in sources:
        print(f"\n  [{name}]")
        count, chars = await fn()
        results[name] = {"count": count, "chars": chars}
        total_demands += count

    print("\n" + "=" * 55)
    print(f"  总计: 约 {total_demands:,} 条需求/年")
    print()

    # 存储估算
    avg_chars_per_demand = 500  # 标题+描述约500字
    estimated_kb = (total_demands * avg_chars_per_demand) / 1024
    estimated_mb = estimated_kb / 1024
    estimated_gb = estimated_mb / 1024

    print(f"  存储估算（纯文本）:")
    print(f"    每条约 {avg_chars_per_demand} 字符")
    print(f"    总计约 {estimated_kb:,.0f} KB = {estimated_mb:.1f} MB")
    print(f"    加索引+分类标注后 ≈ {estimated_mb*3:.0f} MB")
    print(f"    加 pgvector 向量后 ≈ {estimated_mb*30:.0f} MB")
    print()

    server_disk = 40  # 阿里云 40GB
    estimated_total_mb = estimated_mb * 30  # 包含向量的存储
    usage_pct = (estimated_total_mb / (server_disk * 1024)) * 100

    print(f"  服务器磁盘: {server_disk} GB")
    print(f"  需求库占用量: {estimated_total_mb:.0f} MB ({usage_pct:.1f}% of {server_disk}GB)")
    print()
    if usage_pct < 10:
        print(f"  ✅ 结论: 空间充足。需求库仅占 {usage_pct:.1f}%，完全够用。")
    elif usage_pct < 30:
        print(f"  ⚠️ 结论: 空间够用但需要注意。占 {usage_pct:.1f}%。")
    else:
        print(f"  ❌ 结论: 空间紧张。需要扩展磁盘或做数据归档。")
    print("=" * 55)

if __name__ == "__main__":
    asyncio.run(main())
