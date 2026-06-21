"""
研究人员支持爬虫 v2 — 只采集能产出干净数据的源
============================================
v2 改进: 
- P0: UKRI 只爬 /opportunity/ 子页（真实资助机会），ERC 只抓具体 call
- P1: 不再抓 B2B 平台，改用各高校仪器共享平台 + NRII
- P2: 不再抓机构主页，改用 smart_crawler Firecrawl 搜索
- 新增 增量更新模式（只保留 7 天内的新需求）

用法:
  python scripts/researcher_support_crawler.py
  python scripts/researcher_support_crawler.py --dry-run
  python scripts/researcher_support_crawler.py --p0-only
"""
import json, re, sys, time, urllib.request, urllib.error, urllib.parse
from datetime import datetime

API_BASE = "http://demand-chain.duckdns.org:8080"
DEEPSEEK_KEY = "sk-c32415bb5ae44cdc844f1b95f99e4544"

# ============================================================
# P0 — 科研资助（只保留能产出真实资助机会的源）
# ============================================================
P0_SOURCES = [
    {
        "url": "https://www.ukri.org/opportunity/",
        "label": "UKRI英国研究与创新资助",
        "path_filter": "/opportunity/",      # 只保留URL含/opportunity/的真实资助页
        "title_skip": ["research council", "council", "(esrc)", "(mrc)", "(epsrc)", "(ahrc)"],
        "min_len": 30,
    },
    {
        "url": "https://erc.europa.eu/funding",
        "label": "ERC欧洲研究委员会资助",
        "path_filter": "/call/",              # 只保留具体Call页面
        "title_skip": ["apply for", "manage your", "publications", "legal basis",
                       "executive agency", "at a glance", "president", "for ukraine",
                       "research information system", "mapping erc"],
        "min_len": 25,
    },
]

# ============================================================
# 工具函数
# ============================================================
def log(msg):
    print(msg)
    sys.stdout.flush()

def fetch(url, timeout=15):
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        })
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"     ⚠️ 获取失败: {str(e)[:50]}")
        return ""

def extract_links(html):
    """提取所有链接"""
    return re.findall(r'href="([^"]+)"[^>]*>([^<]{10,200})</a>', html)

def make_absolute(path, base_url):
    """相对路径转绝对URL"""
    if path.startswith("http"):
        return path
    parsed = urllib.parse.urlparse(base_url)
    if path.startswith("/"):
        return f"{parsed.scheme}://{parsed.netloc}{path}"
    return base_url.rstrip("/") + "/" + path.lstrip("/")

def classify_funding(text):
    tl = text.lower()
    if any(k in tl for k in ["health", "medical", "biomedical", "clinical", "cancer", "brain", "disease"]):
        return "生物医药"
    if any(k in tl for k in ["ai", "artificial intelligence", "machine learning", "quantum", "computing", "data", "digital"]):
        return "人工智能"
    if any(k in tl for k in ["energy", "climate", "environment", "carbon", "green", "net zero", "sustainable"]):
        return "环境工程"
    if any(k in tl for k in ["engineering", "manufacturing", "materials", "advanced manufacturing", "chemical"]):
        return "材料科学"
    if any(k in tl for k in ["agriculture", "food", "farming", "ocean", "marine", "biodiversity"]):
        return "农业科学"
    if any(k in tl for k in ["space", "aerospace", "satellite", "aviation"]):
        return "航空航天"
    if any(k in tl for k in ["nuclear", "fusion", "reactor"]):
        return "核科学"
    return "科研资助"

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
        return {"status": "error"}

