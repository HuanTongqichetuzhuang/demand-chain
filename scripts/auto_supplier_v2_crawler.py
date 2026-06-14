#!/usr/bin/env python3
"""
需求链平台 — 供应商深度爬虫 v2
自动从多个公开渠道搜索真实供应商，提取完整信息（行业、学科、工艺、联系方式）。

核心改进 v2:
1. 多渠道搜索: 企业标准平台、政府采购中标、高新企业名录、行业白皮书
2. DeepSeek AI 结构化: 提取行业、学科、工艺、技能、TRL等级
3. 联系方式发现: 查找公司网站 → 抽取邮箱/电话
4. 定时自动运行: 支持 --schedule 参数（配合WorkBuddy自动化）

用法:
  python scripts/auto_supplier_v2_crawler.py              # 跑一次
  python scripts/auto_supplier_v2_crawler.py --dry-run     # 试跑不入库
"""
import hashlib, json, re, sys, time, urllib.request, urllib.error, traceback
from datetime import datetime

# ============================================================
# Config
# ============================================================
API_BASE = "http://8.154.26.92:8080"
FIRECRAWL_KEY = "fc-e97094049296412bb87cc3946d515649"
DEEPSEEK_KEY = "sk-c32415bb5ae44cdc844f1b95f99e4544"

# ============================================================
# AI 结构化 Prompt — 提取供应商完整信息
# ============================================================
SUPPLIER_PROMPT = """分析以下文本，判断是否是一家真实的企业/研究机构/供应商。输出JSON。

如果是真实的供应商:
{
  "is_supplier": true,
  "name": "企业/机构名称",
  "description": "100字内业务描述，突出核心能力",
  "industry": "所属行业（如：动力电池、航空航天、生物医药、半导体、智能制造等）",
  "discipline": "涉及的科学学科（如：材料科学与工程、物理学/电磁学、计算机科学/AI等）",
  "skills": ["核心技术能力1", "核心技术能力2", "核心技术能力3"],
  "process": ["涉及的制造工艺或技术流程1", "工艺2", "工艺3"],
  "trl": 0-9的数字（技术就绪等级: 1-3研究级, 4-6开发级, 7-9产品级）,
  "url": "官方网站链接(如果有)",
  "country": "所在国家"
}

如果不是:
{"is_supplier": false, "reason": "原因"}

规则:
- 导航链接、广告、列表页导航不是供应商
- 真实供应商应有: 具体业务描述、产品/服务、技术能力
- 如果文本明显是多家公司的列表，挑其中最重点的公司输出
- 输出纯JSON，无其他文字"""


# ============================================================
# 搜索词 — 精准搜索真实公司/供应商
# ============================================================
SUPPLIER_QUERIES = [
    # === 采招网中标企业（已验证有效）===
    'site:bidcenter.com.cn 传感器 中标 公司',
    'site:bidcenter.com.cn 新材料 中标 公司',
    'site:bidcenter.com.cn 智能制造 中标 公司',
    'site:bidcenter.com.cn 生物医药 中标 公司',
    'site:bidcenter.com.cn 半导体 中标 公司',
    'site:bidcenter.com.cn 机器人 中标 公司',
    'site:bidcenter.com.cn 新能源 中标 公司',

    # === 制造商/供应商名录 ===
    'site:cn.made-in-china.com 传感器 manufacturer company profile',
    'site:cn.made-in-china.com 半导体 芯片 公司',
    'site:cn.made-in-china.com 机器人 自动化 公司',
    'site:cn.made-in-china.com 新材料 复合材料 公司',
    'site:cn.made-in-china.com 生物科技 医疗 公司',

    # === 国际供应商 ===
    'site:crunchbase.com "sensor" "company" 2025',
    'site:crunchbase.com "robotics" "manufacturing" 2025',
    'site:crunchbase.com "clean energy" "technology" 2025',

    # === 政府采购中标（SBIR等）===
    'site:sbir.gov award company sensor OR AI OR manufacturing 2025',
    'site:grants.gov "award" "small business" sensor 2025',

    # === B2B平台 ===
    'site:globalsources.com sensor manufacturer',
    'site:thomasnet.com sensor supplier manufacturer',
]


# ============================================================
# HTTP 工具函数
# ============================================================
def http_post(url, payload, headers=None, timeout=30):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers or {}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:200]
        return {"error": f"HTTP {e.code}: {body}"}
    except Exception as e:
        return {"error": str(e)}


