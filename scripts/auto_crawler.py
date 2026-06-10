#!/usr/bin/env python3
"""
需求链平台 — 自动爬虫
Auto-crawler for real demands and suppliers from public sources.
Runs: python auto_crawler.py

Sources:
- USA.gov federal challenges (API)
- XPRIZE competitions (scrape)
- EU Horizon Europe calls (scrape)
- India BIRAC calls (scrape)
- Climate-KIC open calls

Classification uses keyword matching (no AI API needed).
"""

import hashlib
import json
import re
import time
import urllib.request
import urllib.parse
from datetime import datetime, timezone

# ============================================================
# Config
# ============================================================
API_BASE = "http://localhost:8080"
DB_CONN = "postgresql+asyncpg://dc:dc@localhost:5432/demand_chain"

# Category keyword mapping
CATEGORY_KEYWORDS = {
    "人工智能": ["ai", "artificial intelligence", "machine learning", "deep learning", "llm", "大模型", "神经网络", "automl", "computer vision", "自然语言", "nlp"],
    "生物医药": ["drug", "diagnostic", "biomedical", "medical", "clinical", "therapeutic", "vaccine", "基因", "药物", "诊断", "临床", "疗法", "pharmaceutical", "healthcare"],
    "新能源": ["solar", "photovoltaic", "wind energy", "hydrogen", "battery", "energy storage", "光伏", "风电", "氢能", "储能", "钙钛矿", "clean energy", "renewable"],
    "环境工程": ["carbon capture", "water treatment", "wastewater", "desalination", "recycling", "carbon removal", "碳捕集", "废水", "海水淡化", "climate", "emission", "sustainability"],
    "材料科学": ["material", "polymer", "composite", "nanomaterial", "coating", "alloy", "ceramic", "材料", "高分子", "复合材料", "涂层", "纳米"],
    "航空航天": ["aerospace", "satellite", "propulsion", "drone", "uav", "aviation", "航天", "卫星", "无人机", "推进", "航空"],
    "机器人与智能系统": ["robot", "autonomous", "uav", "drone", "robotics", "slam", "机器人", "自主导航", "无人系统", "agv"],
    "信息技术": ["blockchain", "quantum", "cybersecurity", "software", "platform", "digital", "区块链", "量子", "网络安全", "软件", "平台", "隐私计算"],
    "传感器技术": ["sensor", "detector", "mems", "lidar", "radar", "传感器", "检测", "陀螺", "惯性"],
    "农业科学": ["agriculture", "crop", "farming", "food", "soil", "农业", "作物", "养殖", "食品", "植物工厂"],
    "海洋科学": ["ocean", "marine", "seawater", "coral", "fishery", "海洋", "海水", "渔业", "珊瑚"],
    "安全科学": ["security", "surveillance", "fire", "safety", "protection", "安防", "消防", "安全", "防护"],
    "交通运输": ["transport", "logistics", "railway", "high-speed", "electric vehicle", "ev", "交通", "物流", "高铁", "电动车"],
    "化学工程": ["chemical", "catalyst", "synthesis", "ammonia", "化工", "催化剂", "合成", "反应器"],
    "核科学": ["nuclear", "reactor", "radiation", "核", "反应堆", "辐照"],
    "生物技术": ["biotech", "crispr", "gene", "genome", "synthetic biology", "生物技术", "基因编辑", "合成生物"],
    "电子科学与技术": ["semiconductor", "chip", "ic", "ga", "sic", "optoelectronic", "半导体", "芯片", "集成电路", "光电"],
    "土木工程": ["concrete", "construction", "building", "seismic", "土木", "建筑", "混凝土", "抗震"],
    "智慧城市": ["smart city", "urban", "iot", "智慧城市", "城市", "物联网"],
}

# Source configuration
SOURCES = {
    "usa_gov": {
        "enabled": True,
        "url": "https://www.usa.gov/find-active-challenge",
        "type": "demand",
    },
    "xprize": {
        "enabled": True,
        "url": "https://www.xprize.org/competitions",
        "type": "demand",
    },
    "climate_kic": {
        "enabled": True,
        "url": "https://www.climate-kic.org/get-involved/open-calls/",
        "type": "demand",
    },
}


def classify(text):
    """Classify a demand/supplier text into a category."""
    text_lower = text.lower()
    scores = {}
    for category, keywords in CATEGORY_KEYWORDS.items():
        score = 0
        for kw in keywords:
            if kw.lower() in text_lower:
                score += 1
        if score > 0:
            scores[category] = score
    if not scores:
        return "其他"
    return max(scores, key=scores.get)


def fetch_url(url, timeout=15):
    """Fetch a URL and return text content."""
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (compatible; DemandChainCrawler/1.0; +https://8.154.26.92:8080)",
            "Accept": "text/html,application/json,*/*",
        })
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"  [WARN] Failed to fetch {url}: {e}")
        return ""