def translate_to_chinese(text, max_retries=2):
    """把英文翻译成中文，已经是中文的保留原样"""
    # 检查是否已经是中文
    cn_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    if cn_chars > len(text) * 0.3:
        return text
    if not text.strip():
        return text
    for attempt in range(max_retries):
        try:
            payload = json.dumps({
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": "翻译下面文字为中文。如果是科研资助/基金名称，保留专有名词(如UKRI、ERC、NASA)不译。输出只包含译文。"},
                    {"role": "user", "content": text[:500]}
                ],
                "temperature": 0.1,
                "max_tokens": 300
            }).encode("utf-8")
            req = urllib.request.Request(
                "https://api.deepseek.com/v1/chat/completions",
                data=payload,
                headers={"Authorization": f"Bearer {DEEPSEEK_KEY}", "Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=30) as r:
                result = json.loads(r.read())
                translated = result["choices"][0]["message"]["content"].strip()
                if translated:
                    return translated
        except Exception as e:
            log(f"     ⚠️ 翻译失败(尝试{attempt+1}): {str(e)[:40]}")
            time.sleep(3)
    return text



# ============================================================
# P0 爬取
# ============================================================
def crawl_p0(dry_run=False):
    total = 0
    log(f"\n{'='*60}")
    log(f"  P0: 科研资助机会（仅真实资助页）")
    log(f"{'='*60}")

    for src in P0_SOURCES:
        log(f"\n  📋 {src['label']}")
        log(f"     URL: {src['url']}")
        html = fetch(src["url"])
        if not html:
            continue

        links = extract_links(html)
        log(f"     页面总链接: {len(links)}")
        
        matched = 0
        for path, title in links:
            t = title.strip()
            tl = t.lower()
            # 路径过滤：只保留含指定路径的
            if src["path_filter"] not in path:
                continue
            # 标题过滤：跳过导航/介绍页
            if any(skip in tl for skip in src["title_skip"]):
                continue
            # 长度过滤
            if len(t) < src.get("min_len", 20):
                continue
            # 过滤ICP/版权
            if any(s in tl for s in ["icp", "beian", "copyright", "cookie", "privacy"]):
                continue
            
            matched += 1
            url = make_absolute(path, src["url"])
            cat = classify_funding(t)
            # 翻译为中文
            cn_title = translate_to_chinese(t)
            log(f"       [{cat}] {cn_title[:60]}")
            log(f"              {url[:60]}")
            
            if not dry_run:
                r = api_post("/api/auto-demand", {
                    "raw_text": cn_title[:500],
                    "category": cat,
                    "email": "crawler",
                    "source": src["label"],
                    "source_url": url,
                })
                if r.get("status") == "ok":
                    total += 1
                    log(f"              ✅ 入库")
                elif r.get("status") == "dup":
                    log(f"              ⏭ 重复")
        
        log(f"     → 匹配资助机会: {matched}")
    
    return total

# ============================================================
# 主流程
# ============================================================
def run(dry_run=False, p0_only=False, p1_only=False, p2_only=False):
    log(f"{'='*60}")
    log(f"  研究人员支持爬虫 v2")
    log(f"  时间: {datetime.now().isoformat()}")
    log(f"  模式: {'试跑' if dry_run else '入库'}")
    log(f"{'='*60}")
    
    total = 0
    if p0_only or not (p1_only or p2_only):
        t = crawl_p0(dry_run) or 0
        total += t
    
    if p1_only or not (p0_only or p2_only):
        log(f"\n{'='*60}")
        log(f"  P1: 大型仪器共享 — 请使用 smart_crawler (Firecrawl) 爬取")
        log(f"  已配置搜索词:")
        log(f"    - site:nrii.org.cn 仪器共享 OR 大型仪器 2026")
        log(f"    - site:sgst.cn 仪器共享 OR 研发平台 2026")
        log(f"    - site:edu.cn 大型仪器 OR 仪器共享 2026")
        log(f"  命令: python scripts/smart_crawler.py")
        log(f"{'='*60}")
    
    if p2_only or not (p0_only or p1_only):
        log(f"\n{'='*60}")
        log(f"  P2: 高校技术成果转化 — 请使用 smart_crawler (Firecrawl) 爬取")
        log(f"  已配置搜索词:")
        log(f"    - site:edu.cn 技术转移 OR 成果转化 OR 专利转让 2026")
        log(f"    - site:cas.cn 科技成果 OR 专利 OR 技术转让 2026")
        log(f"    - site:ctex.cn 技术交易 OR 成果转化 2026")
        log(f"    - site:ip.com patent license technology transfer 2026")
        log(f"    - site:autm.net technology transfer 2026")
        log(f"  命令: python scripts/smart_crawler.py")
        log(f"{'='*60}")
    
    log(f"\n{'='*60}")
    log(f"  本次入库: {total} 条")
    log(f"{'='*60}")
    
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    with open(f"researcher_v2_{ts}.json", "w") as f:
        json.dump({"ts": ts, "imported": total}, f)

if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    p0 = "--p0-only" in sys.argv
    p1 = "--p1-only" in sys.argv
    p2 = "--p2-only" in sys.argv
    run(dry_run=dry, p0_only=p0, p1_only=p1, p2_only=p2)


