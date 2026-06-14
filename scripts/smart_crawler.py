#!/usr/bin/env python3
"""
需求链平台 — 智能爬虫 v2
使用 Firecrawl API 搜索全网真实需求公告 + DeepSeek AI 筛选。
替代旧的 auto_crawler.py（那个抓导航链接太多垃圾了）。

核心改进：
1. Firecrawl 全网搜索，不再抓网站导航链接
2. DeepSeek AI 判断是不是真实需求，提取结构化信息
3. 每个搜索结果都先 AI 过滤，非需求直接丢弃
4. 入库前做 fingerprint 去重

用法:
  python scripts/smart_crawler.py           # 跑一次
  python scripts/smart_crawler.py --dry-run # 试跑，不入库
"""
import hashlib
import json
import re
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime

# ============================================================
# Config
# ============================================================
API_BASE = "http://8.154.26.92:8080"
FIRECRAWL_KEY = "fc-e97094049296412bb87cc3946d515649"
DEEPSEEK_KEY = "sk-c32415bb5ae44cdc844f1b95f99e4544"

# ============================================================
# AI 筛选 Prompt
# ============================================================
DEMAND_PROMPT = """判断以下文本是否是一条真实的技术需求/竞赛/招标/项目征集。输出 JSON:

如果是真实需求:
{"is_demand":true,"title":"中文标题","summary":"100字内中文摘要","category":"分类","tags":["标签"],"deadline":"截止日期或未知","prize":"奖金或未知","org":"发布机构"}

如果不是:
{"is_demand":false,"reason":"原因"}

分类选项: 人工智能|生物医药|新能源|环境工程|材料科学|航空航天|机器人与智能系统|信息技术|传感器技术|农业科学|海洋科学|安全科学|交通运输|化学工程|核科学|生物技术|电子科学与技术|土木工程|其他

规则:
- 新闻通报、政策说明、导航链接不是需求
- 真实需求有: 具体技术指标、奖金金额、截止日期、申请链接等
- 输出纯JSON，无其他文字"""

# ============================================================
# 搜索词 — 针对各来源找真实需求页面
# ============================================================
DEMAND_QUERIES = [
    # 美国政府挑战赛 — challenge.gov 关了，直接搜各站点
    'site:grants.gov "grant" "deadline" 2026',
    'site:sam.gov "solicitation" "proposal" 2026',
    'site:sbir.gov "solicitation" "topic" 2026',
    # XPRIZE
    'site:xprize.org competition water OR carbon OR health OR quantum 2026',
    # DARPA
    'site:darpa.mil "solicitation" OR "broad agency announcement" 2026',
    # NASA
    'site:nasa.gov "prize" OR "challenge" OR "competition" 2026',
    # EU Horizon
    'site:ec.europa.eu "horizon europe" "call" "deadline" 2026',
    # 中国项目申报
    'site:gov.cn "揭榜挂帅" OR "项目申报" OR "技术需求" 2026',
    'site:nsfc.gov.cn "项目指南" OR "申请通告" 2026',
    # 全球创新挑战
    'site:herox.com challenge prize 2026',
    'site:innocentive.com challenge 2026',
    'site:climate-kic.org "open call" 2026',
    'site:solve.mit.edu challenge 2026',
]

SUPPLIER_QUERIES = [
    'site:startus-insights.com carbon capture startup company 2026',
    'site:energystartups.org hydrogen OR energy OR climate startup',
    'site:rankred.com climate tech OR energy OR biotech startup company',
    'site:crunchbase.com "carbon capture" OR "clean energy" OR "biotech" company',
]

# ============================================================
# HTTP 工具
# ============================================================
def http_post(url, payload, headers=None, timeout=30):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers or {}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def firecrawl_search(query, limit=3):
    """Firecrawl 全网搜索"""
    try:
        result = http_post(
            "https://api.firecrawl.dev/v1/search",
            {"query": query, "limit": min(limit, 5),
             "scrapeOptions": {"formats": ["markdown"], "onlyMainContent": True}},
            {"Authorization": f"Bearer {FIRECRAWL_KEY}", "Content-Type": "application/json"},
        )
        if result.get("success"):
            return [{"url": i.get("url",""), "title": i.get("title",""),
                     "content": (i.get("markdown","") or i.get("description",""))[:2000]}
                    for i in result.get("data", [])]
    except Exception as e:
        print(f"  Firecrawl search error: {e}")
    return []