def firecrawl_search(query, limit=5, page_content=False):
    """Firecrawl 搜索 + 内容抓取"""
    try:
        opts = {"formats": ["markdown"], "onlyMainContent": True}
        result = http_post(
            "https://api.firecrawl.dev/v1/search",
            {"query": query, "limit": min(limit, 5),
             "scrapeOptions": opts},
            {"Authorization": f"Bearer {FIRECRAWL_KEY}", "Content-Type": "application/json"},
        )
        if result.get("success"):
            return [{"url": i.get("url",""), "title": i.get("title",""),
                     "content": (i.get("markdown","") or i.get("description",""))[:4000]}
                    for i in result.get("data", [])]
    except Exception as e:
        print(f"  [Firecrawl Error] {e}")
    return []


def firecrawl_scrape(url):
    """抓取单页内容"""
    try:
        result = http_post(
            "https://api.firecrawl.dev/v1/scrape",
            {"url": url, "formats": ["markdown"], "onlyMainContent": True},
            {"Authorization": f"Bearer {FIRECRAWL_KEY}", "Content-Type": "application/json"},
        )
        if result.get("success"):
            d = result.get("data", {})
            meta = d.get("metadata", {}) or {}
            return {"url": url, "title": meta.get("title", ""),
                    "content": d.get("markdown", "")[:5000]}
    except Exception as e:
        print(f"  [Scrape Error] {e}")
    return {"url": url, "title": "", "content": ""}


def deepseek_analyze(text, prompt=SUPPLIER_PROMPT):
    """DeepSeek AI 分析内容"""
    try:
        result = http_post(
            "https://api.deepseek.com/v1/chat/completions",
            {"model": "deepseek-chat", "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": text[:4000]},
            ], "temperature": 0.05, "max_tokens": 1024},
            {"Authorization": f"Bearer {DEEPSEEK_KEY}", "Content-Type": "application/json"},
        )
        if "error" in result:
            return {"is_supplier": None, "reason": result["error"][:60]}
        content = result["choices"][0]["message"]["content"].strip()
        content = content[content.find("{"):content.rfind("}")+1] if "{" in content else content
        return json.loads(content)
    except Exception as e:
        return {"is_supplier": None, "reason": str(e)[:60]}


def google_search_contact(company_name):
    """搜索公司联系方式"""
    query = f'{company_name} 联系方式 email OR 邮箱 OR 联系电话'
    items = firecrawl_search(query, limit=2)
    emails = []
    phones = []
    website = ""
    for item in items:
        text = item.get("content", "") + " " + item.get("title", "")
        # 提取邮箱
        emails.extend(re.findall(r'[\w.+-]+@[\w-]+\.[\w.-]+', text))
        # 提取电话
        phones.extend(re.findall(r'\+?86[\s-]?\d{3,4}[\s-]?\d{7,8}', text))
        phones.extend(re.findall(r'0\d{2,3}[\s-]?\d{7,8}', text))
        # 提取网站
        urls = re.findall(r'https?://(?:www\.)?[\w-]+\.(?:com|cn|net|org)[\w/.-]*', text)
        if urls and not website:
            website = urls[0]
    contact = {}
    if emails:
        contact["email"] = emails[0].lower()
    if phones:
        contact["phone"] = phones[0]
    if website:
        contact["website"] = website
    return contact


def extract_contact_from_website(website_url):
    """从公司网站提取联系信息"""
    page = firecrawl_scrape(website_url)
    text = page.get("content", "") + " " + page.get("title", "")
    emails = re.findall(r'[\w.+-]+@[\w-]+\.[\w.-]+', text)
    phones = re.findall(r'\+?86[\s-]?\d{3,4}[\s-]?\d{7,8}', text)
    phones.extend(re.findall(r'0\d{2,3}[\s-]?\d{7,8}', text))
    contact = {}
    if emails:
        contact["email"] = emails[0].lower()
    if phones:
        contact["phone"] = phones[0]
    if website_url:
        contact["website"] = website_url
    return contact


# ============================================================
# 供应商入库
# ============================================================
def insert_supplier(supplier):
    """构造完整 supplier 对象并入库"""
    name = supplier.get("name", "").strip()
    if not name or len(name) < 2:
        return {"status": "skip", "reason": "empty name"}

    agent_card = {
        "name": name,
        "description": (supplier.get("description") or "")[:500],
        "category": supplier.get("category", "其他"),
        "industry": supplier.get("industry", ""),
        "discipline": supplier.get("discipline", ""),
        "trl": supplier.get("trl", 0),
        "url": supplier.get("url", ""),
        "skills": supplier.get("skills", []),
        "process": supplier.get("process", []),
        "contact": supplier.get("contact", {}),
    }

    payload = {
        "email": "crawler",
        "profile_type": supplier.get("profile_type", "COMPANY"),
        "country": supplier.get("country", "中国"),
        "trust_score": supplier.get("trust_score", 0.5),
        "agent_card": agent_card,
    }

    result = http_post(
        f"{API_BASE}/api/auto-supplier",
        payload,
        {"Content-Type": "application/json"},
        timeout=10,
    )
    return result


