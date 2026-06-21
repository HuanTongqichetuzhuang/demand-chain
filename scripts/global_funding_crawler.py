#!/usr/bin/env python3
"""
需求链平台 — 全球科研基金爬虫 v1.0
========================================
采集全球主要发达经济体的科研资助机会：
1. DOE ARPA-E (美国能源部前沿能源项目)
2. DOE EERE (美国能源部可再生能源)
3. NSF (美国国家科学基金会)
4. NIH (美国国立卫生研究院)
5. NEDO (日本新能源产业技术机构)
6. NRF (韩国国家研究基金会)
7. ARC (澳大利亚研究委员会)
8. NSERC (加拿大自然科学与工程研究会)

用法:
  python scripts/global_funding_crawler.py           # 正式运行
  python scripts/global_funding_crawler.py --dry-run  # 试跑不入库
  python scripts/global_funding_crawler.py --us-only  # 只跑美国源
  python scripts/global_funding_crawler.py --asia-only # 只跑亚洲源
"""
import hashlib, json, re, sys, time, urllib.request, urllib.error, urllib.parse
from datetime import datetime

API_BASE = "http://8.154.26.92:8080"
DEEPSEEK_KEY = "sk-c32415bb5ae44cdc844f1b95f99e4544"

def log(msg):
    print(msg)
    sys.stdout.flush()

