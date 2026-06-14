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
API_BASE = "http://8.154.26.92:8080"

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
    # === 供应商 / 公司来源 ===
    "startus_ccus": {
        "enabled": True,
        "url": "https://www.startus-insights.com/innovators-guide/carbon-capture-utilization-storage-startups/",
        "type": "supplier",
        "extractor": "startus_ccus",
        "label": "碳捕集初创企业",
    },
    "energy_startups_hydrogen": {
        "enabled": True,
        "url": "https://www.energystartups.org/top/hydrogen-fuel/",
        "type": "supplier",
        "extractor": "energy_hydrogen",
        "label": "氢能初创企业",
    },
    "climate_tech_2026": {
        "enabled": True,
        "url": "https://www.rankred.com/climate-tech-startups/",
        "type": "supplier",
        "extractor": "rankred",
        "label": "气候科技初创企业2026",
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


# 要跳过的非需求链接关键词（导航、页脚、登录等）
NAV_SKIP_URL = [
    "#", "javascript", "login", "register", "mailto", "css", "js/",
    "signin", "signup", "logout", "account", "password", "forgot",
    "terms", "privacy", "cookie", "legal", "accessibility",
    "sitemap", "rss", "feed", "search", "contact", "about",
    "careers", "press", "newsroom", "media", "investor",
    "facebook", "twitter", "linkedin", "youtube", "instagram",
    "share", "print", "pdf", "download", "upload",
    "branches-of-government", "agency-index", "phone", "usagov-outreach",
    "feature-articles", "website-usage", "partner-with-us",
    "report-website", "usa.gov/es", "executive-branch",
    "federal-agency", "governors", "tribal-governments",
    "elected-officials", "departments", "budget",
]

NAV_SKIP_TITLE = [
    "create an account", "terms of service", "privacy policy",
    "accessibility", "become a ", "meet the ", "sign in",
    "login", "register", "copyright", "all rights reserved",
    "powered by", "website usage", "report a website",
    "partner with us", "branches of government", "directory of",
    "feature articles", "follow us", "subscribe", "newsletter",
    "grand challenges", "areas of impact",
    # USA.gov / NSFC 等站点特有的导航链接
    "usagov", "1-844", "call us at", "all topics and services",
    "about the u.s.", "government agencies", "state government",
    "local government", "tribal government", "elected official",
    "federal agency", "site policies", "budget and performance",
    "the white house", "u.s. house", "u.s. senate",
    "federal register", "regulations", "constitution",
    "appendix", "annual report", "synthesis evidence",
    "international evaluation", "leadership", "at a glance",
    "guide to programs", "application and review",
    "faq", "glossary", "disclaimer", "site map",
    "freedom of information", "foia", "no fear act",
    "inspector general", "the office of",
    "get.agorize", "powered by agorize",
    "about this site", "using this site",
    "agree to support", "icfcrt",
]

DEMAND_KEYWORDS = [
    "challenge", "competition", "prize", "grant", "funding",
    "solicitation", "request for proposal", "rfp", "call for",
    "open call", "accelerator", "incubator", "fellowship",
    "innovation", "research", "development", "prototype",
    "solution", "solve", "hackathon", "bootcamp", "award",
    "opportunity", "proposal", "submission", "deadline",
]


def extract_generic_links(html, base_url, source_label):
    """Extract links with anchor text from any page, filtering out navigation and footer.
    NOW WITH DEMAND FILTERING: only keep links whose title contains demand/pitch keywords."""
    demands = []
    pattern = r'href="([^"]+)"[^>]*>([^<]{15,200})</a>'
    for match in re.finditer(pattern, html):
        path = match.group(1)
        title = match.group(2).strip()

        # Skip navigation / footer URLs
        if any(skip in path.lower() for skip in NAV_SKIP_URL):
            continue
        # Skip navigation / footer titles
        title_lower = title.lower()
        if any(skip in title_lower for skip in NAV_SKIP_TITLE):
            continue
        # Skip if title looks like a URL
        if title_lower.startswith("http") or title_lower.startswith("www."):
            continue
        # Skip single word or very short titles
        if len(title) < 18:
            continue
        # Skip if no meaningful content words
        words = title.split()
        if len(words) < 3:
            continue

        # ONLY keep items that contain demand-relevant keywords
        has_demand_kw = any(kw in title_lower for kw in DEMAND_KEYWORDS)
        if not has_demand_kw:
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
    # Supplier extractors
    "startus_ccus": lambda html, src: extract_suppliers_startus(html, src),
    "rankred": lambda html, src: extract_suppliers_rankred(html, src),
    "energy_hydrogen": lambda html, src: extract_suppliers_energy_hydrogen(html, src),
}

