#!/usr/bin/env python3
"""
需求链平台 — 供应商深度爬虫 v3 (无Firecrawl依赖)
============================================
自动从多个公开渠道搜索真实供应商，提取完整信息。

数据来源:
1. GitHub API (免费, 搜索仓库→提取组织)
2. 直接HTTP请求 (可访问的公开网站)
3. DeepSeek AI 结构化提取

用法:
  python3 auto_supplier_v3_crawler.py                # 正式运行
  python3 auto_supplier_v3_crawler.py --dry-run       # 试跑不入库
  python3 auto_supplier_v3_crawler.py --limit=5       # 每源最多5条
"""
import json, re, sys, time, traceback, os
from datetime import datetime

try:
    import requests
except ImportError:
    print("Error: requests not installed. Run: pip install requests")
    sys.exit(1)

# ============================================================
# Config
# ============================================================
API_BASE = "http://demand-chain.duckdns.org:8080"
DEEPSEEK_KEY = "sk-c32415bb5ae44cdc844f1b95f99e4544"
RESULTS_DIR = "supplier_backups"

os.makedirs(RESULTS_DIR, exist_ok=True)

# ============================================================
# 搜索词配置
# ============================================================
GITHUB_TOPIC_QUERIES = [
    # 中文科技企业（GitHub组织）
    ('传感器技术', 'sensor stars:>50'),
    ('机器人与智能系统', 'robotics stars:>50'),
    ('人工智能', 'artificial-intelligence stars:>50'),
    ('新能源', 'renewable-energy stars:>50'),
    ('生物医药', 'bioinformatics stars:>50'),
    ('材料科学', 'materials-science stars:>50'),
    ('电子科学与技术', 'semiconductor stars:>50'),
    ('航空航天', 'aerospace stars:>50'),
    ('环境工程', 'environmental-engineering stars:>50'),
    ('化学工程', 'chemical-engineering stars:>50'),
    ('信息技术', 'cybersecurity stars:>50'),
    ('农业科学', 'agriculture-technology stars:>50'),
    # 新增：更多细分领域
    ('量子计算', 'quantum-computing stars:>30'),
    ('自动驾驶', 'autonomous-driving stars:>50'),
    ('储能技术', 'energy-storage stars:>30'),
    ('碳捕集', 'carbon-capture stars:>20'),
    ('合成生物学', 'synthetic-biology stars:>20'),
    ('脑机接口', 'brain-computer-interface stars:>20'),
    ('6G通信', '6g stars:>30'),
    ('边缘计算', 'edge-computing stars:>50'),
    ('生物信息学', 'bioinformatics stars:>50'),
    ('智能电网', 'smart-grid stars:>30'),
    # === 新增：科学仪器/实验设备领域 ===
    ('科学仪器', 'scientific-instrumentation stars:>10'),
    ('实验室设备', 'laboratory-equipment stars:>10'),
    ('生物仪器', 'bioinstrumentation stars:>10'),
    ('分析仪器', 'analytical-chemistry stars:>20'),
    ('光学仪器', 'optical-instrument stars:>10'),
    ('传感器设计', 'sensor-design stars:>20'),
    ('微流控', 'microfluidics stars:>20'),
    ('质谱技术', 'mass-spectrometry stars:>10'),
    ('显微镜技术', 'microscopy stars:>30'),
    ('光谱技术', 'spectroscopy stars:>20'),
    ('测量计量', 'metrology stars:>10'),
]

DIRECT_SCRAPE_URLS = [
    # 已知可访问的公开数据源
    ('中国科学院', 'http://www.cas.cn/zz/kyjg/'),
    # 中国主要科研机构
    ('中科院深圳先进院', 'https://www.siat.ac.cn/'),
    ('北京航空航天大学科研', 'https://www.buaa.edu.cn/'),
    ('清华大学技术转移', 'https://www.tsinghua.edu.cn/'),
    ('浙江大学科研', 'https://www.zju.edu.cn/'),
    ('上海交大科研', 'https://www.sjtu.edu.cn/'),
    # 美国能源部国家实验室
    ('MIT Media Lab', 'https://www.media.mit.edu/'),
    ('Stanford Research', 'https://www.stanford.edu/'),
]

# ============================================================
# HTTP 工具
# ============================================================
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

