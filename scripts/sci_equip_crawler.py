"""
科研设备专用爬虫 — 对接科研院校与实验器材制造商
============================================
采集目标：
- 需求侧：高校/科研院所对实验仪器、设备、耗材的采购需求
- 供给侧：科学仪器制造商、实验设备供应商、检测服务机构

用法:
  python scripts/sci_equip_crawler.py
  python scripts/sci_equip_crawler.py --dry-run
"""
import hashlib, json, re, sys, time, urllib.request, urllib.error, urllib.parse
from datetime import datetime
from collections import Counter

API_BASE = "http://demand-chain.duckdns.org:8080"

# ============================================================
# 科研设备需求源
# ============================================================
DEMAND_SOURCES = [
    {
        "name": "中国政府采购网-仪器设备招标",
        "url": "http://www.ccgp.gov.cn/cggg/dfgg/",
        "type": "demand",
        "label": "政府采购仪器设备招标",
    },
    {
        "name": "中国招标投标公共服务平台",
        "url": "http://www.cebpubservice.com/",
        "type": "demand",
        "label": "招标投标-仪器设备",
    },
]

# ============================================================
# 科研设备供应商/服务商源
# ============================================================
SUPPLIER_SOURCES = [
    {
        "name": "SelectScience国际科学仪器",
        "url": "https://www.selectscience.net/products/",
        "type": "supplier",
        "label": "SelectScience科学仪器",
    },
    {
        "name": "中国计量院校准服务",
        "url": "https://www.nim.ac.cn/",
        "type": "supplier", 
        "label": "中国计量院校准检测",
    },
    {
        "name": "中国分析测试协会",
        "url": "https://www.caia.org.cn/",
        "type": "supplier",
        "label": "分析测试协会",
    },
    {
        "name": "LabWrench实验室设备",
        "url": "https://www.labwrench.com/",
        "type": "supplier",
        "label": "LabWrench设备目录",
    },
]

# ============================================================
# 科学仪器关键词
# ============================================================
SCIENTIFIC_INSTRUMENTS = [
    "显微镜", "光谱仪", "质谱仪", "色谱仪", "离心机", "PCR仪", "测序仪",
    "流式细胞仪", "酶标仪", "冻干机", "培养箱", "超净台", "生物安全柜",
    "HPLC", "LC-MS", "GC-MS", "NMR", "XRD", "SEM", "TEM", "AFM",
    "spectrometer", "microscope", "chromatography", "centrifuge",
    "spectrophotometer", "analyzer", "detector", "sensor",
    "实验仪器", "科研设备", "检测设备", "分析仪器", "实验设备",
    "仪器仪表", "实验室设备", "教学仪器",
]

# 实验器材/科学仪器企业关键词
EQUIPMENT_CATEGORIES = {
    "分析仪器": ["光谱", "质谱", "色谱", "波谱", "元素分析", "analyzer", "spectrometer"],
    "光学仪器": ["显微镜", "望远镜", "光学", "imaging", "microscope", "lens"],
    "生命科学仪器": ["PCR", "测序", "流式", "酶标", "培养", "离心", "bio", "culture"],
    "物性测试": ["硬度", "拉力", "冲击", "热分析", "流变", "粒度", "test"],
    "实验室设备": ["离心机", "培养箱", "超净台", "安全柜", "冻干", "灭菌", "autoclave"],
    "测量仪器": ["传感器", "校准", "计量", "检测", "measure", "meter", "gauge"],
    "电子测量": ["示波器", "信号", "频谱", "网络分析", "oscilloscope", "multimeter"],
    "试剂/耗材": ["试剂", "耗材", "标准品", "抗体", "reagent", "consumable"],
}

DEMAND_KEYWORDS = [
    "采购", "招标", "竞争性谈判", "询价", "公开招标", "采购公告",
    "购置", "采购项目", "设备采购", "仪器采购",
    "procurement", "purchase", "solicitation", "bid",
]

NAV_SKIP = ["login", "register", "sign", "password", "copyright", "beian",
            "privacy", "terms", "cookie", "sitemap", "javascript:", "mailto:"]

# ============================================================
# 提取器
# ============================================================