# ============================================================
# XPRIZE-specific extractor
# ============================================================

def extract_demands_from_xprize(html):
    """Extract competition titles from XPRIZE page."""
    demands = []
    # Look for competition/prize names in h2/h3 tags
    headings = re.findall(r'<h[23][^>]*>(?:<[^>]+>\s*)*([A-Z][A-Za-z0-9 /\-]{5,80})</h[23]>', html)
    if not headings:
        # Try anchor text patterns
        headings = re.findall(r'>([A-Z][A-Za-z0-9 /\-]{10,80})</a>', html)
    for title in headings:
        title = title.strip()
        if any(kw in title.lower() for kw in ["prize", "challenge", "competition", "xpize", "award"]) or len(title) > 15:
            demands.append({"title": title, "source": "XPRIZE竞赛", "url": "https://www.xprize.org/competitions", "body": title})
    return demands


CRAWL_SPECIAL = {}


# ============================================================
# Supplier Crawlers
# ============================================================

def extract_suppliers_startus(html, src_key):
    """Extract supplier companies from StartUs Insights lists."""
    suppliers = []
    
    # Pattern 1: <hX><strong>Name</strong></hX><p>Description</p>
    companies = re.findall(r'<h\d[^>]*>(?:<[^>]+>\s*)*([A-Z][A-Za-z0-9\s&.-]{3,60})(?:\s*<[^>]+>\s*)*</h\d>(?:\s*<(?:p|div)[^>]*>\s*([^<]{20,400}?)\s*</(?:p|div)>)', html, re.DOTALL)
    
    # Pattern 2: <strong>Name</strong> followed by a paragraph
    if not companies:
        companies = re.findall(r'<strong[^>]*>([A-Z][A-Za-z0-9\s&.-]{3,60})</strong>(?:\s*</[^>]+>)?\s*<p[^>]*>([^<]+)</p>', html)
    
    # Pattern 3: JSON-LD structured data
    if not companies:
        json_blocks = re.findall(r'<script type="application/ld\+json">({.*?})</script>', html, re.DOTALL)
        for block in json_blocks:
            try:
                data = json.loads(block)
                items = []
                if isinstance(data, dict):
                    items = data.get("itemListElement", data.get("@graph", []))
                elif isinstance(data, list):
                    items = data
                for item in items:
                    name = ""
                    if isinstance(item, dict):
                        name = item.get("item", {}).get("name", "") or item.get("name", "")
                        desc = item.get("item", {}).get("description", "") or item.get("description", "")
                    if name and len(name) > 2:
                        suppliers.append({"name": name.strip(), "description": desc.strip(), "source": SOURCES[src_key]["label"]})
            except:
                pass
        if suppliers:
            return suppliers
    
    # Pattern 4: Look for company-like text in list items
    if not companies:
        companies = re.findall(r'<li[^>]*>([A-Z][A-Za-z0-9\s&.-]{3,60})</li>', html)
        companies = [(c, "") for c in companies]
    
    # Pattern 5: YAML/JSON embedded fallback
    if not companies:
        return fallback_json_extract(html, src_key)
    
    for name, desc in companies:
        name = name.strip()
        if len(name) > 2 and len(name) < 100:
            # Skip non-company phrases
            if any(skip in name.lower() for skip in ["top ", "market ", "list of", "category", "country"]):
                continue
            suppliers.append({"name": name, "description": desc.strip()[:300], "source": SOURCES[src_key]["label"]})
    return suppliers