def http_get(url, timeout=10, params=None):
    try:
        r = requests.get(url, params=params, timeout=timeout, headers=HEADERS)
        return r
    except Exception as e:
        return None


def deepseek_extract(company_name, context_text=""):
    """用DeepSeek提取供应商结构化信息"""
    text = context_text.strip() or company_name
    try:
        r = requests.post("https://api.deepseek.com/v1/chat/completions",
            json={
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": """你是一个专业的供应商信息提取器。分析以下文本，提取企业/机构的详细信息。

输出必须是纯JSON，格式如下:
{
  "name": "企业/机构完整名称",
  "industry": "所属行业（如：动力电池、航空航天、生物医药、半导体、智能制造、人工智能、物联网、环境工程等）",
  "discipline": "涉及的科学学科（如：材料科学与工程、物理学/电磁学、计算机科学/AI、控制科学、机械工程、化学工程等）",
  "description": "50-100字的中文业务描述，突出核心技术和能力",
  "skills": ["核心技术能力1", "核心技术能力2", "核心技术能力3", "核心技术能力4"],
  "process": ["涉及的制造或研发工艺1", "工艺2", "工艺3"],
  "trl": 数字(1-3研究级,4-6开发级,7-9产品级)
}

规则：
- 如果文本信息不完整，根据公司名称和已知行业知识合理推断
- industry和discipline必须有值，不能为空
- skills和process至少各2项
- 输出纯JSON，不要其他文字"""},
                    {"role": "user", "content": text[:3000]}
                ],
                "temperature": 0.05,
                "max_tokens": 800
            },
            headers={"Authorization": f"Bearer {DEEPSEEK_KEY}"},
            timeout=20)
        if r.status_code == 200:
            content = r.json()["choices"][0]["message"]["content"].strip()
            # 提取JSON部分
            start = content.find("{")
            end = content.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(content[start:end])
            else:
                return {"error": "no JSON in response", "raw": content[:100]}
        else:
            return {"error": f"API status {r.status_code}"}
    except Exception as e:
        return {"error": str(e)[:100]}


def insert_supplier(supplier):
    """入库"""
    try:
        payload = {
            "email": "crawler_v3",
            "profile_type": "COMPANY",
            "country": supplier.get("country", "中国"),
            "trust_score": supplier.get("trust_score", 0.5),
            "agent_card": {
                "name": supplier["name"],
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
        }
        r = requests.post(
            f"{API_BASE}/api/auto-supplier",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10)
        if r.status_code in (200, 201):
            result = r.json()
            if result.get("status") == "ok":
                return "ok"
            elif result.get("status") == "dup":
                return "dup"
            else:
                return f"fail: {result}"
        else:
            return f"fail: HTTP {r.status_code}"
    except Exception as e:
        return f"fail: {e}"


def classify(industry, discipline, skills_text):
    """基于行业/学科/技能分类"""
    cat_map = {
        "人工智能": ["人工智能", "ai", "机器学习", "深度学习", "大模型", "自然语言", "计算机视觉", "机器人"],
        "生物医药": ["生物医药", "制药", "医疗", "临床", "基因", "诊断", "疫苗", "healthcare", "bio"],
        "新能源": ["新能源", "光伏", "风电", "氢能", "储能", "电池", "太阳能", "可再生能源", "energy"],
        "环境工程": ["环境", "碳捕集", "废水", "水处理", "回收", "climate"],
        "材料科学": ["材料", "高分子", "复合材料", "纳米", "涂层", "陶瓷", "合金", "materials"],
        "航空航天": ["航空航天", "卫星", "无人机", "推进", "航空", "航天", "aerospace"],
        "机器人与智能系统": ["机器人", "自动化", "无人系统", "slam", "导航", "robotics", "automation"],
        "信息技术": ["信息技术", "网络安全", "量子", "区块链", "软件", "平台", "通信", "security"],
        "传感器技术": ["传感器", "检测", "mems", "lidar", "radar", "陀螺", "sensor"],
        "电子科学与技术": ["半导体", "芯片", "集成电路", "光电", "电子", "semiconductor", "chip"],
        "化学工程": ["化工", "催化剂", "合成", "反应", "化学工程", "chemical"],
        "生物技术": ["生物技术", "基因编辑", "合成生物", "发酵", "crispr", "biotech"],
        "农业科学": ["农业", "作物", "养殖", "食品", "植物", "agriculture"],
        "交通运输": ["交通", "物流", "电动车", "自动驾驶", "transport"],
        "海洋科学": ["海洋", "海水", "渔业", "ocean", "marine"],
    }
    text = f"{industry} {discipline} {skills_text}".lower()
    scores = {}
    for cat, kws in cat_map.items():
        score = sum(1 for kw in kws if kw.lower() in text)
        if score > 0:
            scores[cat] = score
    if scores:
        return max(scores, key=scores.get)
    return "其他"


def fingerprint(text):
    import hashlib
    return hashlib.md5(text.encode("utf-8", errors="replace")).hexdigest()[:12]


# ============================================================
# 数据源爬虫
# ============================================================

def crawl_github_by_topic(topic_query, limit=10):
    """
    通过GitHub话题搜索组织
    策略: 搜索topic相关的高星仓库，提取组织名和描述
    """
    _, query = topic_query
    results = []
    try:
        r = requests.get(
            "https://api.github.com/search/repositories",
            params={"q": query, "per_page": min(limit, 20), "sort": "stars"},
            timeout=15,
            headers={"Accept": "application/vnd.github.v3+json", **HEADERS})
        if r.status_code != 200:
            return results

        items = r.json().get("items", [])
        seen_orgs = set()
        for item in items:
            owner = item.get("owner", {})
            login = owner.get("login", "")
            org_type = owner.get("type", "User")

            # 跳过个人用户，只保留组织
            if org_type != "Organization":
                continue
            if login in seen_orgs:
                continue
            seen_orgs.add(login)

            # 获取组织详情
            try:
                org_r = requests.get(
                    f"https://api.github.com/orgs/{login}",
                    timeout=10,
                    headers={"Accept": "application/vnd.github.v3+json", **HEADERS})
                if org_r.status_code == 200:
                    org_data = org_r.json()
                    name = org_data.get("name") or login
                    desc = org_data.get("description") or item.get("description") or ""
                    blog = org_data.get("blog", "")
                    location = org_data.get("location", "")
                    email = org_data.get("email", "")
                    avatar = org_data.get("avatar_url", "")

                    # Skip suspicious names (navigation text, list headers)
                    if is_suspicious_name(name):
                        continue

                    results.append({
                        "name": name,
                        "description": (desc or "")[:200],
                        "url": blog or f"https://github.com/{login}",
                        "country": "中国" if location and ("中国" in location or "China" in location.lower()) else "",
                        "contact": {"email": email} if email else {},
                        "source": f"github_org:{login}",
                        "location": location or "",
                    })
            except:
                continue

        return results
    except Exception as e:
        return results


def is_suspicious_name(name):
    """检查名称是否可疑（导航文字、列表标题等非真实企业名）"""
    name_lower = name.lower().strip()
    suspicious = [
        "energy startups by", "climate tech startups", "startups to watch",
        "top ", "best ", "leading ", "companies in ", "companies to watch",
        "list of ", "directory of", "ranked", "news and insights",
        "trends in ", "market overview", "technologies to watch",
        "innovations in ", "industry outlook", "global market",
        "load more", "advertising", "promote", "add startup",
        "you may also", "related posts", "sponsored",
    ]
    return any(p in name_lower for p in suspicious)


def crawl_github_by_stars(category_name, topic, limit=10):
    """
    另一种策略: 搜索中文关键词，找到相关组织的仓库
    """
    results = []
    try:
        # 用中英文混合搜索
        r = requests.get(
            "https://api.github.com/search/repositories",
            params={"q": topic, "per_page": min(limit, 15), "sort": "stars"},
            timeout=15,
            headers={"Accept": "application/vnd.github.v3+json", **HEADERS})
        if r.status_code != 200:
            return results

        items = r.json().get("items", [])
        for item in items:
            owner = item.get("owner", {})
            login = owner.get("login", "")
            if owner.get("type") != "Organization":
                continue

            desc = (item.get("description") or "")[:200]
            topics = item.get("topics", [])
            lang = item.get("language", "")
            repo_url = item.get("html_url", "")
            repo_name = item.get("name", "")

            # Skip suspicious names
            if is_suspicious_name(login):
                continue

            results.append({
                "name": login,
                "description": desc,
                "url": f"https://github.com/{login}",
                "country": "中国" if any(t in ("chinese", "china", "zh") for t in topics) else "",
                "source": f"github_repo:{login}/{repo_name}",
                "topics": topics,
                "language": lang,
            })

        return results
    except Exception as e:
        return results


def find_email_contact(company_name):
    """搜索公司联系方式"""
    try:
        # 尝试用GitHub搜索公司名的仓库
        r = requests.get(
            "https://api.github.com/search/repositories",
            params={"q": f"{company_name} in:readme email OR 联系 OR contact", "per_page": 3},
            timeout=10,
            headers={"Accept": "application/vnd.github.v3+json", **HEADERS})
        if r.status_code == 200:
            items = r.json().get("items", [])
            for item in items[:3]:
                desc = item.get("description", "") or ""
                emails = re.findall(r'[\w.+-]+@[\w-]+\.[\w.-]+', desc)
                if emails:
                    return {"email": emails[0].lower(), "github_url": item.get("html_url", "")}
    except:
        pass
    return {}


# ============================================================
# 主流程
# ============================================================

def run(dry_run=False, limit_per_source=8):
    stats = {"ok": 0, "dup": 0, "fail": 0, "skip": 0}
    total_suppliers = []

    print(f"\n{'=' * 70}")
    print(f"需求链 供应商深度爬虫 v3")
    print(f"时间: {datetime.now().isoformat()}")
    print(f"模式: {'试跑(不入库)' if dry_run else '正式入库'}")
    print(f"{'=' * 70}")

    # === Phase 1: GitHub Organization 爬取 ===
    print(f"\n{'=' * 70}")
    print("Phase 1: GitHub Organization 爬取")
    print(f"{'=' * 70}")

    for cat_name, query in GITHUB_TOPIC_QUERIES:
        print(f"\n[{cat_name}] 搜索: {query[:50]}...")
        companies = crawl_github_by_topic((cat_name, query), limit=limit_per_source)
        print(f"  → 发现 {len(companies)} 个组织")

        for company in companies:
            name = company["name"]
            print(f"\n  📄 {name[:40]}")

            # 用DeepSeek提取结构化信息
            context = f"公司名称: {name}\n描述: {company.get('description','')}\n位置: {company.get('location','')}"
            result = deepseek_extract(name, context)
            if "error" in result:
                print(f"     ❌ AI分析失败: {result['error'][:40]}")
                continue

            supplier = {
                "name": result.get("name", name),
                "description": result.get("description", ""),
                "industry": result.get("industry", ""),
                "discipline": result.get("discipline", ""),
                "skills": result.get("skills", []),
                "process": result.get("process", []),
                "trl": result.get("trl", 3),
                "url": company.get("url", ""),
                "country": company.get("country", "中国"),
                "profile_type": "COMPANY",
                "trust_score": 0.4,
                "contact": company.get("contact", {}),
            }

            # 分类
            desc_text = f"{supplier['industry']} {supplier['discipline']} {' '.join(supplier['skills'])}"
            supplier["category"] = classify(
                supplier["industry"], supplier["discipline"], desc_text)

            # 显示结果
            has_skills = "✅" if supplier["skills"] else "❌"
            has_process = "✅" if supplier["process"] else "❌"
            has_contact = "✅" if supplier["contact"] else "❌"
            print(f"     行业: {supplier['industry'][:20]}")
            print(f"     学科: {supplier['discipline'][:20]}")
            print(f"     技能: {supplier['skills'][:3]}")
            print(f"     工艺: {supplier['process'][:3]}")
            print(f"     联系方式: {has_contact}")

            total_suppliers.append(supplier)

            # 入库
            if not dry_run:
                result_status = insert_supplier(supplier)
                if result_status == "ok":
                    stats["ok"] += 1
                    print(f"     ✅ 入库成功")
                elif result_status == "dup":
                    stats["dup"] += 1
                    print(f"     ⏭ 已存在(跳过)")
                else:
                    stats["fail"] += 1
                    print(f"     ❌ 入库失败")

            # 避免GitHub API限流
            time.sleep(1.5)

        time.sleep(2)

    # === Phase 2: 备用搜索 ===
    print(f"\n{'=' * 70}")
    print("Phase 2: 补充搜索（中文关键词）")
    print(f"{'=' * 70}")

    chinese_queries = [
        ("传感器技术", "传感器 OR 检测 中国 stars:>30"),
        ("人工智能", "AI OR 人工智能 中国 stars:>30"),
        ("机器人", "机器人 OR AGV 中国 stars:>30"),
        ("半导体", "半导体 OR 芯片 中国 stars:>30"),
        ("新能源", "太阳能 OR 锂电池 中国 stars:>30"),
        ("生物医药", "基因 OR 医疗 中国 stars:>30"),
        ("材料科学", "新材料 OR 复合材料 中国 stars:>30"),
        # 新增搜索
        ("自动驾驶", "自动驾驶 OR 智能驾驶 中国 stars:>20"),
        ("储能", "储能 OR 钠离子 中国 stars:>20"),
        ("量子", "量子计算 OR 量子通信 中国 stars:>20"),
        ("脑机", "脑机接口 OR 神经科学 中国 stars:>20"),
        ("合成生物", "合成生物学 OR 基因编辑 中国 stars:>20"),
        ("氢能", "氢能 OR 燃料电池 中国 stars:>20"),
        ("航空航天", "航天 OR 卫星 中国 stars:>20"),
    ]

    for cat_name, query in chinese_queries:
        print(f"\n[{cat_name}] 补充搜索: {query[:40]}...")
        companies = crawl_github_by_stars(cat_name, query, limit=limit_per_source)
        print(f"  → 发现 {len(companies)} 个")

        for company in companies:
            name = company["name"]
            if any(s["name"] == name for s in total_suppliers):
                stats["skip"] += 1
                continue

            context = f"公司/组织名称: {name}\n描述: {company.get('description','')}\n标签: {company.get('topics',[])}\n编程语言: {company.get('language','')}"
            result = deepseek_extract(name, context)
            if "error" in result:
                continue

            supplier = {
                "name": result.get("name", name),
                "description": result.get("description", ""),
                "industry": result.get("industry", ""),
                "discipline": result.get("discipline", ""),
                "skills": result.get("skills", []),
                "process": result.get("process", []),
                "trl": result.get("trl", 3),
                "url": company.get("url", ""),
                "country": "中国",
                "profile_type": "COMPANY",
                "trust_score": 0.3,
                "contact": {},
            }

            desc_text = f"{supplier['industry']} {supplier['discipline']} {' '.join(supplier['skills'])}"
            supplier["category"] = classify(
                supplier["industry"], supplier["discipline"], desc_text)

            print(f"\n  📄 {name[:40]}")
            print(f"     行业: {supplier['industry'][:20]} | 学科: {supplier['discipline'][:20]}")
            total_suppliers.append(supplier)

            if not dry_run:
                result_status = insert_supplier(supplier)
                if result_status == "ok":
                    stats["ok"] += 1
                    print(f"     ✅ 入库")
                elif result_status == "dup":
                    stats["dup"] += 1
                    print(f"     ⏭ 已存在")
                else:
                    stats["fail"] += 1

            time.sleep(1.5)

    # === 保存备份 ===
    if total_suppliers:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = os.path.join(RESULTS_DIR, f"suppliers_v3_{ts}.json")
        try:
            with open(backup_file, "w", encoding="utf-8") as f:
                json.dump(total_suppliers, f, ensure_ascii=False, indent=2)
            print(f"\n  备份: {backup_file}")
        except:
            pass

    # === 汇总 ===
    print(f"\n{'=' * 70}")
    print(f"爬取完成!")
    print(f"  发现: {len(total_suppliers)} 个供应商")
    if not dry_run:
        print(f"  入库: {stats['ok']} 新 | {stats['dup']} 重复 | {stats['fail']} 失败 | {stats['skip']} 跳过")
    print(f"{'=' * 70}")

    return stats


# ============================================================
# Main
# ============================================================
if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    limit = 8
    for arg in sys.argv:
        if arg.startswith("--limit="):
            limit = int(arg.split("=")[1])

    print(f"=== 需求链 供应商深度爬虫 v3 ===")
    print(f"模式: {'试跑(不入库)' if dry_run else '正式入库'}")
    print(f"每源数量: {limit}")
    print(f"API: {API_BASE}")
    print(f"DeepSeek: {'已配置' if DEEPSEEK_KEY else '未配置'}")

    run(dry_run=dry_run, limit_per_source=limit)

    print(f"\n完成时间: {datetime.now().isoformat()}")


