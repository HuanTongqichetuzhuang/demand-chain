#!/usr/bin/env python3
"""
需求链平台 — 科研数据新维度爬虫 v1.0
========================================
将科研数据转化为可匹配的技术需求：
1. ClinicalTrials.gov — 全球临床试验 → 生物医药研发需求
2. WIPO PATENTSCOPE — 公开专利 → 可转化的专利技术需求
3. arXiv API — 最新论文摘要 → DeepSeek提取产业化需求

用法:
  python scripts/sci_data_crawler.py            # 正式运行
  python scripts/sci_data_crawler.py --dry-run  # 试跑不入库
  python scripts/sci_data_crawler.py --trials   # 只跑临床试验
  python scripts/sci_data_crawler.py --patents  # 只跑专利
  python scripts/sci_data_crawler.py --arxiv    # 只跑论文
"""
import hashlib, json, re, sys, time, urllib.request, urllib.error, urllib.parse
from datetime import datetime

API_BASE = "http://8.154.26.92:8080"
DEEPSEEK_KEY = "sk-c32415bb5ae44cdc844f1b95f99e4544"

def log(msg):
    print(msg)
    sys.stdout.flush()

def fetch(url, timeout=25):
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json,text/html,*/*",
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
                    {"role": "system", "content": "翻译下面文字为中文。保留专有名词(人名、机构缩写、化学式)不译。只输出译文。"},
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

def classify(text):
    tl = text.lower()
    if any(k in tl for k in ["cancer", "tumor", "oncology", "chemotherapy", "radiation therapy", "immunotherapy", "carcinoma", "neoplasm", "leukemia"]):
        return "生物医药"
    if any(k in tl for k in ["cardiovascular", "heart", "cardiac", "stroke", "hypertension", "blood pressure", "arrhythmia"]):
        return "生物医药"
    if any(k in tl for k in ["diabetes", "obesity", "metabolic", "endocrin", "thyroid", "insulin"]):
        return "生物医药"
    if any(k in tl for k in ["vaccine", "infection", "virus", "bacterial", "antibiotic", "antiviral", "covid", "influenza", "hiv", "malaria", "tb", "tuberculosis"]):
        return "生物医药"
    if any(k in tl for k in ["neurological", "brain", "alzheimer", "parkinson", "dementia", "epilepsy", "spinal", "nerve", "mental", "psychiatric", "depression", "anxiety"]):
        return "生物医药"
    if any(k in tl for k in ["ai", "machine learning", "deep learning", "artificial intelligence", "computer vision", "nlp", "neural network", "llm", "transformer", "reinforcement"]):
        return "人工智能"
    if any(k in tl for k in ["solar", "photovoltaic", "battery", "hydrogen", "fuel cell", "energy storage", "perovskite", "wind", "renewable"]):
        return "新能源"
    if any(k in tl for k in ["material", "nanomaterial", "polymer", "composite", "coating", "alloy", "ceramic", "graphene", "mxene", "metamater"]):
        return "材料科学"
    if any(k in tl for k in ["semiconductor", "chip", "transistor", "quantum", "photonics", "optoelectronic", "led", "laser", "detector", "sensor"]):
        return "电子科学与技术"
    if any(k in tl for k in ["gene", "genome", "crispr", "dna", "rna", "sequencing", "genetic", "biomarker", "diagnostic"]):
        return "生物技术"
    if any(k in tl for k in ["robot", "autonomous", "drone", "uav", "robotics", "manipulation", "slam", "navigation"]):
        return "机器人与智能系统"
    if any(k in tl for k in ["water", "wastewater", "carbon", "climate", "environment", "pollution", "recycling", "sustainable"]):
        return "环境工程"
    if any(k in tl for k in ["aerospace", "propulsion", "satellite", "aviation", "space"]):
        return "航空航天"
    if any(k in tl for k in ["agriculture", "crop", "food", "soil", "farming", "plant"]):
        return "农业科学"
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

# ============================================================
# AI Prompt：从论文摘要提取可转化的产业化需求
# ============================================================
ARXIV_DEMAND_PROMPT = """分析以下论文摘要，判断该研究是否有产业化潜力。输出JSON:

{"is_demand":true/false,"title":"技术需求中文标题","summary":"80字内中文说明该技术可以解决什么问题","category":"分类","tags":["标签"]}

如果is_demand为true，则这项技术可以转化为一个技术需求（即"我们需要XXX技术来解决YYY问题"）。
如果is_demand为false，reason给出原因（纯基础研究/方法学改进/数据报告）。

分类选项: 人工智能|生物医药|新能源|环境工程|材料科学|航空航天|机器人与智能系统|信息技术|传感器技术|农业科学|化学工程|生物技术|电子科学与技术

输出纯JSON，无其他文字。"""


def deepseek_analyze(text, prompt_template, max_retries=2):
    """用DeepSeek分析文本，返回JSON"""
    for attempt in range(max_retries):
        try:
            payload = json.dumps({
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": prompt_template},
                    {"role": "user", "content": text[:3000]}
                ],
                "temperature": 0.3, "max_tokens": 512
            }).encode("utf-8")
            req = urllib.request.Request(
                "https://api.deepseek.com/v1/chat/completions",
                data=payload,
                headers={"Authorization": f"Bearer {DEEPSEEK_KEY}", "Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=30) as r:
                result = json.loads(r.read())
                content = result["choices"][0]["message"]["content"].strip()
                content = content[content.find("{"):content.rfind("}")+1] if "{" in content else content
                return json.loads(content)
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(5)
    return {"is_demand": False, "reason": "AI分析失败"}


# ============================================================
# ClinicalTrials.gov — 全球临床试验
# 免费API: https://clinicaltrials.gov/api/v2/studies
# ============================================================
def crawl_clinical_trials(dry_run=False):
    """爬取近期注册的临床试验，提取生物医药研发需求"""
    total = 0
    label = "ClinicalTrials临床试验"
    log(f"\n  📋 {label}")
    
    # 搜索：最近30天注册的介入性试验（有治疗手段的）
    api_url = ("https://clinicaltrials.gov/api/v2/studies?"
               "query.term=AREA%5bOverallStatus%5d%22NOT_YET_RECRUITING%22+OR+AREA%5bOverallStatus%5d%22RECRUITING%22"
               "&pageSize=15&sort=LastUpdatePostDate&countTotal=true")
    
    log(f"     API: {api_url[:80]}...")
    data = fetch(api_url)
    if not data:
        return 0
    
    try:
        parsed = json.loads(data)
        studies = parsed.get("studies", [])
        log(f"     获取试验数: {len(studies)}")
    except Exception as e:
        log(f"     ⚠️ 解析失败: {e}")
        return 0
    
    for study in studies:
        try:
            protocol = study.get("protocolSection", {})
            id_module = protocol.get("identificationModule", {})
            status_module = protocol.get("statusModule", {})
            design_module = protocol.get("designModule", {})
            conditions_module = protocol.get("conditionsModule", {})
            sponsor_module = protocol.get("sponsorCollaboratorsModule", {})
            
            title = id_module.get("briefTitle", "")
            nct_id = id_module.get("nctId", "")
            status = status_module.get("overallStatus", "")
            conditions = conditions_module.get("conditions", [])
            sponsor = sponsor_module.get("leadSponsor", {}).get("name", "")
            
            if not title or len(title) < 15:
                continue
            
            # 只保留有介入措施的
            phases = design_module.get("phases", [])
            phase_str = ", ".join(phases) if phases else "未知"
            
            # 构建描述
            conditions_str = ", ".join(conditions[:3]) if conditions else "多种疾病"
            desc = f"临床试验 {nct_id}: {title}. 适应症: {conditions_str}. 阶段: {phase_str}. 发起方: {sponsor}"
            cn_title = translate_to_chinese(title)
            cat = "生物医药"
            
            log(f"       [{cat}] {cn_title[:70]}")
            url = f"https://clinicaltrials.gov/study/{nct_id}"
            log(f"              {url}")
            
            if not dry_run:
                r = api_post("/api/auto-demand", {
                    "raw_text": f"{cn_title}\n{nct_id}: {desc[:300]}\n来源: {label}",
                    "category": cat,
                    "email": "crawler",
                    "source": label,
                    "source_url": url,
                })
                if r.get("status") == "ok":
                    total += 1
                    log(f"              ✅ 入库")
                elif r.get("status") == "dup":
                    log(f"              ⏭ 重复")
        except Exception as e:
            log(f"     ⚠️ 处理条目出错: {e}")
            continue
    
    log(f"     → 入库: {total}")
    return total


# ============================================================
# WIPO PATENTSCOPE — 近期公开专利
# API: https://patentscope.wipo.int/search/ 有免费JSON API
# ============================================================
def crawl_wipo_patents(dry_run=False):
    """爬取WIPO近期PCT专利，提取可转化的技术需求"""
    total = 0
    label = "WIPO国际专利"
    log(f"\n  📋 {label}")
    
    # PATENTSCOPE REST API — 搜索最近专利
    api_url = ("https://patentscope.wipo.int/search/en/result.json?"
               "searchId=latest&sort=score&maxRec=20&recBatchSize=20")
    
    log(f"     API: {api_url}")
    data = fetch(api_url)
    
    # PATENTSCOPE API可能复杂，试直接搜索页面
    if not data or "error" in data.lower()[:100]:
        log(f"     ⚠️ REST API不可用，尝试搜索页面")
        search_url = "https://patentscope.wipo.int/search/en/search.jsf"
        html = fetch(search_url)
        if not html:
            return 0
        
        # 提取搜索结果
        log(f"     搜索页面已加载")
    
    # 尝试解析返回的JSON
    patents = []
    if data:
        try:
            parsed = json.loads(data)
            recs = parsed.get("records", [])
            patents = recs
            log(f"     获取专利数: {len(patents)}")
        except:
            pass
    
    if not patents:
        # 备选：使用简单搜索
        log(f"     使用备选搜索...")
        alt_url = ("https://patentscope.wipo.int/search/en/result.json?"
                   "query=ALL&sort=date&maxRec=15&recBatchSize=15")
        alt_data = fetch(alt_url)
        if alt_data:
            try:
                parsed = json.loads(alt_data)
                recs = parsed.get("records", []) or parsed.get("record", []) or []
                patents = recs
                log(f"     备选搜索结果: {len(patents)}")
            except:
                pass
    
    for patent in patents[:20]:
        try:
            # 不同格式兼容
            if isinstance(patent, dict):
                title = (patent.get("title", "") or 
                         patent.get("inventionTitle", "") or 
                         patent.get("woTitle", "") or 
                         patent.get("titleOriginal", ""))
                
                if isinstance(title, dict):
                    title = title.get("text", "") or title.get("_", "")
                if not title or len(str(title)) < 15:
                    continue
                
                app_num = (patent.get("appNumber", "") or 
                          patent.get("woNumber", "") or 
                          patent.get("pctNumber", "") or 
                          "")
                abstract = patent.get("abstract", "") or patent.get("abstract", {}).get("text", "") or ""
            else:
                continue
            
            cn_title = translate_to_chinese(title)
            cat = classify(f"{title} {abstract}")
            
            log(f"       [{cat}] {cn_title[:70]}")
            url = f"https://patentscope.wipo.int/search/en/detail.jsf?docId={app_num}" if app_num else search_url
            log(f"              {app_num}")
            
            if not dry_run:
                demand_text = f"专利技术需求: {cn_title}"
                if abstract:
                    demand_text += f"\n创新点: {translate_to_chinese(abstract[:300])}"
                demand_text += f"\n来源: {label}, 专利号: {app_num}"
                
                r = api_post("/api/auto-demand", {
                    "raw_text": demand_text[:500],
                    "category": cat,
                    "email": "crawler",
                    "source": label,
                    "source_url": url,
                })
                if r.get("status") == "ok":
                    total += 1
                    log(f"              ✅ 入库")
                elif r.get("status") == "dup":
                    log(f"              ⏭ 重复")
        except Exception as e:
            log(f"     ⚠️ 处理专利出错: {e}")
            continue
    
    log(f"     → 入库: {total}")
    return total


# ============================================================
# arXiv API v2 — 最新论文 → AI提取未解决问题作为技术需求
# 重点：从"Future Work" / "Open Problems" / 摘要末段提取
# ============================================================

# arXiv分类映射（只选应用潜力高的领域）
ARXIV_CATEGORIES = [
    # cs — 计算机科学
    ("cs.AI", "人工智能", "AI"),
    ("cs.LG", "机器学习", "AI"),
    ("cs.CV", "计算机视觉", "AI"),
    ("cs.CL", "自然语言处理", "AI"),
    ("cs.RO", "机器人学", "机器人与智能系统"),
    ("cs.NE", "神经进化计算", "AI"),
    ("cs.CR", "密码学与安全", "信息技术"),
    ("cs.SE", "软件工程", "信息技术"),
    ("cs.DC", "分布式计算", "信息技术"),
    ("cs.HC", "人机交互", "信息技术"),
    ("cs.CY", "计算与社会", "信息技术"),
    # eess — 电子工程
    ("eess.SP", "信号处理", "传感器技术"),
    ("eess.IV", "图像处理", "计算机视觉"),
    ("eess.SY", "系统与控制", "机器人与智能系统"),
    # physics — 物理
    ("physics.optics", "光学", "传感器技术"),
    ("physics.med-ph", "医学物理", "生物医药"),
    ("physics.app-ph", "应用物理", "材料科学"),
    ("physics.chem-ph", "化学物理", "化学工程"),
    # q-bio — 生物学
    ("q-bio.QM", "定量生物学", "生物医药"),
    ("q-bio.BM", "生物分子", "生物医药"),
    ("q-bio.GN", "基因组学", "生物医药"),
    ("q-bio.NC", "神经科学", "生物医药"),
    # q-fin — 金融
    ("q-fin.CP", "计算金融", "信息技术"),
    # stat — 统计
    ("stat.ML", "统计学习", "AI"),
    ("stat.AP", "应用统计", "信息技术"),
]

# 需求转化Prompt：专注提取"未解决问题"
ARXIV_DEMAND_PROMPT_V2 = """你是一个技术需求分析师。分析以下论文的标题和摘要，提取其中提到的"未解决问题"、"未来工作"、"开放挑战"或"当前方法局限"。

输出JSON格式：
{
  "has_demand": true/false,
  "demand_title": "30字内的技术需求标题（中文，从'需要/缺乏/亟待解决'等角度表述）",
  "demand_description": "100字内说明需要解决的具体技术问题（中文）",
  "problem_source": "future_work" / "limitation" / "open_challenge" / "explicit_gap",
  "category": "从以下选: AI|生物医药|新能源|环境工程|材料科学|航空航天|机器人与智能系统|信息技术|传感器技术|农业科学|化学工程|生物技术|电子科学与技术",
  "key_technologies": ["相关技术关键词（中文，最多3个）"]
}

判断标准：
- has_demand=true：论文明确提到"future work"、"future research"、"open problem"、"challenge"、"limitation"、"need for"、"remains unsolved"、"lack of"、"not yet addressed" 等指向未解决问题的表述
- has_demand=false：纯方法改进、基准测试、调查综述（没有指向具体未解决问题）、或已有明确解决方案

只输出JSON，不要其他文字。"""


def crawl_arxiv(dry_run=False):
    """爬取arXiv最新论文，用DeepSeek提取未解决问题作为技术需求"""
    total = 0
    skipped_dup = 0
    label = "arXiv论文需求转化"
    
    # 已处理的arXiv ID（避免同一篇被多个分类重复抓）
    seen_ids = set()
    
    log(f"\n  📋 {label} v2 — 专注未解决问题提取")
    log(f"     分类数: {len(ARXIV_CATEGORIES)}")
    
    for cat_id, cat_name, plat_cat in ARXIV_CATEGORIES:
        # 每类取最新10篇（足够覆盖当天新论文）
        api_url = (f"https://export.arxiv.org/api/query?"
                   f"search_query=cat:{cat_id}"
                   f"&sortBy=submittedDate&sortOrder=descending"
                   f"&max_results=10")
        
        log(f"     {cat_id} ({cat_name})...")
        xml = fetch(api_url)
        if not xml:
            log("     ❌ 无响应")
            continue
        
        entries = re.findall(r'<entry>(.*?)</entry>', xml, re.DOTALL)
        log(f"     → {len(entries)}篇")
        
        for entry in entries:
            try:
                # 提取arXiv ID和元数据
                id_m = re.search(r'<id>http://arxiv\.org/abs/([^<]+)</id>', entry)
                title_m = re.search(r'<title>(.*?)</title>', entry, re.DOTALL)
                summary_m = re.search(r'<summary>(.*?)</summary>', entry, re.DOTALL)
                published_m = re.search(r'<published>([^<]+)</published>', entry)
                
                if not id_m or not title_m:
                    continue
                
                arxiv_id = id_m.group(1).split("v")[0]  # 去掉版本号
                title = re.sub(r'\s+', ' ', title_m.group(1).strip())
                summary = re.sub(r'\s+', ' ', summary_m.group(1).strip())[:3000] if summary_m else ""
                
                # 去重：arXiv ID
                if arxiv_id in seen_ids:
                    continue
                seen_ids.add(arxiv_id)
                
                if len(title) < 10 or not summary:
                    continue
                
                # 用DeepSeek提取未解决问题
                combined = f"Title: {title}\n\nAbstract: {summary}"
                result = deepseek_analyze(combined, ARXIV_DEMAND_PROMPT_V2)
                
                if isinstance(result, dict) and result.get("has_demand"):
                    demand_title = result.get("demand_title", "")
                    demand_desc = result.get("demand_description", "")
                    demand_cat = result.get("category", plat_cat)
                    problem_source = result.get("problem_source", "future_work")
                    technologies = result.get("key_technologies", [])
                    tech_str = ", ".join(technologies[:3]) if technologies else ""
                    
                    log(f"       ✅ [{demand_cat}] {demand_title[:50]}")
                    log(f"         论文: {title[:50]}... | 问题来源: {problem_source}")
                    
                    if not dry_run:
                        source_url = f"https://arxiv.org/abs/{arxiv_id}"
                        raw_text = (
                            f"技术需求: {demand_title}\n"
                            f"说明: {demand_desc}\n"
                            f"问题来源: {problem_source}\n"
                            f"相关技术: {tech_str}\n"
                            f"来源论文: {title}\n"
                            f"摘要: {summary[:800]}\n"
                            f"来源: {label}({cat_name})"
                        )
                        r = api_post("/api/auto-demand", {
                            "raw_text": raw_text,
                            "category": demand_cat,
                            "email": "crawler",
                            "source": f"{label}({cat_name})",
                            "source_url": source_url,
                            "organization": "",
                            "deadline": "",
                            "budget_hint": "",
                            "location": "",
                        })
                        if r.get("status") == "ok":
                            total += 1
                        elif r.get("status") == "dup":
                            skipped_dup += 1
                else:
                    reason = result.get("reason", "") if isinstance(result, dict) else ""
                    if reason:
                        log(f"       ⏭ {reason[:30]}")
                
                time.sleep(3)  # arXiv API限制: 每秒1次
            except Exception as e:
                log(f"     ⚠️ 处理出错: {e}")
                continue
    
    log(f"     → 入库: {total} | 重复跳过: {skipped_dup}")
    return total


# ============================================================
# 主流程
# ============================================================
def run(dry_run=False, trials_only=False, patents_only=False, arxiv_only=False):
    log(f"{'='*60}")
    log(f"  科研数据新维度爬虫 v1.0")
    log(f"  时间: {datetime.now().isoformat()}")
    log(f"  模式: {'试跑(不入库)' if dry_run else '入库'}")
    log(f"{'='*60}")
    
    total = 0
    
    if not patents_only and not arxiv_only:
        t = crawl_clinical_trials(dry_run) or 0; total += t
    
    if not trials_only and not patents_only:
        t = crawl_arxiv(dry_run) or 0; total += t
    
    log(f"\n{'='*60}")
    log(f"  本次入库: {total} 条")
    log(f"{'='*60}")
    
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    with open(f"sci_data_{ts}.json", "w") as f:
        json.dump({"ts": ts, "source": "科研数据新维度", "imported": total}, f)
    
    return total

if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    trials = "--trials" in sys.argv
    patents = "--patents" in sys.argv
    arxiv = "--arxiv" in sys.argv
    run(dry_run=dry, trials_only=trials, patents_only=patents, arxiv_only=arxiv)