def extract_suppliers_rankred(html, src_key):
    """Extract supplier companies from RankRed list articles."""
    suppliers = []
    # Pattern 1: "1. Company Name" in headings
    headings = re.findall(r'<h\d[^>]*>(\d+)\.?\s*([A-Z][A-Za-z0-9\s&.,-]{3,80})</h\d>', html)
    if not headings:
        # Pattern 2: "Company Name" in <strong> inside numbered sections
        headings = re.findall(r'<strong[^>]*>\d+\.?\s*([A-Z][A-Za-z0-9\s&.,-]{3,80})</strong>', html)
    if not headings:
        # Pattern 3: Any heading with a company-like name (capitalized, 2+ words)
        headings = re.findall(r'<h[23][^>]*>([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)</h[23]>', html)
        headings = [(h,) for h in headings]
    for match in headings:
        name = match[-1].strip()
        if len(name) > 3 and len(name) < 100:
            if not any(skip in name.lower() for skip in ["privacy", "terms", "cookie", "contact", "about", "top ", "list of"]):
                suppliers.append({"name": name, "description": "", "source": SOURCES[src_key]["label"]})
    return suppliers


def extract_suppliers_energy_hydrogen(html, src_key):
    """Extract hydrogen startup companies from EnergyStartups page."""
    suppliers = set()
    # Pattern: company names in link text
    links = re.findall(r'<a[^>]*href="[^"]*"[^>]*>([A-Z][A-Za-z0-9\s&.-]{3,60})</a>', html)
    for name in links:
        name = name.strip()
        name_lower = name.lower()
        if any(skip in name_lower for skip in [
            "startups in", "market ", "top 1", "list of", "category",
            "privacy", "terms ", "sign ", "login", "home", "about",
            "contact", "blog", "search", "submit",
        ]):
            continue
        if len(name) > 2 and len(name) < 80:
            suppliers.add(name)
    return [{"name": n, "description": "", "source": SOURCES[src_key]["label"]} for n in suppliers]


def fallback_json_extract(html, src_key):
    """Try to extract company data from JSON-LD or embedded JSON."""
    suppliers = []
    patterns = [
        r'"company_name"\s*:\s*"([^"]+)"\s*,\s*"description"\s*:\s*"([^"]+)"',
        r'"name"\s*:\s*"([^"]+)"\s*,\s*"description"\s*:\s*"([^"]+)"',
    ]
    for pat in patterns:
        matches = re.findall(pat, html)
        for name, desc in matches:
            suppliers.append({"name": name, "description": desc, "source": SOURCES[src_key]["label"]})
        if suppliers:
            break
    return suppliers


def crawl_supplier_source(src_key):
    """Crawl a supplier source and collect profiles."""
    src = SOURCES[src_key]
    label = src.get("label", src_key)
    print(f"\n--- [供应商] {label} ---")
    
    html = fetch_url(src["url"])
    if not html:
        return []
    
    extractor_key = src.get("extractor", "generic_links")
    extractor = EXTRACTORS.get(extractor_key)
    if not extractor:
        print(f"  [WARN] No extractor for {extractor_key}")
        return []
    
    suppliers = extractor(html, src_key)
    print(f"  Found {len(suppliers)} companies")
    
    for s in suppliers:
        # Normalize: generic_links returns 'title', supplier extractors return 'name'
        if "title" in s and "name" not in s:
            s["name"] = s.pop("title")
        s["category"] = classify(s.get("description", "") + " " + s.get("name", ""))
        print(f"  [{s['category']}] {s['name'][:40]}...")
    
    return suppliers