def firecrawl_scrape(url):
    """抓取单页"""
    try:
        result = http_post(
            "https://api.firecrawl.dev/v1/scrape",
            {"url": url, "formats": ["markdown"], "onlyMainContent": True},
            {"Authorization": f"Bearer {FIRECRAWL_KEY}", "Content-Type": "application/json"},
        )
        if result.get("success"):
            d = result.get("data", {})
            return {"url": url, "title": (d.get("metadata",{}) or {}).get("title",""),
                    "content": d.get("markdown","")[:3000]}
    except Exception as e:
        print(f"  Firecrawl scrape error: {e}")
    return {"url": url, "title": "", "content": ""}


def deepseek_filter(text):
    """DeepSeek 判断是否真实需求"""
    try:
        result = http_post(
            "https://api.deepseek.com/v1/chat/completions",
            {"model": "deepseek-chat", "messages": [
                {"role": "system", "content": DEMAND_PROMPT},
                {"role": "user", "content": text[:3000]},
            ], "temperature": 0.1, "max_tokens": 512},
            {"Authorization": f"Bearer {DEEPSEEK_KEY}", "Content-Type": "application/json"},
        )
        content = result["choices"][0]["message"]["content"].strip()
        content = content[content.find("{"):content.rfind("}")+1] if "{" in content else content
        return json.loads(content)
    except Exception as e:
        return {"is_demand": None, "reason": str(e)}


def fingerprint(text):
    return hashlib.md5(text.encode("utf-8", errors="replace")).hexdigest()[:12]


