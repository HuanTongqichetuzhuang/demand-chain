#!/usr/bin/env python3
"""
需求链平台 — 中国企业供应商名录爬虫 v1.0
========================================
采集公开的中国企业/机构名单，转为结构化供应商数据：
1. 工信部专精特新"小巨人"企业
2. 科创板上市科技公司
3. 国家企业技术中心
4. CNAS认可实验室

用法:
  python scripts/china_enterprise_crawler.py            # 正式运行
  python scripts/china_enterprise_crawler.py --dry-run   # 试跑不入库
  python scripts/china_enterprise_crawler.py --zjt       # 只跑专精特新
"""
import hashlib, json, re, sys, time, urllib.request, urllib.error, urllib.parse
from datetime import datetime

API_BASE = "http://8.154.26.92:8080"
DEEPSEEK_KEY = "sk-c32415bb5ae44cdc844f1b95f99e4544"

def log(msg):
    print(msg)
    sys.stdout.flush()

def fetch(url, timeout=20, encoding="auto"):
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        })
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            enc = r.headers.get_content_charset() or "utf-8"
            return raw.decode(enc, errors="replace")
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
                    {"role": "system", "content": "翻译为中文，只输出译文。"},
                    {"role": "user", "content": text[:500]}
                ],
                "temperature": 0.1, "max_tokens": 200
            }).encode("utf-8")
            req = urllib.request.Request(
                "https://api.deepseek.com/v1/chat/completions",
                data=payload,
                headers={"Authorization": f"Bearer {DEEPSEEK_KEY}", "Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=30) as r:
                result = json.loads(r.read())
                t = result["choices"][0]["message"]["content"].strip()
                if t: return t
        except Exception as e:
            log(f"     ⚠️ 翻译失败(尝试{attempt+1}): {e}")
            time.sleep(3)
    return text

def classify_enterprise(name, industry_hint=""):
    tl = (name + " " + industry_hint).lower()
    if any(k in tl for k in ["医药", "医疗", "生物", "制药", "医学", "临床", "基因", "疫苗", "诊断", "health", "pharma", "biotech"]):
        return "生物医药"
    if any(k in tl for k in ["半导体", "芯片", "集成电路", "电子", "光电", "通信", "5g", "6g", "semiconductor", "chip"]):
        return "电子科学与技术"
    if any(k in tl for k in ["人工智能", "智能", "大数据", "ai", "artificial", "machine learning"]):
        return "人工智能"
    if any(k in tl for k in ["机器", "自动化", "机器人", "robot", "automation"]):
        return "机器人与智能系统"
    if any(k in tl for k in ["新能源", "光伏", "风电", "氢", "储能", "电池", "solar", "battery"]):
        return "新能源"
    if any(k in tl for k in ["材料", "纳米", "高分子", "合金", "陶瓷", "纤维", "material"]):
        return "材料科学"
    if any(k in tl for k in ["航空", "航天", "卫星", "无人", "飞行", "aero", "space"]):
        return "航空航天"
    if any(k in tl for k in ["软件", "信息", "网络", "数据", "云计算", "blockchain", "software", "data"]):
        return "信息技术"
    if any(k in tl for k in ["环境", "环保", "水", "废", "碳", "节能", "environment"]):
        return "环境工程"
    if any(k in tl for k in ["传感", "仪器", "仪表", "检测", "测量", "sensor", "instrument"]):
        return "传感器技术"
    if any(k in tl for k in ["汽车", "交通", "车", "transport", "vehicle", "ev"]):
        return "交通运输"
    if any(k in tl for k in ["农业", "农", "种子", "food", "农业"]):
        return "农业科学"
    if any(k in tl for k in ["化工", "催化", "化学", "chemical"]):
        return "化学工程"
    if any(k in tl for k in ["核", "radiation"]):
        return "核科学"
    if any(k in tl for k in ["实验室", "检验", "检测", "校准", "test", "lab", "calibration"]):
        return "传感器技术"
    return "其他"


def api_post(path, payload):
    data = json.dumps(payload).encode("utf-8")
    try:
        req = urllib.request.Request(f"{API_BASE}{path}", data=data,
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return {"status": "error", "code": e.code, "msg": e.read().decode()[:100]}
    except Exception as e:
        return {"status": "error", "reason": str(e)}


# ============================================================
# 1. 专精特新"小巨人"企业（从公开的CSV/Excel/政府公告）
# ============================================================
def crawl_zjt_enterprises(dry_run=False):
    """爬取专精特新小巨人企业 — 使用已整理的CSV数据"""
    total = 0
    label = "专精特新小巨人企业"
    log(f"\n  📋 {label}")
    
    # 读取本地已有CSV（如果存在）
    import os
    csv_files = [f for f in os.listdir(".") if f.startswith("companies_zjtx") and f.endswith(".csv")]
    csv_files += [f for f in os.listdir(".") if f == "companies_zjtx.csv"]
    
    if csv_files:
        log(f"     发现本地CSV: {csv_files[0]}")
        import csv
        try:
            with open(csv_files[0], "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            log(f"     CSV行数: {len(rows)}")
            
            for row in rows:
                name = row.get("name", "") or row.get("企业名称", "") or row.get("公司", "") or ""
                if not name:
                    continue
                province = row.get("province", "") or row.get("地区", "") or row.get("省份", "") or ""
                cat = classify_enterprise(name, province)
                
                log(f"       [{cat}] {name[:50]}  {province}")
                if not dry_run:
                    r = api_post("/api/auto-supplier", {
                        "email": "crawler",
                        "profile_type": "COMPANY",
                        "country": "中国",
                        "trust_score": 0.7,
                        "agent_card": {
                            "name": name,
                            "description": f"专精特新小巨人企业{f'（{province}）' if province else ''}",
                            "category": cat,
                            "industry": cat,
                            "url": "",
                            "skills": [cat, "专精特新", "技术研发"],
                            "contact": {},
                        },
                    })
                    if r.get("status") == "ok":
                        total += 1
                    elif r.get("status") == "dup":
                        pass
        except Exception as e:
            log(f"     ⚠️ CSV解析失败: {e}")
            return 0
        log(f"     → 入库: {total}")
        return total
    
    log(f"     无本地CSV文件，尝试搜索工信部公开名单...")
    # 搜索工信部公示名单（如果可以直接访问）
    gov_urls = [
        "https://www.miit.gov.cn/zwgk/zcwj/wjfb/tz/art/2023/art_123456.html",
    ]
    
    log(f"     ⚠️ 专精特新名单页面JS渲染，无法直接HTTP抓取")
    log(f"     → 可以使用本地 companies_zjtx.csv 文件")
    log(f"     → 也可以搜索: site:gov.cn 专精特新 小巨人 企业名单")
    return 0


# ============================================================
# 2. CNAS 认可实验室
# ============================================================
def crawl_cnas_labs(dry_run=False):
    """爬取 CNAS 认可实验室名录"""
    total = 0
    label = "CNAS认可实验室"
    log(f"\n  📋 {label}")
    
    url = "https://www.cnas.org.cn/"
    log(f"     URL: {url}")
    html = fetch(url)
    if not html:
        log(f"     ⚠️ 需要更具体的子页面URL")
        log(f"     → 搜索: site:cnas.org.cn 认可实验室 OR 检测实验室")
        return 0
    
    # 尝试找实验室目录链接
    lab_links = re.findall(r'href="([^"]*lab[^"]*)"', html, re.I)
    if lab_links:
        log(f"     Lab子页面: {len(lab_links)}")
    else:
        log(f"     → CNAS官网JS渲染，建议使用smart_crawler搜索")
    return 0


# ============================================================
# 3. 科创板上市科技公司（上交所数据）
# ============================================================
def crawl_kcb_listed(dry_run=False):
    """爬取科创板上市公司"""
    total = 0
    label = "科创板上市公司"
    log(f"\n  📋 {label}")
    
    # 上交所科创板列表（公开）
    url = "http://www.sse.com.cn/assortment/stock/list/name/"
    log(f"     URL: {url}")
    html = fetch(url, encoding="auto")
    
    if not html:
        log(f"     ⚠️ 上交所页面需要JS渲染")
        log(f"     → 可以改用东方财富等第三方数据")
        
        # 尝试东方财富
        alt_url = "https://data.eastmoney.com/kcb/"
        log(f"     备选: {alt_url}")
        alt_html = fetch(alt_url)
        if not alt_html:
            log(f"     → 建议使用 smart_crawler 搜索: site:eastmoney.com 科创板 上市公司")
            return 0
    
    # 提取表格数据
    rows = re.findall(r'<tr[^>]*>(.*?)</tr>', html, re.DOTALL)
    log(f"     表格行数: {len(rows)}")
    
    for row in rows[:100]:
        cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
        if len(cells) < 2:
            continue
        name_match = re.search(r'>([^<]{2,30})<', cells[1])
        if not name_match:
            continue
        company_name = name_match.group(1).strip()
        if not company_name or len(company_name) < 3:
            continue
        
        cat = classify_enterprise(company_name)
        log(f"       [{cat}] {company_name[:50]}")
        
        if not dry_run:
            r = api_post("/api/auto-supplier", {
                "email": "crawler",
                "profile_type": "COMPANY",
                "country": "中国",
                "trust_score": 0.8,
                "agent_card": {
                    "name": company_name,
                    "description": f"科创板上市公司，{cat}领域",
                    "category": cat,
                    "industry": cat,
                    "url": "",
                    "skills": [cat, "技术研发", "上市公司"],
                    "contact": {},
                },
            })
            if r.get("status") == "ok":
                total += 1
            elif r.get("status") == "dup":
                pass
    
    log(f"     → 入库: {total}")
    return total


# ============================================================
# 4. 国家企业技术中心（发改委名单）
# ============================================================
def crawl_national_tech_centers(dry_run=False):
    """爬取国家企业技术中心"""
    total = 0
    label = "国家企业技术中心"
    log(f"\n  📋 {label}")
    
    log(f"     ⚠️ 发改委网站JS渲染，无法直接HTTP抓取")
    log(f"     → 搜索: site:gov.cn 国家企业技术中心 名单 2026")
    return 0


# ============================================================
# 主流程
# ============================================================
def run(dry_run=False, zjt_only=False):
    log(f"{'='*60}")
    log(f"  中国企业供应商名录爬虫 v1.0")
    log(f"  时间: {datetime.now().isoformat()}")
    log(f"  模式: {'试跑(不入库)' if dry_run else '入库'}")
    log(f"{'='*60}")
    
    total = 0
    
    # 1. 专精特新
    t = crawl_zjt_enterprises(dry_run) or 0
    total += t
    
    if not zjt_only:
        # 2. CNAS
        t = crawl_cnas_labs(dry_run) or 0
        total += t
        
        # 3. 科创板
        t = crawl_kcb_listed(dry_run) or 0
        total += t
        
        # 4. 国家企业技术中心
        t = crawl_national_tech_centers(dry_run) or 0
        total += t
    
    log(f"\n{'='*60}")
    log(f"  本次入库: {total} 条")
    log(f"{'='*60}")
    
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    with open(f"china_enterprise_{ts}.json", "w") as f:
        json.dump({"ts": ts, "source": "中国企业名录", "imported": total}, f)
    
    return total

if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    zjt = "--zjt" in sys.argv
    run(dry_run=dry, zjt_only=zjt)