def fingerprint(text):
    return hashlib.md5(text.encode("utf-8", errors="replace")).hexdigest()[:12]


# ============================================================
# 分类
# ============================================================
CATEGORY_KEYWORDS = {
    "人工智能": ["ai", "artificial intelligence", "machine learning", "deep learning", "llm", "大模型", "神经网络", "计算机视觉", "自然语言"],
    "生物医药": ["drug", "diagnostic", "medical", "clinical", "therapeutic", "vaccine", "基因", "药物", "诊断", "临床", "pharmaceutical", "healthcare"],
    "新能源": ["solar", "photovoltaic", "wind", "hydrogen", "battery", "energy storage", "光伏", "风电", "氢能", "储能", "钙钛矿", "clean energy", "renewable"],
    "环境工程": ["carbon capture", "water treatment", "wastewater", "recycling", "碳捕集", "废水", "climate", "emission", "sustainability"],
    "材料科学": ["material", "polymer", "composite", "nanomaterial", "coating", "alloy", "ceramic", "材料", "高分子", "复合材料", "涂层", "纳米"],
    "航空航天": ["aerospace", "satellite", "propulsion", "drone", "uav", "aviation", "航天", "卫星", "无人机", "推进", "航空"],
    "机器人与智能系统": ["robot", "autonomous", "robotics", "slam", "机器人", "自主导航", "无人系统", "agv"],
    "信息技术": ["blockchain", "quantum", "cybersecurity", "software", "digital", "区块链", "量子", "网络安全", "软件", "隐私计算"],
    "传感器技术": ["sensor", "detector", "mems", "lidar", "radar", "传感器", "检测", "陀螺", "惯性"],
    "电子科学与技术": ["semiconductor", "chip", "ic", "ga", "sic", "optoelectronic", "半导体", "芯片", "集成电路", "光电"],
    "化学工程": ["chemical", "catalyst", "synthesis", "ammonia", "化工", "催化剂", "合成", "反应器"],
    "生物技术": ["biotech", "crispr", "gene", "genome", "synthetic biology", "生物技术", "基因编辑", "合成生物"],
    "交通运输": ["transport", "logistics", "electric vehicle", "ev", "交通", "物流", "电动车"],
    "海洋科学": ["ocean", "marine", "seawater", "海洋", "海水", "渔业"],
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
def save_backup(name, data, suffix=""):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    fname = f"supplier_backup_{name}_{ts}{suffix}.json"
    try:
        with open(fname, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"  备份: {fname}")
    except:
        print(f"  备份写入失败: {fname}")


# ============================================================
# 核心爬取流程
# ============================================================
def crawl_suppliers(dry_run=False):
    """
    主流程:
    1. Firecrawl搜索 → 候选URL
    2. Firecrawl抓取 → 页面内容
    3. DeepSeek AI分析 → 结构化数据
    4. 联系方式发现 → 搜索网站+提取邮箱
    5. 入库
    """
    stats = {"ok": 0, "dup": 0, "fail": 0, "skip": 0}
    seen_urls = set()
    all_discovered = []

    print("\n" + "=" * 70)
    print("【供应商深度爬取】搜索 → AI分析 → 联系方式发现 → 入库")
    print("=" * 70)

    for q_idx, query in enumerate(SUPPLIER_QUERIES):
        print(f"\n[{q_idx+1}/{len(SUPPLIER_QUERIES)}] 搜索: {query[:80]}...")
        items = firecrawl_search(query, limit=4)
        print(f"  → {len(items)} 个结果")

        for item in items:
            url = item.get("url", "")
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)

            title = item.get("title", "")[:80]
            frag = item.get("content", "")[:2000]

            if len(title) < 4 and len(frag) < 100:
                print(f"  ⏭ 跳过(内容太少): {title}")
                continue

            print(f"\n  📄 {title}")
            print(f"     {url[:80]}")

            # Step 1: DeepSeek AI 分析
            text_to_analyze = f"TITLE: {title}\n\nCONTENT: {frag}"
            result = deepseek_analyze(text_to_analyze)

            if not result.get("is_supplier"):
                # 重新抓取完整页面内容再分析
                print(f"     ↻ 首次分析未识别，深抓页面...")
                page = firecrawl_scrape(url)
                text2 = f"TITLE: {page['title']}\n\nCONTENT: {page['content'][:4000]}"
                result = deepseek_analyze(text2)
                if result.get("is_supplier"):
                    # 结果中补充url
                    if not result.get("url"):
                        result["url"] = url
                else:
                    print(f"     ❌ 未识别为供应商: {result.get('reason','?')[:40]}")
                    continue

            # Step 2: 构建供应商信息
            supplier = {
                "name": result.get("name", title).strip(),
                "description": result.get("description", ""),
                "industry": result.get("industry", ""),
                "discipline": result.get("discipline", ""),
                "skills": result.get("skills", []),
                "process": result.get("process", []),
                "trl": result.get("trl", 0),
                "url": result.get("url", url),
                "country": result.get("country", "中国"),
                "profile_type": "COMPANY",
                "trust_score": 0.5,
            }

            # 分类
            desc_text = f"{supplier['description']} {supplier['industry']} {supplier['discipline']} {' '.join(supplier['skills'])}"
            supplier["category"] = classify(desc_text)

            # Step 3: 发现联系方式
            print(f"     🔍 查找联系方式...")
            contact = {}
            # 先搜公司名
            contact = google_search_contact(supplier["name"])
            # 如果有网站，再从网站提取
            if supplier.get("url") and "google.com" not in supplier["url"]:
                site_contact = extract_contact_from_website(supplier["url"])
                contact.update({k: v for k, v in site_contact.items() if v})
            supplier["contact"] = contact

            # Step 4: 展示结果
            has_email = "✅" if contact.get("email") else "❌"
            has_phone = "✅" if contact.get("phone") else "❌"
            has_web = "✅" if contact.get("website") or supplier.get("url") else "❌"
            print(f"     ✅ 识别: {supplier['name'][:40]}")
            print(f"       行业: {supplier['industry'][:20]} | 学科: {supplier['discipline'][:20]}")
            print(f"       技能: {supplier['skills'][:3]}")
            print(f"       工艺: {supplier['process'][:3]}")
            print(f"       联系方式: 邮箱{has_email} 电话{has_phone} 网站{has_web}")
            print(f"       TRL: {supplier['trl']}")

            all_discovered.append(supplier)

            # Step 5: 入库
            if not dry_run:
                r = insert_supplier(supplier)
                status = r.get("status", "error") if isinstance(r, dict) else "error"
                if status == "ok":
                    stats["ok"] += 1
                    print(f"     💾 入库成功")
                elif status == "dup":
                    stats["dup"] += 1
                    print(f"     ⏭ 已存在(跳过)")
                else:
                    stats["fail"] += 1
                    print(f"     ❌ 入库失败: {r}")
            else:
                print(f"     🏃 试跑模式(不入库)")

            time.sleep(2)  # 避免API限流

        time.sleep(3)  # 查询间间隔

    if all_discovered:
        save_backup("suppliers", all_discovered)
    if not dry_run and all_discovered:
        save_backup("suppliers_result", stats, suffix="_stats")

    print(f"\n{'=' * 70}")
    print(f"爬取完成!")
    print(f"  发现: {len(all_discovered)} 个供应商")
    if not dry_run:
        print(f"  入库: {stats['ok']} 新 | {stats['dup']} 重复 | {stats['fail']} 失败 | {stats['skip']} 跳过")
    print(f"{'=' * 70}")
    return stats