# ============================================================
# API 入库
# ============================================================
def api_post(path, payload):
    data = json.dumps(payload).encode("utf-8")
    try:
        req = urllib.request.Request(f"{API_BASE}{path}", data=data,
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return {"status": "error", "code": e.code}
    except Exception as e:
        return {"status": "error", "reason": str(e)}


def insert_demand(d):
    return api_post("/api/auto-demand", {
        "raw_text": f"{d['title']}: {d.get('summary','')}\n来源: {d.get('org','未知')}, 奖金: {d.get('prize','未知')}, 截止: {d.get('deadline','未知')}",
        "category": d.get("category", "其他"),
        "email": "crawler",
    })


def insert_supplier(s):
    return api_post("/api/auto-supplier", {
        "email": "crawler",
        "profile_type": s.get("profile_type", "COMPANY"),
        "country": s.get("country", "中国"),
        "trust_score": s.get("trust_score", 0.5),
        "agent_card": {
            "name": s["name"],
            "description": s.get("description", ""),
            "category": s.get("category", "其他"),
            "industry": s.get("industry", ""),
            "discipline": s.get("discipline", ""),
            "trl": s.get("trl", 0),
            "url": s.get("url", ""),
            "skills": s.get("skills", []),
        },
    })


# ============================================================
# 爬虫主流程
# ============================================================
class CrawlerStats:
    def __init__(self):
        self.demand_ok = 0; self.demand_dup = 0; self.demand_fail = 0
        self.supplier_ok = 0; self.supplier_dup = 0; self.supplier_fail = 0


def crawl_demands(dry_run=False):
    stats = CrawlerStats()
    print("\n" + "=" * 60)
    print("Phase 1: Search + AI filter real demands")
    print("=" * 60)

    seen = set()
    candidates = []

    for q in DEMAND_QUERIES:
        print(f"\n  Search: {q[:80]}...")
        items = firecrawl_search(q, limit=3)
        print(f"    => {len(items)} results")
        for item in items:
            fp = fingerprint(item["url"])
            if fp not in seen:
                seen.add(fp)
                candidates.append(item)
        time.sleep(2)

    print(f"\n  Deduped: {len(candidates)} unique candidates\n")

    # AI filter
    real = []
    for i, c in enumerate(candidates):
        text = f"TITLE: {c['title']}\n\nCONTENT: {c['content']}"
        if len(text.strip()) < 60:
            continue
        sys.stdout.write(f"  [{i+1}/{len(candidates)}] {c['title'][:60]}... ")
        sys.stdout.flush()

        result = deepseek_filter(text)
        if result.get("is_demand"):
            result["url"] = c["url"]
            real.append(result)
            print(f"YES [{result.get('category','?')}]")
        elif result.get("is_demand") is False:
            print(f"NO {result.get('reason','')[:40]}")
        else:
            # 重试：深抓页面内容
            print("retry scrape...")
            page = firecrawl_scrape(c["url"])
            if page.get("content"):
                text2 = f"TITLE: {page['title']}\n\nCONTENT: {page['content'][:3000]}"
                result2 = deepseek_filter(text2)
                if result2.get("is_demand"):
                    result2["url"] = c["url"]
                    real.append(result2)
                    print(f"    YES [{result2.get('category','?')}]")
                else:
                    print(f"    NO")
        time.sleep(1)

    print(f"\n  AI confirmed: {len(real)} real demands\n")

    # Insert
    for d in real:
        r = insert_demand(d)
        status = r.get("status", "error")
        if status == "ok":
            stats.demand_ok += 1
            print(f"  OK: {d['title'][:60]}")
        elif status == "dup":
            stats.demand_dup += 1
        else:
            stats.demand_fail += 1
            print(f"  FAIL: {r}")

    return stats


def crawl_suppliers(dry_run=False):
    stats = CrawlerStats()
    print("\n" + "=" * 60)
    print("Phase 2: Supplier search")
    print("=" * 60)

    seen = set()
    for q in SUPPLIER_QUERIES:
        print(f"\n  Search: {q[:80]}...")
        items = firecrawl_search(q, limit=3)
        print(f"    => {len(items)} results")
        for item in items:
            fp = fingerprint(item["url"])
            if fp in seen:
                continue
            seen.add(fp)
            # Build supplier from search result
            name = item.get("title", "")[:80]
            desc = item.get("content", "")[:300]
            if not name or len(name) < 3:
                continue
            s = {
                "name": name,
                "description": desc,
                "url": item.get("url", ""),
                "category": classify(desc + " " + name),
                "industry": "",
                "discipline": "",
                "skills": [],
                "country": "",
                "profile_type": "COMPANY",
                "trust_score": 0.4,
            }
            r = insert_supplier(s)
            status = r.get("status", "error")
            if status == "ok":
                stats.supplier_ok += 1
                print(f"  OK: [{s['category']}] {name[:50]}")
            elif status == "dup":
                stats.supplier_dup += 1
            else:
                stats.supplier_fail += 1
        time.sleep(2)

    return stats


# ============================================================
# 简单分类（复用旧爬虫的分类逻辑）
# ============================================================
CATEGORY_KEYWORDS = {
    "人工智能": ["ai", "machine learning", "deep learning", "llm", "大模型"],
    "生物医药": ["drug", "diagnostic", "biomedical", "medical", "vaccine"],
    "新能源": ["solar", "hydrogen", "battery", "energy storage", "光伏", "储能"],
    "环境工程": ["carbon capture", "water treatment", "climate", "碳捕集"],
    "材料科学": ["material", "polymer", "composite", "nanomaterial", "材料"],
    "航空航天": ["aerospace", "satellite", "propulsion", "drone", "航天"],
    "机器人与智能系统": ["robot", "autonomous", "robotics", "机器人"],
    "信息技术": ["blockchain", "quantum", "cybersecurity", "software"],
    "传感器技术": ["sensor", "detector", "mems", "传感器"],
    "农业科学": ["agriculture", "crop", "farming", "农业"],
    "海洋科学": ["ocean", "marine", "海水"],
    "安全科学": ["security", "safety", "protection", "安全"],
    "交通运输": ["transport", "logistics", "electric vehicle", "交通"],
    "化学工程": ["chemical", "catalyst", "synthesis", "化工"],
    "核科学": ["nuclear", "reactor", "radiation"],
    "生物技术": ["biotech", "crispr", "gene", "合成生物"],
    "电子科学与技术": ["semiconductor", "chip", "ic", "半导体"],
    "土木工程": ["concrete", "construction", "土木"],
}


def classify(text):
    text_lower = text.lower()
    scores = {}
    for cat, kws in CATEGORY_KEYWORDS.items():
        s = sum(1 for kw in kws if kw.lower() in text_lower)
        if s > 0:
            scores[cat] = s
    return max(scores, key=scores.get) if scores else "其他"


# ============================================================
# 保存备份
# ============================================================
def save_backup(name, data):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    fname = f"{name}_{ts}.json"
    with open(fname, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  Backup: {fname}")


# ============================================================
# Main
# ============================================================
def run(dry_run=False):
    print(f"=== Smart Crawler v2 ===")
    print(f"Started: {datetime.now().isoformat()}")
    print(f"Strategy: Firecrawl search -> DeepSeek AI filter\n")

    ds = crawl_demands(dry_run)
    ss = crawl_suppliers(dry_run)

    print(f"\n{'=' * 60}")
    print(f"Summary:")
    print(f"  Demands:   {ds.demand_ok} new, {ds.demand_dup} dup, {ds.demand_fail} fail")
    print(f"  Suppliers: {ss.supplier_ok} new, {ss.supplier_dup} dup, {ss.supplier_fail} fail")
    print(f"Done.")


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    run(dry_run=dry)