def fetch(url, timeout=20):
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/json,*/*",
        })
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception as e:
        log(f"     ⚠️ 获取失败 {url[:60]}: {str(e)[:50]}")
        return ""

def translate_to_chinese(text, max_retries=2):
    if not text or len(text) < 5:
        return text
    cn_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    if cn_chars > len(text) * 0.3:
        return text
    for attempt in range(max_retries):
        try:
            payload = json.dumps({
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": "翻译下面文字为中文。保留专有名词(机构缩写如ARPA-E、NSF、NIH、NEDO、NRF不译)。只输出译文。"},
                    {"role": "user", "content": text[:500]}
                ],
                "temperature": 0.1, "max_tokens": 300
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

def classify_funding(text):
    tl = text.lower()
    if any(k in tl for k in ["energy", "solar", "wind", "renewable", "battery", "grid", "hydrogen", "nuclear", "fusion", "fuel", "photovoltaic", "geothermal", "biofuel"]):
        return "新能源"
    if any(k in tl for k in ["health", "medical", "biomedical", "clinical", "cancer", "brain", "disease", "drug", "vaccine", "therapy", "diagnostic", "genetic", "genome"]):
        return "生物医药"
    if any(k in tl for k in ["ai", "artificial intelligence", "machine learning", "deep learning", "nlp", "computer vision", "autonomous", "robotics", "neural"]):
        return "人工智能"
    if any(k in tl for k in ["material", "nanomaterial", "polymer", "composite", "alloy", "ceramic", "coating", "catalyst"]):
        return "材料科学"
    if any(k in tl for k in ["cyber", "security", "encryption", "quantum", "blockchain", "privacy", "cryptograph"]):
        return "信息技术"
    if any(k in tl for k in ["aerospace", "space", "satellite", "aviation", "propulsion", "drone", "uav"]):
        return "航空航天"
    if any(k in tl for k in ["climate", "environment", "carbon", "emission", "sustainable", "water", "ocean", "marine"]):
        return "环境工程"
    if any(k in tl for k in ["agriculture", "crop", "food", "soil", "fishery", "farming"]):
        return "农业科学"
    if any(k in tl for k in ["manufacturing", "advanced manufacturing", "industry", "automation", "sensor", "semiconductor", "chip"]):
        return "电子科学与技术"
    if any(k in tl for k in ["chemistry", "chemical", "biology", "biotech", "synthetic", "crispr"]):
        return "生物技术"
    if any(k in tl for k in ["education", "training", "social", "behavior", "learning", "curriculum"]):
        return "其他"
    return "其他"


def api_post(path, payload):
    data = json.dumps(payload).encode("utf-8")
    try:
        req = urllib.request.Request(f"{API_BASE}{path}", data=data,
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return {"status": "error", "code": e.code}
    except Exception as e:
        return {"status": "error", "reason": str(e)}

def extract_links(html):
    return re.findall(r'href="([^"]+)"[^>]*>([^<]{15,300})</a>', html)

def make_absolute(path, base_url):
    if path.startswith("http"):
        return path
    parsed = urllib.parse.urlparse(base_url)
    if path.startswith("/"):
        return f"{parsed.scheme}://{parsed.netloc}{path}"
    return base_url.rstrip("/") + "/" + path.lstrip("/")


# ============================================================
# 美国能源部 ARPA-E — 前沿能源项目 (改用 DOE 主站)
# ============================================================
def crawl_doe(dry_run=False):
    """DOE — 改用 energy.gov 主资助页"""
    total = 0
    label = "DOE美国能源部"
    log(f"\n  📋 {label}")
    
    urls = [
        "https://www.energy.gov/funding-opportunities",
        "https://www.energy.gov/eere/funding-opportunities",
    ]
    
    for url in urls:
        log(f"     URL: {url}")
        html = fetch(url)
        if not html:
            continue
        
        links = extract_links(html)
        log(f"     页面连接数: {len(links)}")
        matched = 0
        for path, title in links:
            tl = title.lower()
            if any(s in tl for s in ["login", "sign in", "register", "cookie", "privacy", "terms", "subscribe", "contact", "faq", "careers", "about"]):
                continue
            if len(title) < 20:
                continue
            if not any(k in tl for k in ["funding", "opportunity", "program", "open", "apply", "solicitation", "request for", "proposal", "notice", "deada", "foa"]):
                continue
            
            matched += 1
            cn_title = translate_to_chinese(title)
            cat = classify_funding(title)
            url_abs = make_absolute(path, url)
            log(f"       [{cat}] {cn_title[:70]}")
            log(f"              {url_abs[:70]}")
            if not dry_run:
                r = api_post("/api/auto-demand", {
                    "raw_text": f"{cn_title}\n来源: {label}, 参见: {url_abs}",
                    "category": cat, "email": "crawler",
                    "source": label, "source_url": url_abs,
                })
                if r.get("status") == "ok":
                    total += 1
                    log(f"              ✅ 入库")
                elif r.get("status") == "dup":
                    log(f"              ⏭ 重复")
        log(f"     → 匹配: {matched}")
    
    return total


# ============================================================
# DOE EERE — 可再生能源
# ============================================================
def crawl_doe_eere(dry_run=False):
    total = 0
    label = "DOE EERE可再生能源"
    log(f"\n  📋 {label}")
    
    url = "https://www.energy.gov/eere/funding-opportunities"
    log(f"     URL: {url}")
    html = fetch(url)
    if not html:
        return 0
    
    links = extract_links(html)
    log(f"     页面连接数: {len(links)}")
    matched = 0
    for path, title in links:
        tl = title.lower()
        if any(s in tl for s in ["login", "sign in", "register", "cookie", "privacy", "subscribe", "newsletter"]):
            continue
        if len(title) < 20:
            continue
        if not any(k in tl for k in ["funding", "opportunity", "grant", "solicitation", "request for", "proposal", "notice", "open", "apply"]):
            continue
        
        matched += 1
        cn_title = translate_to_chinese(title)
        cat = classify_funding(title)
        url_abs = make_absolute(path, url)
        log(f"       [{cat}] {cn_title[:70]}")
        log(f"              {url_abs[:70]}")
        if not dry_run:
            r = api_post("/api/auto-demand", {
                "raw_text": f"{cn_title}\n来源: {label}, 参见: {url_abs}",
                "category": cat,
                "email": "crawler",
                "source": label,
                "source_url": url_abs,
            })
            if r.get("status") == "ok":
                total += 1
                log(f"              ✅ 入库")
            elif r.get("status") == "dup":
                log(f"              ⏭ 重复")
    log(f"     → 匹配: {matched}")
    return total


# ============================================================
# NSF — 美国国家科学基金会（通过 Grants.gov 替代）
# 注：nsf.gov 直接 HTTP 被屏蔽，改用 Grants.gov RSS + 搜素
# ============================================================
def crawl_nsf(dry_run=False):
    total = 0
    label = "NSF美国国家科学基金会"
    log(f"\n  📋 {label}")
    
    # Grants.gov 公开 RSS (无需API key)
    rss_url = "https://www.grants.gov/grantsws/rest/opportunities/rss?status=open"
    log(f"     RSS: {rss_url}")
    xml = fetch(rss_url)
    if not xml:
        # 备选: Grants.gov 搜索页面
        log(f"     RSS不可用，尝试Grants.gov搜索页")
        url = "https://www.grants.gov/search-grants"
        html = fetch(url)
        if not html:
            return 0
        links = extract_links(html)
        log(f"     页面连接数: {len(links)}")
    else:
        items = re.findall(r'<item>(.*?)</item>', xml, re.DOTALL)
        log(f"     RSS条目数: {len(items)}")
        for item in items[:20]:
            title_m = re.search(r'<title>(.*?)</title>', item, re.DOTALL)
            link_m = re.search(r'<link>(.*?)</link>', item, re.DOTALL)
            desc_m = re.search(r'<description>(.*?)</description>', item, re.DOTALL)
            if not title_m:
                continue
            title = title_m.group(1).strip()
            link = link_m.group(1).strip() if link_m else ""
            desc = desc_m.group(1).strip()[:200] if desc_m else ""
            if len(title) < 15:
                continue
            cn_title = translate_to_chinese(title)
            cat = classify_funding(title)
            log(f"       [{cat}] {cn_title[:70]}")
            if not dry_run:
                r = api_post("/api/auto-demand", {
                    "raw_text": f"{cn_title}\n{desc}\n来源: {label}通过Grants.gov",
                    "category": cat, "email": "crawler",
                    "source": label, "source_url": link,
                })
                if r.get("status") == "ok":
                    total += 1
                    log(f"              ✅ 入库")
                elif r.get("status") == "dup":
                    log(f"              ⏭ 重复")
    
    log(f"     → 入库: {total}")
    return total


# ============================================================
# NIH — 美国国立卫生研究院（改用 Grants.gov 生物医学类）
# 注：直接访问 grants.nih.gov 被屏蔽，改用 Grants.gov 按分类过滤
# ============================================================
def crawl_nih(dry_run=False):
    total = 0
    label = "NIH美国国立卫生研究院资助"
    log(f"\n  📋 {label}")
    
    # NIH 在 Grants.gov 上的资助公告页面
    urls = [
        "https://www.grants.gov/web/grants/search-grants.html",
        "https://grants.nih.gov/funding/searchguide/index.html#/",
    ]
    
    for url in urls:
        log(f"     URL: {url}")
        html = fetch(url)
        if not html:
            continue
        
        links = extract_links(html)
        log(f"     页面连接数: {len(links)}")
        matched = 0
        for path, title in links:
            tl = title.lower()
            if any(s in tl for s in ["login", "sign in", "register", "email", "subscribe", "cookie"]):
                continue
            if len(title) < 25:
                continue
            if not any(k in tl for k in ["grant", "funding", "research", "health", "medical", "clinical", "rfa", "pa-", "par-", "not-", "opportunity"]):
                continue
            
            matched += 1
            cn_title = translate_to_chinese(title)
            cat = "生物医药"
            url_abs = make_absolute(path, url)
            log(f"       [{cat}] {cn_title[:70]}")
            log(f"              {url_abs[:70]}")
            if not dry_run:
                r = api_post("/api/auto-demand", {
                    "raw_text": f"{cn_title}\n来源: {label}, 参见: {url_abs}",
                    "category": cat, "email": "crawler",
                    "source": label, "source_url": url_abs,
                })
                if r.get("status") == "ok":
                    total += 1
                    log(f"              ✅ 入库")
                elif r.get("status") == "dup":
                    log(f"              ⏭ 重复")
        log(f"     → 匹配: {matched}")
    
    return total


# ============================================================
# NEDO — 日本新能源产业技术综合开发机构
# ============================================================
def crawl_nedo(dry_run=False):
    total = 0
    label = "NEDO日本新能源产业技术机构"
    log(f"\n  📋 {label}")
    
    urls = [
        ("https://www.nedo.go.jp/koubo/", "NEDO公募"),
        ("https://www.nedo.go.jp/english/funding/index.html", "NEDO English funding"),
    ]
    
    for url, name in urls:
        log(f"     URL: {url}")
        html = fetch(url)
        if not html:
            continue
        
        links = extract_links(html)
        log(f"     页面连接数: {len(links)}")
        matched = 0
        for path, title in links:
            tl = title.lower()
            if any(s in tl for s in ["cookie", "privacy", "newsletter", "site map", "about", "access"]):
                continue
            if len(title) < 15:
                continue
            if not any(k in tl for k in ["funding", "grant", "call", "program", "project", "research", "公募", "助成", "研究開発", "技術開発", "proposal", "募集", "fy"]):
                continue
            
            matched += 1
            cn_title = translate_to_chinese(title)
            cat = classify_funding(title)
            url_abs = make_absolute(path, url)
            log(f"       [{cat}] {cn_title[:70]}")
            log(f"              {url_abs[:70]}")
            if not dry_run:
                r = api_post("/api/auto-demand", {
                    "raw_text": f"{cn_title}\n来源: {label}({name}), 参见: {url_abs}",
                    "category": cat,
                    "email": "crawler",
                    "source": label,
                    "source_url": url_abs,
                })
                if r.get("status") == "ok":
                    total += 1
                    log(f"              ✅ 入库")
                elif r.get("status") == "dup":
                    log(f"              ⏭ 重复")
        log(f"     → 匹配: {matched}")
    
    return total


# ============================================================
# NRF — 韩国国家研究基金会
# ============================================================
def crawl_nrf(dry_run=False):
    """NRF韩国 — 改用 NRF 韩文主页 + BK21 等已知项目页"""
    total = 0
    label = "NRF韩国国家研究基金会"
    log(f"\n  📋 {label}")
    
    # 使用多个可能的路径
    urls = [
        "https://www.nrf.re.kr/index",
        "https://www.nrf.re.kr/eng/index",
    ]
    
    for url in urls:
        log(f"     URL: {url}")
        html = fetch(url)
        if not html:
            continue
        links = extract_links(html)
        log(f"     页面连接数: {len(links)}")
        matched = 0
        for path, title in links:
            tl = title.lower()
            if any(s in tl for s in ["cookie", "privacy", "login", "sign", "sitemap"]):
                continue
            if len(title) < 15:
                continue
            if not any(k in tl for k in ["funding", "grant", "program", "연구", "사업", "지원", "과제", "공고"]):
                continue
            matched += 1
            cn_title = translate_to_chinese(title)
            cat = classify_funding(title)
            url_abs = make_absolute(path, url)
            log(f"       [{cat}] {cn_title[:70]}")
            if not dry_run:
                r = api_post("/api/auto-demand", {
                    "raw_text": f"{cn_title}\n来源: {label}", "category": cat,
                    "email": "crawler", "source": label, "source_url": url_abs,
                })
                if r.get("status") == "ok":
                    total += 1
                    log(f"              ✅ 入库")
                elif r.get("status") == "dup":
                    log(f"              ⏭ 重复")
        log(f"     → 匹配: {matched}")
    return total


# ============================================================
# ARC — 澳大利亚研究委员会
# ============================================================
def crawl_arc(dry_run=False):
    """ARC澳大利亚 — 因网络超时改用可访问的澳洲研究资助页面"""
    total = 0
    label = "澳大利亚研究资助"
    log(f"\n  📋 {label}")
    
    # 改用政府和教育机构公开页面（更易访问）
    urls = [
        "https://www.education.gov.au/research-block-grants",
        "https://www.business.gov.au/grants-and-programs",
    ]
    
    for url in urls:
        log(f"     URL: {url}")
        html = fetch(url, timeout=15)
        if not html:
            continue
        links = extract_links(html)
        log(f"     页面连接数: {len(links)}")
        matched = 0
        for path, title in links:
            tl = title.lower()
            if any(s in tl for s in ["login", "sign in", "register", "cookie", "subscribe", "contact"]):
                continue
            if len(title) < 20:
                continue
            if not any(k in tl for k in ["grant", "funding", "scheme", "program", "research", "award", "scholarship", "fellowship"]):
                continue
            matched += 1
            cn_title = translate_to_chinese(title)
            cat = classify_funding(title)
            url_abs = make_absolute(path, url)
            log(f"       [{cat}] {cn_title[:70]}")
            if not dry_run:
                r = api_post("/api/auto-demand", {
                    "raw_text": f"{cn_title}\n来源: {label}", "category": cat,
                    "email": "crawler", "source": label, "source_url": url_abs,
                })
                if r.get("status") == "ok":
                    total += 1
                    log(f"              ✅ 入库")
                elif r.get("status") == "dup":
                    log(f"              ⏭ 重复")
        log(f"     → 匹配: {matched}")
    return total


# ============================================================
# NSERC — 加拿大自然科学与工程研究会
# ============================================================
def crawl_nserc(dry_run=False):
    total = 0
    label = "NSERC加拿大自然科学与工程研究会"
    log(f"\n  📋 {label}")
    
    url = "https://www.nserc-crsng.gc.ca/professors-professeurs/grants-subs/index_eng.asp"
    log(f"     URL: {url}")
    html = fetch(url)
    if not html:
        return 0
    
    links = extract_links(html)
    log(f"     页面连接数: {len(links)}")
    matched = 0
    for path, title in links:
        tl = title.lower()
        if any(s in tl for s in ["login", "sign in", "register", "cookie", "subscribe", "contact", "faq", "search"]):
            continue
        if len(title) < 20:
            continue
        if not any(k in tl for k in ["grant", "funding", "program", "fellowship", "scholarship", "research", "discovery", "innovation", "collaborative", "strategic", "network", "award"]):
            continue
        
        matched += 1
        cn_title = translate_to_chinese(title)
        cat = classify_funding(title)
        url_abs = make_absolute(path, url)
        log(f"       [{cat}] {cn_title[:70]}")
        log(f"              {url_abs[:70]}")
        if not dry_run:
            r = api_post("/api/auto-demand", {
                "raw_text": f"{cn_title}\n来源: {label}, 参见: {url_abs}",
                "category": cat,
                "email": "crawler",
                "source": label,
                "source_url": url_abs,
            })
            if r.get("status") == "ok":
                total += 1
                log(f"              ✅ 入库")
            elif r.get("status") == "dup":
                log(f"              ⏭ 重复")
    log(f"     → 匹配: {matched}")
    return total


# ============================================================
# 主流程
# ============================================================
def run(dry_run=False, us_only=False, asia_only=False):
    log(f"{'='*60}")
    log(f"  全球科研基金爬虫 v1.0")
    log(f"  时间: {datetime.now().isoformat()}")
    log(f"  模式: {'试跑(不入库)' if dry_run else '入库'}")
    log(f"{'='*60}")
    
    total = 0
    
    if not asia_only:
        # 美国/欧洲/澳洲源
        t = crawl_doe(dry_run) or 0; total += t
        t = crawl_doe_eere(dry_run) or 0; total += t
        t = crawl_arc(dry_run) or 0; total += t
        t = crawl_nserc(dry_run) or 0; total += t
    
    if not us_only:
        # 亚洲源
        t = crawl_nedo(dry_run) or 0; total += t
        t = crawl_nrf(dry_run) or 0; total += t
    
    log(f"\n{'='*60}")
    log(f"  本次入库: {total} 条")
    log(f"{'='*60}")
    
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    with open(f"global_funding_{ts}.json", "w") as f:
        json.dump({"ts": ts, "source": "全球科研基金", "imported": total}, f)
    
    return total

if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    us = "--us-only" in sys.argv
    asia = "--asia-only" in sys.argv
    run(dry_run=dry, us_only=us, asia_only=asia)
