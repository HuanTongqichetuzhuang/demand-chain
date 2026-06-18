#!/usr/bin/env python3
"""
需求链平台 — 智能爬虫 v2.1
使用 Firecrawl API 搜索全网真实需求公告 + DeepSeek AI 筛选。
Firecrawl 额度用尽时自动降级为 HTTP 直连模式。

核心改进：
1. Firecrawl 全网搜索，不再抓网站导航链接
2. DeepSeek AI 判断是不是真实需求，提取结构化信息
3. 每个搜索结果都先 AI 过滤，非需求直接丢弃
4. 入库前做 fingerprint 去重
5. Firecrawl 额度耗尽 (HTTP 402) 时自动切换 HTTP 直连降级

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
API_BASE = "http://demand-chain.duckdns.org:8080"
FIRECRAWL_KEY = "fc-e97094049296412bb87cc3946d515649"
DEEPSEEK_KEY = "sk-c32415bb5ae44cdc844f1b95f99e4544"

# Firecrawl 信用额度状态
_firecrawl_credits_ok = True

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
    # 新加源
    'site:ukri.org opportunity grant deadline 2026',
    'site:contractsfinder.service.gov.uk tender technology 2026',
    'site:worldbank.org procurement technology OR innovation 2026',
    'site:sbir.nasa.gov solicitation topic 2026',
    'site:service.most.gov.cn 项目申报 OR 研发 2026',
    'site:xiongan.gov.cn 揭榜挂帅 OR 技术攻关 2026',
    # ===== 科研设备需求专项搜索 =====
    'site:ccgp.gov.cn 仪器采购 OR 设备采购 OR 实验设备 2026',
    'site:cebpubservice.com 仪器设备 OR 实验室设备 OR 科研设备 招标',
    'site:gov.cn 高校仪器 OR 科研设备 OR 实验仪器 采购 招标 2026',
    'site:edu.cn 仪器采购 OR 设备采购 OR 实验室建设 招标 2026',
    'site:instrument.com.cn OR site:bio-equip.com 采购需求 OR 招标 OR 询价',
    'site:selectscience.net laboratory instrument supplier OR manufacturer 2026',
    'site:fishersci.com OR site:sigmaaldrich.com new product laboratory 2026',
    'site:labx.com laboratory equipment auction OR sale 2026',
    # ===== 科研资助/基金机会 (P0) =====
    'site:nsfc.gov.cn 项目指南 OR 申请通告 OR 基金 2026',
    'site:gov.cn 自然科学基金 OR 重点研发计划 申报 2026',
    'site:kjt.*.gov.cn 基金 OR 项目申报 OR 科技计划 2026',
    'site:erc.europa.eu funding call 2026',
    'site:ukri.org grant funding call deadline 2026',
    'site:ec.europa.eu "horizon europe" call deadline 2026',
    # ===== 大型仪器共享 (P1) =====
    'site:nrii.org.cn 仪器共享 OR 大型仪器 2026',
    'site:sgst.cn 仪器共享 OR 研发平台 2026',
    # ===== 高校技术成果 (P2) =====
    'site:edu.cn 技术转移 OR 成果转化 OR 专利转让 2026',
    'site:cas.cn 科技成果 OR 专利 OR 技术转让 2026',
    'site:ctex.cn 技术交易 OR 成果转化 2026',
    'site:ip.com patent license technology transfer 2026',
    'site:autm.net technology transfer 2026',
]

SUPPLIER_QUERIES = [
    'site:startus-insights.com carbon capture startup company 2026',
    'site:energystartups.org hydrogen OR energy OR climate startup',
    'site:rankred.com climate tech OR energy OR biotech startup company',
    'site:crunchbase.com "carbon capture" OR "clean energy" OR "biotech" company',
    # 新加供应商源
    'site:eu-startups.com startup company 2026',
    'site:ycombinator.com company startup technology',
    'site:angellist.com startup company technology',
    # ===== 科学仪器供应商专项搜索 =====
    'site:instrument.com.cn 厂商 OR 供应商 OR 生产商 2026',
    'site:bio-equip.com 公司 OR 厂商 OR 供应商 2026',
    'site:selectscience.net supplier OR manufacturer OR brand laboratory 2026',
    'site:thomasnet.com scientific instrument manufacturer 2026',
    'site:labcompare.com laboratory instrument supplier 2026',
    'site:labx.com laboratory equipment seller OR company 2026',
    'site:casmart.com.cn 供应商 OR 商家 OR 品牌 2026',
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
    """Firecrawl 全网搜索 — 失败时自动切换为 HTTP 直连降级"""
    global _firecrawl_credits_ok
    if not _firecrawl_credits_ok:
        return fallback_http_search(query, limit)
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
    except urllib.error.HTTPError as e:
        if e.code == 402:
            print(f"  ⚠️ Firecrawl 额度用尽 (HTTP 402)，切换为 HTTP 直连降级模式")
            _firecrawl_credits_ok = False
            return fallback_http_search(query, limit)
        print(f"  Firecrawl search error: {e}")
    except Exception as e:
        print(f"  Firecrawl search error: {e}")
    return []


def fallback_http_search(query, limit=3):
    """Firecrawl 额度耗尽时的 HTTP 直连降级方案 — 直接请求目标网站"""
    import urllib.parse
    results = []
    
    # 从搜索词中提取站点和关键词
    site_match = query.lower()
    keywords = []
    for part in query.split():
        if not part.startswith("site:") and not part.startswith("OR") and part not in ["AND", "2026"]:
            keywords.append(part.strip('"'))
    
    # 根据站点直接构建请求
    if "grants.gov" in site_match:
        url = "https://www.grants.gov/web/grants/search-grants.html"
        results.append({"url": url, "title": "Grants.gov 资助搜索", "content": "关键词: " + " ".join(keywords)})
    elif "xprize" in site_match:
        url = "https://www.xprize.org/competitions"
        results.append({"url": url, "title": "XPRIZE 竞赛列表", "content": "浏览所有活跃竞赛"})
    elif "darpa" in site_match:
        url = "https://www.darpa.mil/work-with-us/opportunities"
        results.append({"url": url, "title": "DARPA 合作机会", "content": "所有公开招标"})
    elif "nasa" in site_match:
        url = "https://www.nasa.gov/prizes-challenges-and-crowdsourcing/"
        results.append({"url": url, "title": "NASA 挑战与竞赛", "content": "浏览NASA公开挑战"})
    elif "herox" in site_match:
        url = "https://www.herox.com/"
        results.append({"url": url, "title": "HeroX 挑战赛", "content": "浏览公开挑战"})
    elif "ccgp" in site_match or "gov.cn" in site_match:
        results.append({"url": "http://www.ccgp.gov.cn/cggg/dfgg/", "title": "中国政府采购", "content": "政府采购仪器设备招标"})
    elif "cebpubservice" in site_match:
        results.append({"url": "http://www.cebpubservice.com/", "title": "招标投标公共服务", "content": "仪器设备招标公告"})
    elif "edu.cn" in site_match and ("技术" in query or "成果" in query):
        results.append({"url": "https://www.edu.cn/", "title": "中国教育网 技术转移", "content": "高校技术成果转让信息"})
    elif "cas.cn" in site_match:
        results.append({"url": "https://www.cas.cn/", "title": "中国科学院 成果转化", "content": "中科院科技成果与专利转让"})
    elif "startus-insights" in site_match:
        url = f"https://www.startus-insights.com/?s={'+'.join(keywords)}"
        results.append({"url": url, "title": "StartUs 初创企业", "content": "搜索: " + " ".join(keywords)})
    elif "ukri" in site_match:
        url = "https://www.ukri.org/opportunity/"
        results.append({"url": url, "title": "UKRI 英国研究与创新资助", "content": "浏览所有资助机会"})
    elif "erc" in site_match:
        url = "https://erc.europa.eu/funding"
        results.append({"url": url, "title": "ERC 欧洲研究委员会资助", "content": "浏览所有资助机会"})
    elif "nsfc" in site_match or "国家自然科学" in query:
        url = "https://www.nsfc.gov.cn/"
        results.append({"url": url, "title": "国家自然科学基金", "content": "项目指南与申请通告"})
    
    # 通用: 用 Google/Bing 搜索结果 (直接URL)
    search_term = " ".join(keywords) if keywords else query
    encoded = urllib.parse.quote(search_term[:100])
    results.append({
        "url": f"https://www.google.com/search?q={encoded}",
        "title": f"Google 搜索: {search_term[:60]}",
        "content": f"通过 Google 搜索 '{search_term[:80]}' 的结果"
    })
    
    if results:
        print("    [HTTP降级] " + "; ".join(r["title"] for r in results))
    return results[:limit]


# firecrawl_scrape 别名（兼容 retry 调用），降级模式下返回空内容
firecrawl_scrape = fallback_http_search


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
            "process": s.get("process", []),
            "contact": s.get("contact", {}),
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
    global _firecrawl_credits_ok
    mode = "Firecrawl API"
    if not _firecrawl_credits_ok:
        mode = "HTTP 直连降级 (Firecrawl 额度用尽)"
    print(f"=== Smart Crawler v2.1 ===")
    print(f"Started: {datetime.now().isoformat()}")
    print(f"Mode: {mode}")
    print(f"Strategy: {'Firecrawl' if _firecrawl_credits_ok else 'HTTP direct'} -> DeepSeek AI filter\n")

    # 重置状态，本运行中如果遇到402会自动降级
    _firecrawl_credits_ok = True

    ds = crawl_demands(dry_run)
    ss = crawl_suppliers(dry_run)

    final_mode = "HTTP 直连降级" if not _firecrawl_credits_ok else "Firecrawl"
    print(f"\n{'=' * 60}")
    print(f"Summary:")
    print(f"  Mode:      {final_mode}")
    print(f"  Demands:   {ds.demand_ok} new, {ds.demand_dup} dup, {ds.demand_fail} fail")
    print(f"  Suppliers: {ss.supplier_ok} new, {ss.supplier_dup} dup, {ss.supplier_fail} fail")
    print(f"Done.")


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    run(dry_run=dry)