# ============================================================
# 清理低质量供应商（联网后调用）
# ============================================================
def cleanup_low_quality():
    """清理数据库中描述为空或技能为空的供应商"""
    print("\n清理低质量供应商...")
    import urllib.request, json
    try:
        req = urllib.request.Request(f"{API_BASE}/api/suppliers")
        with urllib.request.urlopen(req, timeout=10) as resp:
            suppliers = json.loads(resp.read().decode("utf-8"))

        # 标记需要删除的供应商
        to_delete = []
        for s in suppliers:
            if not s.get("skills") and not s.get("description"):
                to_delete.append(s["name"])
                print(f"  标记删除: {s['name']}")

        if to_delete:
            print(f"\n共 {len(to_delete)} 个低质量供应商需要清理")
            print("可通过 ssh 执行: docker exec dc-db psql -U dc -d demand_chain -c \"DELETE FROM capability_profiles WHERE agent_card_json->>'name' IN ('"+"','".join(to_delete)+"');\"")
        else:
            print("✅ 数据库中没有低质量供应商")

        return to_delete
    except Exception as e:
        print(f"  清理失败: {e}")
        return []


# ============================================================
# Main
# ============================================================
def run(dry_run=False, cleanup=False):
    print(f"=== 需求链 供应商深度爬虫 v2 ===")
    print(f"时间: {datetime.now().isoformat()}")
    print(f"模式: {'试跑(不入库)' if dry_run else '正式入库'}")
    print(f"API: {API_BASE}")
    print(f"Firecrawl Key: {FIRECRAWL_KEY[:12]}...{FIRECRAWL_KEY[-4:]}")
    print(f"DeepSeek Key: {DEEPSEEK_KEY[:12]}...{DEEPSEEK_KEY[-4:]}")

    if cleanup:
        cleanup_low_quality()

    stats = crawl_suppliers(dry_run=dry_run)

    print(f"\nDone. {datetime.now().isoformat()}")


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    clean = "--cleanup" in sys.argv
    run(dry_run=dry, cleanup=clean)
