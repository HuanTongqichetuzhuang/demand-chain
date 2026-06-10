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

# Source configuration — 可扩展，只需加 URL 和提取器
SOURCES = {
    "usa_gov": {
        "enabled": True,
        "url": "https://www.usa.gov/find-active-challenge",
        "type": "demand",
        "extractor": "generic_links",
        "label": "USA.gov联邦挑战",
    },
    "xprize": {
        "enabled": True,
        "url": "https://www.xprize.org/competitions",
        "type": "demand",
        "extractor": "xprize",
        "label": "XPRIZE竞赛",
    },
    "nasa": {
        "enabled": True,
        "url": "https://www.nasa.gov/prizes-challenges-and-crowdsourcing/",
        "type": "demand",
        "extractor": "generic_links",
        "label": "NASA挑战",
    },
    "mit_solve": {
        "enabled": True,
        "url": "https://solve.mit.edu/challenges",
        "type": "demand",
        "extractor": "generic_links",
        "label": "MIT Solve",
    },
    "darpa": {
        "enabled": True,
        "url": "https://www.darpa.mil/",
        "type": "demand",
        "extractor": "darpa",
        "label": "DARPA",
    },
    "aerospace_sg": {
        "enabled": True,
        "url": "https://open.innovation-challenge.sg/en/challenges/aerospace-open-innovation-challenge-2026",
        "type": "demand",
        "extractor": "generic_links",
        "label": "新加坡航空航天挑战",
    },
    "climate_kic": {
        "enabled": True,
        "url": "https://www.climate-kic.org/get-involved/open-calls/",
        "type": "demand",
        "extractor": "generic_links",
        "label": "Climate-KIC",
    },
    "nsfc": {
        "enabled": True,
        "url": "https://www.nsfc.gov.cn/english/site_1/international/D6/2026/01-20/501.html",
        "type": "demand",
        "extractor": "generic_links",
        "label": "国家自然科学基金委",
    },
    "grants_gov": {
        "enabled": True,
        "url": "https://simpler.grants.gov/search",
        "type": "demand",
        "extractor": "grant_search",
        "label": "Grants.gov美国联邦资助",
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


def extract_generic_links(html, base_url, source_label):
    """Extract links with anchor text from any page."""
    demands = []
    pattern = r'href="([^"]+)"[^>]*>([^<]{10,200})</a>'
    for match in re.finditer(pattern, html):
        path = match.group(1)
        title = match.group(2).strip()
        # Skip navigation, footer, and other non-content links
        if any(skip in path for skip in ["#", "javascript", "login", "register", "mailto", "css", "js/"]):
            continue
        # Skip short/category links
        if len(title) < 15:
            continue
        # Build absolute URL
        if path.startswith("http"):
            url = path
        elif path.startswith("/"):
            from urllib.parse import urlparse
            parsed = urlparse(base_url)
            url = f"{parsed.scheme}://{parsed.netloc}{path}"
        else:
            url = base_url.rstrip("/") + "/" + path.lstrip("/")
        demands.append({"title": title, "source": source_label, "url": url, "body": title})
    return demands


def extract_demands_from_darpa(html):
    """Extract demands from DARPA main page."""
    demands = []
    # Look for program/challenge descriptions
    sections = re.findall(r'>([A-Z ]{10,100})</[^>]+>[^<]*([A-Z][a-z].{20,200})', html)
    for title, desc in sections[:15]:
        if any(kw in title.lower() for kw in ["program", "challenge", "initiative"]):
            demands.append({"title": title.strip(), "source": "DARPA", "url": "https://www.darpa.mil/", "body": f"{title.strip()}: {desc.strip()}"})
    return demands


def extract_demands_from_grant_search(html):
    """Extract demands from Grants.gov search results."""
    demands = []
    pattern = r'<a[^>]*href="[^"]*opportunity[^"]*"[^>]*>([^<]+)</a>'
    for match in re.finditer(pattern, html):
        title = match.group(1).strip()
        if len(title) > 20:
            demands.append({"title": title, "source": "Grants.gov", "url": "https://simpler.grants.gov/search", "body": title})
    return demands


EXTRACTORS = {
    "generic_links": lambda html, src: extract_generic_links(html, SOURCES[src]["url"], SOURCES[src]["label"]),
    "xprize": lambda html, src: extract_demands_from_xprize(html),
    "darpa": lambda html, src: extract_demands_from_darpa(html),
    "grant_search": lambda html, src: extract_demands_from_grant_search(html),
}

CRAWL_SPECIAL = {
    "usa_gov": crawl_usa_gov,
    "xprize": crawl_xprize,
}


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


def crawl_source(src_key):
    """Crawl a single source by key. Uses special crawler if available, else generic extractor."""
    src = SOURCES[src_key]
    if not src.get("enabled", True):
        print(f"  SKIP: {src_key} (disabled)")
        return []
    
    label = src.get("label", src_key)
    print(f"\n--- {label} ---")
    
    # Use special crawler if defined
    if src_key in CRAWL_SPECIAL:
        return CRAWL_SPECIAL[src_key]()
    
    # Generic extraction
    html = fetch_url(src["url"])
    if not html:
        return []
    
    extractor_key = src.get("extractor", "generic_links")
    extractor = EXTRACTORS.get(extractor_key)
    if not extractor:
        print(f"  [WARN] No extractor for {extractor_key}")
        return []
    
    demands = extractor(html, src_key)
    print(f"  Found {len(demands)} items")
    
    for d in demands:
        d["category"] = classify(d.get("body", "") or d.get("title", ""))
        print(f"  [{d['category']}] {d['title'][:50]}...")
    
    return demands


def run():
    """Main entry point."""
    print(f"=== Demand Chain Auto-Crawler ===")
    print(f"Started at: {datetime.now(timezone.utc).isoformat()}")
    print()

    all_demands = []
    source_keys = list(SOURCES.keys())

    for src_key in source_keys:
        try:
            demands = crawl_source(src_key)
            all_demands.extend(demands)
        except Exception as e:
            print(f"  [ERROR] {src_key} crawl failed: {e}")
            import traceback; traceback.print_exc()

    print(f"\n=== Total demands collected: {len(all_demands)} ===")

    if all_demands:
        try:
            seed_demands_to_db(all_demands)
        except Exception as e:
            print(f"  [ERROR] DB seeding failed: {e}")

    print("\nDone.")


if __name__ == "__main__":
    run()