def extract_demands_from_usa_gov(html):
    """Extract demands from USA.gov challenges page."""
    demands = []
    # Pattern: find challenge links and titles
    pattern = r'href="(/challenges/[^"]+)"[^>]*>([^<]+)</a>'
    for match in re.finditer(pattern, html):
        path = match.group(1)
        title = match.group(2).strip()
        url = "https://www.usa.gov" + path
        demands.append({
            "title": title,
            "source": "USA.gov",
            "url": url,
        })
    return demands


def extract_demands_from_xprize(html):
    """Extract demands from XPRIZE competitions page."""
    demands = []
    pattern = r'<a[^>]*href="(/competitions/[^"]+)"[^>]*>([^<]+)</a>'
    for match in re.finditer(pattern, html):
        path = match.group(1)
        title = match.group(2).strip()
        url = "https://www.xprize.org" + path
        if "competitions" in path:
            demands.append({
                "title": title,
                "source": "XPRIZE",
                "url": url,
            })
    return demands


def insert_demand(email, raw_text, category, source_url=""):
    """Insert a demand via the web API."""
    text = f"{raw_text} 来源：{source_url}" if source_url else raw_text
    data = json.dumps({
        "email": email,
        "raw_text": text,
        "category": classify(text) if category == "auto" else category,
        "status": "OPEN",
    }).encode("utf-8")
    try:
        req = urllib.request.Request(
            f"{API_BASE}/api/auto-demand",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read())
            print(f"  OK: {result}")
            return True
    except Exception as e:
        print(f"  [WARN] Insert failed: {e}")
        return False


def crawl_usa_gov():
    """Crawl USA.gov federal challenges."""
    print("\n--- USA.gov Federal Challenges ---")
    html = fetch_url(SOURCES["usa_gov"]["url"])
    if not html:
        return []
    demands = extract_demands_from_usa_gov(html)
    print(f"  Found {len(demands)} challenges")
    for d in demands:
        # Get detail page for full description
        detail_html = fetch_url(d["url"])
        # Extract description: look for text after the title
        desc_match = re.search(r'<p[^>]*>([^<]{50,300})</p>', detail_html)
        description = desc_match.group(1) if desc_match else d["title"]
        d["body"] = f"{d['title']}: {description}"
        d["category"] = classify(d["title"] + " " + description)
        print(f"  [{d['category']}] {d['title'][:50]}...")
    return demands


def crawl_xprize():
    """Crawl XPRIZE competitions."""
    print("\n--- XPRIZE Competitions ---")
    html = fetch_url(SOURCES["xprize"]["url"])
    if not html:
        return []
    demands = extract_demands_from_xprize(html)
    print(f"  Found {len(demands)} competitions")
    for d in demands:
        d["body"] = d["title"]
        d["category"] = classify(d["title"])
        print(f"  [{d['category']}] {d['title'][:50]}...")
    return demands


def seed_demands_to_db(demands):
    """Write demands to database directly."""
    import asyncio
    from sqlalchemy import select
    from src.shared.database import async_session
    from src.shared.models import Demand, DemandStatus
    from uuid import uuid4

    async def _do():
        async with async_session() as session:
            count = 0
            for d in demands:
                # Check if already exists
                result = await session.execute(select(Demand).where(Demand.raw_text.contains(d["title"][:30])))
                if result.scalar_one_or_none():
                    print(f"  SKIP: {d['title'][:30]}... (already exists)")
                    continue

                demand = Demand(
                    id=str(uuid4()),
                    user_id=d.get("source", "crawler").lower(),
                    raw_text=d["body"],
                    category=d["category"],
                    status=DemandStatus.OPEN,
                    visibility="PUBLIC",
                )
                session.add(demand)
                count += 1
            await session.commit()
            print(f"  Inserted {count} new demands")

    asyncio.run(_do())


def run():
    """Main entry point."""
    print(f"=== Demand Chain Auto-Crawler ===")
    print(f"Started at: {datetime.now(timezone.utc).isoformat()}")
    print()

    all_demands = []

    if SOURCES["usa_gov"]["enabled"]:
        try:
            all_demands.extend(crawl_usa_gov())
        except Exception as e:
            print(f"  [ERROR] USA.gov crawl failed: {e}")

    if SOURCES["xprize"]["enabled"]:
        try:
            all_demands.extend(crawl_xprize())
        except Exception as e:
            print(f"  [ERROR] XPRIZE crawl failed: {e}")

    print(f"\n=== Total demands collected: {len(all_demands)} ===")

    if all_demands:
        try:
            seed_demands_to_db(all_demands)
        except Exception as e:
            print(f"  [ERROR] DB seeding failed: {e}")

    print("\nDone.")


if __name__ == "__main__":
    run()