def fetch(url, timeout=15):
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/json,*/*",
        })
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception as e:
        return ""


def extract_generic_links(html):
    """提取页面中的链接，过滤导航/页脚"""
    items = []
    pattern = r'href="([^"]+)"[^>]*>([^<]{10,200})</a>'
    for path, title in re.findall(pattern, html):
        t = title.strip()
        tl = t.lower()
        if not t or len(t) < 10: continue
        if any(s in path.lower() for s in NAV_SKIP): continue
        if any(s in tl for s in ["copyright", "icp", "beian", "privacy", "terms"]): continue
        items.append((path, t))
    return items


def extract_selectscience_suppliers(html):
    """从SelectScience提取科学仪器品牌/供应商"""
    suppliers = set()
    # 提取产品分类链接中的名称
    links = re.findall(r'href="([^"]*)"[^>]*>([A-Z][A-Za-z0-9 /&-]{3,80})</a>', html)
    for path, name in links:
        name = name.strip()
        nl = name.lower()
        if len(name) < 3 or len(name) > 60: continue
        if any(s in nl for s in ["privacy", "terms", "cookie", "sign in", "register",
                                  "all content", "news &", "events", "join free",
                                  "login", "create account", "quick order",
                                  "website navigation", "learn more", "need support"]):
            continue
        # 只保留看起来像公司/品牌名的条目
        if name[0].isupper() and len(name) > 3:
            suppliers.add(name)
        # 也从URL提取看起来像公司名的
        if "/suppliers/" in path.lower() or "/brands/" in path.lower():
            parts = path.strip("/").split("/")
            if parts:
                brand = parts[-1].replace("-", " ").replace("_", " ").title()
                if len(brand) > 2:
                    suppliers.add(brand)
    return list(suppliers)[:50]


def extract_ccgp_demands(html):
    """从中国政府采购网提取采购需求"""
    demands = []
    links = re.findall(r'href="([^"]+)"[^>]*>([^<]{15,150})</a>', html)
    for path, title in links:
        t = title.strip()
        tl = t.lower()
        if any(s in tl for s in ["copyright", "beian", "icp", "cookie", "privacy"]): continue
        if any(s in tl for s in NAV_SKIP): continue
        # 只保留含科研设备关键词的
        is_sci = any(kw in t for kw in ["仪器", "设备", "实验", "检测", "测试", "试剂", "耗材", "分析"])
        if is_sci:
            url = path if path.startswith("http") else f"http://www.ccgp.gov.cn{path}" if path.startswith("/") else path
            demands.append({"title": t, "url": url})
    return demands


def classify_equipment(text):
    """把文本分类到仪器类别"""
    tl = text.lower()
    for cat, kws in EQUIPMENT_CATEGORIES.items():
        if any(kw in tl for kw in kws):
            return cat
    return "其他仪器"


def classify_demand_category(text):
    """分类需求到技术领域"""
    tl = text.lower()
    areas = {
        "分析测试": ["光谱", "色谱", "质谱", "元素分析", "成分", "含量", "浓度"],
        "生命科学": ["PCR", "细胞", "基因", "蛋白", "生物", "细菌", "病毒", "培养"],
        "材料表征": ["SEM", "TEM", "XRD", "XPS", "热分析", "力学", "硬度", "拉伸"],
        "环境监测": ["水质", "大气", "土壤", "污染", "排放", "VOC", "颗粒"],
        "电子测量": ["示波器", "信号", "频谱", "阻抗", "网络分析"],
    }
    for area, kws in areas.items():
        if any(kw in tl for kw in kws):
            return area
    return "通用实验设备"


# ============================================================
# 入库
# ============================================================
def api_post(path, payload):
    data = json.dumps(payload).encode("utf-8")
    try:
        req = urllib.request.Request(f"{API_BASE}{path}", data=data,
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:100]
        return {"status": "error", "code": e.code, "body": body}
    except Exception as e:
        return {"status": "error", "reason": str(e)[:80]}


def insert_demand(item):
    """入库一条科研设备采购需求"""
    return api_post("/api/auto-demand", {
        "raw_text": item["title"],
        "category": item.get("category", "其他"),
        "email": "crawler",
        "source": item.get("source", "科研设备采购"),
        "source_url": item.get("url", ""),
    })


def insert_supplier(item):
    """入库一家科学仪器供应商/服务商"""
    payload = {
        "email": "crawler",
        "profile_type": "COMPANY",
        "country": item.get("country", ""),
        "trust_score": item.get("trust_score", 0.5),
        "agent_card": {
            "name": item["name"],
            "description": item.get("description", "")[:300],
            "category": item.get("category", "其他"),
            "industry": "科学仪器/实验设备",
            "discipline": item.get("discipline", ""),
            "skills": item.get("skills", []),
            "process": item.get("process", []),
            "url": item.get("url", ""),
            "contact": item.get("contact", {}),
        }
    }
    return api_post("/api/auto-supplier", payload)


# ============================================================
# 爬取流程
# ============================================================
def crawl_demands(dry_run=False):
    """爬取科研设备采购需求"""
    print(f"\n{'='*60}")
    print("  科研设备采购需求采集")
    print(f"{'='*60}")
    total = 0

    for src in DEMAND_SOURCES:
        print(f"\n  📋 {src['label']}")
        html = fetch(src["url"])
        if not html:
            print(f"     ❌ 获取失败")
            continue
        
        if "ccgp" in src["url"]:
            items = extract_ccgp_demands(html)
            print(f"     → 找到 {len(items)} 条采购信息")
        else:
            links = extract_generic_links(html)
            items = []
            for path, title in links:
                if any(kw in title for kw in ["仪器", "设备", "实验", "检测", "招标", "采购"]):
                    url = path if path.startswith("http") else (
                        f"http://www.cebpubservice.com{path}" if path.startswith("/") else path
                    )
                    items.append({"title": title, "url": url, "source": src["label"]})
            print(f"     → 找到 {len(items)} 条（过滤后）")

        for item in items[:30]:
            item["source"] = src["label"]
            item["category"] = classify_demand_category(item["title"])
            print(f"       [{item['category']}] {item['title'][:50]}")
            if not dry_run:
                r = insert_demand(item)
                if r.get("status") == "ok":
                    total += 1
                    print(f"         ✅ 入库")
                elif r.get("status") == "dup":
                    print(f"         ⏭ 重复")
                else:
                    print(f"         ❌ {r.get('code', '')} {r.get('reason','')[:30]}")

    return total


def crawl_suppliers(dry_run=False):
    """爬取科学仪器供应商"""
    print(f"\n{'='*60}")
    print("  科学仪器/实验设备供应商采集")
    print(f"{'='*60}")
    total = 0

    for src in SUPPLIER_SOURCES:
        print(f"\n  🏢 {src['label']}")
        html = fetch(src["url"])
        if not html:
            print(f"     ❌ 获取失败")
            continue
        
        companies = []

        if "selectscience" in src["url"]:
            names = extract_selectscience_suppliers(html)
            for name in names:
                companies.append({
                    "name": name,
                    "description": "科学仪器/实验室设备供应商",
                    "category": classify_equipment(name),
                    "country": "国际",
                    "discipline": "仪器科学与技术",
                    "skills": ["科学仪器供应", "实验室设备"],
                    "trust_score": 0.5,
                    "url": "",
                })
            print(f"     → 提取 {len(companies)} 个品牌/供应商")

        elif "nim.ac.cn" in src["url"]:
            links = extract_generic_links(html)
            for path, title in links:
                if any(kw in title for kw in ["计量", "校准", "检测", "测试", "标准", "测量"]):
                    if len(title) > 5:
                        companies.append({
                            "name": f"中国计量院 - {title.strip()[:30]}",
                            "description": title.strip()[:200],
                            "category": "测量仪器",
                            "country": "中国",
                            "discipline": "计量学",
                            "skills": ["计量校准", "检测服务", "标准制定"],
                            "trust_score": 0.7,
                            "url": path if path.startswith("http") else f"https://www.nim.ac.cn{path}" if path.startswith("/") else "",
                        })
            print(f"     → 提取 {len(companies)} 个计量校准服务")

        elif "caia.org.cn" in src["url"]:
            links = extract_generic_links(html)
            for path, title in links:
                if any(kw in title for kw in ["分析", "测试", "仪器", "检测", "实验室", "委员会"]):
                    companies.append({
                        "name": f"中国分析测试 - {title.strip()[:30]}",
                        "description": title.strip()[:200],
                        "category": "分析仪器",
                        "country": "中国",
                        "discipline": "分析化学",
                        "skills": ["分析测试服务", "仪器共享", "技术咨询"],
                        "trust_score": 0.6,
                        "url": path if path.startswith("http") else f"https://www.caia.org.cn{path}" if path.startswith("/") else "",
                    })
            print(f"     → 提取 {len(companies)} 个分析测试机构")

        elif "labwrench" in src["url"]:
            links = extract_generic_links(html)
            for path, title in links:
                if len(title) > 8 and title[0].isupper() and not any(s in title.lower() for s in ["home", "about", "contact", "login", "register"]):
                    companies.append({
                        "name": title.strip()[:40],
                        "description": "实验室设备供应商",
                        "category": classify_equipment(title),
                        "country": "国际",
                        "discipline": "仪器科学与技术",
                        "skills": ["实验室设备", "仪器维护"],
                        "trust_score": 0.4,
                        "url": path if path.startswith("http") else f"https://www.labwrench.com{path}" if path.startswith("/") else "",
                    })
            print(f"     → 提取 {len(companies)} 个设备类别/品牌")

        for c in companies[:40]:
            print(f"       [{c['category']}] {c['name'][:45]}")
            if not dry_run:
                r = insert_supplier(c)
                if r.get("status") == "ok":
                    total += 1
                    print(f"         ✅")
                elif r.get("status") == "dup":
                    print(f"         ⏭ 重复")
                else:
                    print(f"         ❌ {r.get('code', '')}")

    return total


# ============================================================
# Main
# ============================================================
def run(dry_run=False):
    print(f"{'='*60}")
    print(f"  科研设备专用爬虫")
    print(f"  时间: {datetime.now().isoformat()}")
    print(f"  模式: {'试跑(不入库)' if dry_run else '正式入库'}")
    print(f"{'='*60}")

    d_count = crawl_demands(dry_run)
    s_count = crawl_suppliers(dry_run)

    print(f"\n{'='*60}")
    print(f"  采集完成!")
    print(f"  需求(设备采购): {d_count} 条")
    print(f"  供应商(仪器厂商): {s_count} 家")
    print(f"{'='*60}")

    # 保存备份
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    if not dry_run:
        print(f"\n  备份文件: sci_equip_crawl_{ts}.json")


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    run(dry_run=dry)