def seed_suppliers_to_db(suppliers):
    """Send suppliers to the server via HTTP API."""
    count_ok = 0
    count_skip = 0
    count_fail = 0
    for s in suppliers:
        payload = json.dumps({
            "email": "crawler",
            "profile_type": "COMPANY",
            "country": "",
            "trust_score": 0.5,
            "agent_card": {
                "name": s.get("name", ""),
                "description": s.get("description", ""),
                "category": s.get("category", "其他"),
                "industry": s.get("category", "其他"),
                "discipline": "",
                "trl": 0,
                "url": s.get("url", ""),
                "skills": [],
            },
        }).encode("utf-8")
        try:
            req = urllib.request.Request(
                f"{API_BASE}/api/auto-supplier",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status in (200, 201):
                    count_ok += 1
                    print(f"  OK: {s.get('name', '')[:40]}...")
                else:
                    print(f"  STATUS {resp.status}: {s.get('name', '')[:40]}...")
        except urllib.error.HTTPError as e:
            if e.code == 409:
                count_skip += 1
                print(f"  SKIP (dup): {s.get('name', '')[:40]}...")
            else:
                count_fail += 1
                print(f"  FAIL {e.code}: {s.get('name', '')[:40]}...")
        except Exception as e:
            count_fail += 1
            print(f"  ERROR: {s.get('name', '')[:30]}... -> {e}")
    print(f"  Results: {count_ok} inserted, {count_skip} skipped (dup), {count_fail} failed")


def seed_demands_to_db(demands):
    """Send demands to the server via HTTP API."""
    count_ok = 0
    count_skip = 0
    count_fail = 0
    for d in demands:
        payload = json.dumps({
            "raw_text": d.get("body", d.get("title", "")),
            "category": d.get("category", "其他"),
            "email": "crawler",
        }).encode("utf-8")
        try:
            req = urllib.request.Request(
                f"{API_BASE}/api/auto-demand",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status in (200, 201):
                    count_ok += 1
                    print(f"  OK: {d.get('title', '')[:40]}...")
                else:
                    print(f"  STATUS {resp.status}: {d.get('title', '')[:40]}...")
        except urllib.error.HTTPError as e:
            if e.code == 409:
                count_skip += 1
                print(f"  SKIP (dup): {d.get('title', '')[:40]}...")
            else:
                count_fail += 1
                print(f"  FAIL {e.code}: {d.get('title', '')[:40]}...")
        except Exception as e:
            count_fail += 1
            print(f"  ERROR: {d.get('title', '')[:30]}... -> {e}")
    print(f"  Results: {count_ok} inserted, {count_skip} skipped (dup), {count_fail} failed")


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
    all_suppliers = []

    for src_key in list(SOURCES.keys()):
        try:
            src_type = SOURCES[src_key].get("type", "demand")
            if src_type == "supplier":
                items = crawl_supplier_source(src_key)
                all_suppliers.extend(items)
            else:
                items = crawl_source(src_key)
                all_demands.extend(items)
        except Exception as e:
            print(f"  [ERROR] {src_key} crawl failed: {e}")
            import traceback; traceback.print_exc()

    print(f"\n=== Summary ===")
    print(f"  Demands collected: {len(all_demands)}")
    print(f"  Suppliers collected: {len(all_suppliers)}")

    if all_demands:
        try:
            seed_demands_to_db(all_demands)
        except Exception as e:
            print(f"  [ERROR] DB seeding failed: {e}")

    if all_suppliers:
        try:
            seed_suppliers_to_db(all_suppliers)
        except Exception as e:
            print(f"  [ERROR] Supplier DB seeding failed: {e}")

    # Save JSON backup
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if all_demands:
        demands_file = f"crawled_demands_{timestamp}.json"
        with open(demands_file, "w", encoding="utf-8") as f:
            json.dump(all_demands, f, ensure_ascii=False, indent=2)
        print(f"  Demands saved to: {demands_file}")
    if all_suppliers:
        suppliers_file = f"crawled_suppliers_{timestamp}.json"
        with open(suppliers_file, "w", encoding="utf-8") as f:
            json.dump(all_suppliers, f, ensure_ascii=False, indent=2)
        print(f"  Suppliers saved to: {suppliers_file}")

    print("\nDone.")


if __name__ == "__main__":
    run()
