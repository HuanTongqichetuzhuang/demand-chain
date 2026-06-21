#!/usr/bin/env python3
"""
需求链平台 — 中国部委/省级项目爬虫 v1.0
========================================
采集中国政府各部委和省级科技项目：
1. 工信部 — 制造业高质量发展、工业强基、专精特新
2. 中国博士后科学基金 — 博士后资助/特别资助
3. 中国科协 — 青年人才托举、学术交流资助
4. 国家重点实验室开放课题 — 各实验室课题
5. 国防科技创新特区 — 国防科技挑战
6. 各省科技厅项目 — 浙江/广东/江苏/山东

用法:
  python scripts/china_govt_crawler.py            # 正式运行
  python scripts/china_govt_crawler.py --dry-run  # 试跑不入库
  python scripts/china_govt_crawler.py --miit     # 只跑工信部
"""
import hashlib, json, re, sys, time, urllib.request, urllib.error, urllib.parse
from datetime import datetime

API_BASE = "http://8.154.26.92:8080"
DEEPSEEK_KEY = "sk-c32415bb5ae44cdc844f1b95f99e4544"

def log(msg):
    print(msg)
    sys.stdout.flush()

def fetch(url, timeout=20, encoding="utf-8"):
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/json,*/*",
        })
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            if encoding == "auto":
                enc = r.headers.get_content_charset() or "utf-8"
            else:
                enc = encoding
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
                    {"role": "system", "content": "翻译下面文字为中文。保留专有名词不译。只输出译文。"},
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

def classify_china_project(text):
    tl = text.lower()
    # 中文关键词优先
    if any(k in text for k in ["人工智能", "智能", "大数据", "大模型", "机器视觉", "nlp", "自然语言", "机器学习", "深度学习"]):
        return "人工智能"
    if any(k in text for k in ["生物医药", "制药", "医学", "医疗", "临床", "药物", "疫苗", "基因", "诊断", "医疗器械"]):
        return "生物医药"
    if any(k in text for k in ["新能源", "光伏", "风电", "氢能", "储能", "锂电池", "燃料电池", "太阳能", "清洁能源"]):
        return "新能源"
    if any(k in text for k in ["材料", "纳米", "高分子", "复合材料", "涂层", "合金", "陶瓷", "碳纤维"]):
        return "材料科学"
    if any(k in text for k in ["航空航天", "航天", "航空", "卫星", "无人机", "火箭", "空间站"]):
        return "航空航天"
    if any(k in text for k in ["机器人", "自动化", "智能制造", "工业互联网", "数字孪生", "工业软件", "数控", "传感器"]):
        return "机器人与智能系统"
    if any(k in text for k in ["半导体", "芯片", "集成电路", "电子", "光电子", "通信", "5g", "6g", "量子", "光电"]):
        return "电子科学与技术"
    if any(k in text for k in ["环境", "碳中和", "碳达峰", "碳捕集", "污水处理", "大气", "土壤", "生态", "节能", "减排"]):
        return "环境工程"
    if any(k in text for k in ["农业", "农作物", "养殖", "食品", "种子", "耕地", "农机", "智慧农业"]):
        return "农业科学"
    if any(k in text for k in ["海洋", "深海", "海水", "渔业", "船舶"]):
        return "海洋科学"
    if any(k in text for k in ["交通", "高铁", "自动驾驶", "新能源汽车", "电动汽车", "物流", "车联网"]):
        return "交通运输"
    if any(k in text for k in ["化工", "催化", "合成", "反应", "精细化工"]):
        return "化学工程"
    if any(k in text for k in ["核能", "核", "反应堆", "辐射", "同位素"]):
        return "核科学"
    if any(k in text for k in ["生物技术", "合成生物", "发酵", "酶", "蛋白质", "crispr", "基因组"]):
        return "生物技术"
    if any(k in text for k in ["土木", "建筑", "桥梁", "隧道", "水利", "地震", "结构"]):
        return "土木工程"
    if any(k in text for k in ["教育", "人才", "培训", "课程", "教学"]):
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

def extract_links(html, min_len=10):
    return re.findall(r'href="([^"]+)"[^>]*>([^<]{' + str(min_len) + r',300})</a>', html, re.I)

def make_absolute(path, base_url):
    if path.startswith("http"):
        return path
    parsed = urllib.parse.urlparse(base_url)
    if path.startswith("/"):
        return f"{parsed.scheme}://{parsed.netloc}{path}"
    return base_url.rstrip("/") + "/" + path.lstrip("/")


# ============================================================
# 工信部 — 项目申报/专精特新/高质量发展
# ============================================================
def crawl_miit(dry_run=False):
    total = 0
    label = "工信部项目申报"
    log(f"\n  📋 {label}")
    log(f"  ⚠️ 工信部官网使用JS动态加载通知列表，HTTP直连仅能获取导航页。")
    log(f"  → 建议使用 smart_crawler 搜索: site:miit.gov.cn 项目申报 OR 专项资金 OR 高质量发展 2026")
    log(f"  → 尝试可访问的聚合页面...")
    
    # 尝试不同的通知列表页面
    urls = [
        "https://www.miit.gov.cn/zwgk/zcwj/wjfb/tz/index.html",
        "https://www.miit.gov.cn/",
    ]
    
    for url in urls:
        log(f"     URL: {url}")
        html = fetch(url, encoding="auto")
        if not html:
            continue
        
        links = extract_links(html)
        log(f"     页面连接数: {len(links)}")
        matched = 0
        for path, title in links:
            tl = title.strip()
            if len(tl) < 10:
                continue
            if any(s in tl for s in ["首页", "返回", "搜索", "登录", "注册", "隐私", "网站地图", "联系方式", "设为首页", "收藏本站", "投诉", "举报"]):
                continue
            # 工信部项目通常含这些词
            if not any(k in tl for k in ["项目", "申报", "资金", "专项", "试点", "示范", "基地", "企业技术", "制造业", "高质量", "专精特", "小巨人", "工业互联", "智能制", "绿色制造", "两化融合", "服务型制造", "单项冠军"]):
                continue
            
            matched += 1
            cat = classify_china_project(tl)
            url_abs = make_absolute(path, url)
            log(f"       [{cat}] {tl[:70]}")
            log(f"              {url_abs[:70]}")
            if not dry_run:
                r = api_post("/api/auto-demand", {
                    "raw_text": f"{tl}\n来源: {label}",
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
# 中国博士后科学基金
# ============================================================
def crawl_postdoctor(dry_run=False):
    total = 0
    label = "中国博士后科学基金"
    log(f"\n  📋 {label}")
    log(f"  ⚠️ 博士后基金会网站是纯JS渲染的SPA应用，无法HTTP直连。")
    log(f"  → 建议使用 smart_crawler 搜索: site:chinapostdoctor.org.cn 资助 OR 基金 OR 申报 2026")
    log(f"  → 也可直接访问: https://www.chinapostdoctor.org.cn/")
    
    # 尝试已知页面的静态版本
    url = "https://www.chinapostdoctor.org.cn/"
    log(f"     URL: {url}")
    html = fetch(url, encoding="auto")
    if not html:
        return 0
    
    links = extract_links(html)
    log(f"     页面连接数: {len(links)}")
    matched = 0
    for path, title in links:
        tl = title.strip()
        if len(tl) < 15:
            continue
        if any(s in tl for s in ["首页", "返回", "登录", "注册", "网站地图"]):
            continue
        if not any(k in tl for k in ["资助", "基金", "申报", "博士后", "通知", "公示", "特别资助", "面上资助", "站前", "创新人才", "引进", "国际交流", "派出"]):
            continue
        
        matched += 1
        cat = classify_china_project(tl)
        url_abs = make_absolute(path, url)
        log(f"       [{cat}] {tl[:70]}")
        log(f"              {url_abs[:70]}")
        if not dry_run:
            r = api_post("/api/auto-demand", {
                "raw_text": f"{tl}\n来源: {label}",
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
# 中国科协 — 项目申报/人才托举
# ============================================================
def crawl_cast(dry_run=False):
    total = 0
    label = "中国科协项目"
    log(f"\n  📋 {label}")
    
    url = "https://www.cast.org.cn/xw/TZGG/index.html"
    log(f"     URL: {url}")
    html = fetch(url, encoding="auto")
    if not html:
        return 0
    
    links = extract_links(html)
    log(f"     页面连接数: {len(links)}")
    matched = 0
    for path, title in links:
        tl = title.strip()
        if len(tl) < 15:
            continue
        if any(s in tl for s in ["首页", "返回", "登录", "注册"]):
            continue
        if not any(k in tl for k in ["项目", "申报", "人才", "托举", "资助", "评选", "推荐", "通知", "公示", "课题", "研究", "学术", "交流", "论坛", "竞赛", "大赛"]):
            continue
        
        matched += 1
        cat = classify_china_project(tl)
        url_abs = make_absolute(path, url)
        log(f"       [{cat}] {tl[:70]}")
        log(f"              {url_abs[:70]}")
        if not dry_run:
            r = api_post("/api/auto-demand", {
                "raw_text": f"{tl}\n来源: {label}",
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
# 国家重点实验室开放课题（汇总页面）
# ============================================================
def crawl_skl_open(dry_run=False):
    """通过 smart_crawler 相同的逻辑，搜索各国家重点实验室的开放课题"""
    total = 0
    label = "国家重点实验室开放课题"
    log(f"\n  📋 {label}（通过已知实验室网址搜索）")
    
    # 已知的国家重点实验室开放课题页面
    labs = [
        ("https://www.sklse.org/", "软件工程国家重点实验室"),
        ("https://www.sklcs.org/", "计算机科学国家重点实验室"),
        ("https://www.sklmcb.org/", "分子生物学国家重点实验室"),
        ("https://www.sklfs.org/", "功能材料国家重点实验室"),
        ("https://www.sklao.org/", "天体物理国家重点实验室"),
        ("http://www.sklac.org/", "催化基础国家重点实验室"),
        ("https://www.sklpmt.com/", "粉末冶金国家重点实验室"),
    ]
    
    for lab_url, lab_name in labs:
        log(f"     {lab_name}: {lab_url}")
        html = fetch(lab_url)
        if not html:
            continue
        
        links = extract_links(html)
        matched = 0
        for path, title in links:
            tl = title.strip()
            if len(tl) < 15:
                continue
            if not any(k in tl for k in ["开放课题", "基金", "项目申报", "通知", "公告", "申请", "课题指南", "funding", "open", "grant", "call", "research"]):
                continue
            
            matched += 1
            cat = classify_china_project(tl)
            url_abs = make_absolute(path, lab_url)
            log(f"       [{cat}] {tl[:70]}")
            log(f"              {url_abs[:70]}")
            if not dry_run:
                r = api_post("/api/auto-demand", {
                    "raw_text": f"{tl}\n来源: {lab_name}",
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
# 各省科技厅项目
# ============================================================
PROVINCE_SCI_URLS = [
    ("http://kjt.zj.gov.cn/", "浙江省科技厅"),
    ("http://gdstc.gd.gov.cn/", "广东省科技厅"),
    ("http://kxjst.jiangsu.gov.cn/", "江苏省科技厅"),
    ("http://kjt.shandong.gov.cn/", "山东省科技厅"),
    ("https://kjt.ln.gov.cn/", "辽宁省科技厅"),
    ("https://kjt.hubei.gov.cn/", "湖北省科技厅"),
    ("http://kjt.fujian.gov.cn/", "福建省科技厅"),
    ("http://kjt.hunan.gov.cn/", "湖南省科技厅"),
]

def crawl_province_sci(dry_run=False):
    total = 0
    label = "各省科技厅项目"
    log(f"\n  📋 {label}")
    
    # 负向过滤器：这些标题不是真实项目需求
    # 负向过滤器：这些标题不是真实项目需求
    NEGATIVE_TITLES = [
        "调研", "座谈会", "党课", "党建", "学习会", "学习教育",
        "贯彻", "精神", "安全生产", "大讲堂", "培训班", "研修班",
        "解读", "一图读懂", "新年", "春节", "慰问", "致辞",
        "书记", "厅长", "局长", "主任", "部长",
        "总书记", "习近平", "重要讲话", "法律法规",
        "政策解读", "工作部署", "工作推进", "工作会",
        "动员会", "启动会", "主题宣传", "记者会", "新闻发布会",
        "民声热线", "倡议书", "回信", "反响",
        "党纪", "作风", "巡视", "巡察", "审计",
        "公务员", "遴选", "录用", "招聘", "人才引进",
        "财务", "预算", "决算", "政府采购",
        "网络安全", "信息化",
        "青春", "体育", "健身", "书画",
        "退休", "老干部", "妇女", "儿童",
        "保密", "档案管理",
        "处罚", "举报", "信用",
        "服务热线", "办公地址", "乘车路线",
        # 机构名称展示（非项目）
        "中心）", "研究院）", "（简介）",
        # ===== 新增：公告/通知/管理类垃圾 =====
        "会计师事务所", "中标结果", "修改.*决定",
        "政策问答", "注销.*许可", "注销.*资质",
        "新闻发布会", "记者会",
        "专家论证会", "推进会", "务虚会", "研讨会",
        "条例", "实施细则", "若干措施", "行动方案",
        "科技.*奖励", "奖励办法",
        "诚聘", "引进人才", "博士后",
        "规划.*论证", "十五五",
        "工作指引", "管理办法",
        "新春", "拜年", "贺词",
        "奖励的决定", "科技奖励",
        "废止", "失效", "规范性文件",
        # 公告结尾模式
        "公告",
    ]
    
    # 正向关键词：必须是真项目需求
    STRONG_KEYWORDS = [
        "申报", "征集", "立项", "揭榜挂帅",
        "项目指南", "专项资金", "重点研发",
        "科技计划", "技术攻关", "重大专项",
        "基金", "资助", "补助", "补贴",
        "奖励", "奖补",
        # 特定模式：通知 + 项目相关
        "重点研发计划", "自然科学基金", "联合基金",
        "科技创新", "技术需求", "成果转化",
        "示范", "试点",
        # 人才项目
        "人才项目", "领军人才", "青年人才",
        "创新人才", "博士后",
        "揭榜", "招标",
        "项目申报", "项目立项",
        "课题", "经费",
    ]
    
    # 必须同时否定和肯定双向过滤
    def is_real_project(title):
        tl = title.strip()
        if len(tl) < 15:
            return False
        # 负向过滤
        if any(s in tl for s in ["首页", "返回", "搜索", "登录", "注册",
                                  "网站地图", "隐私声明", "设为首页", "收藏",
                                  "联系我们", "领导信息", "机构职能",
                                  "友情链接", "常见问题", "帮助"]):
            return False
        if any(s in tl for s in NEGATIVE_TITLES):
            return False
        # 正向过滤：必须含实质性项目词
        if not any(k in tl for k in STRONG_KEYWORDS):
            return False
        # 额外规则
        if "通知" in tl and not any(k in tl for k in ["申报", "征集", "立项", "项目", "基金", "资金", "专项", "研发", "攻关"]):
            return False
        if "公示" in tl and not any(k in tl for k in ["项目", "立项", "资金", "基金", "补助", "补贴", "奖励"]):
            return False
        # 管理办法/实施细则/若干措施/行动方案 不单独作为项目需求（除非含申报/征集）
        if any(s in tl for s in ["管理办法", "实施细则", "行动方案", "若干措施", "工作指引"]):
            if not any(k in tl for k in ["申报", "征集", "立项", "项目指南", "资助", "奖金"]):
                return False
        # 纯机构名称展示（以"）"结尾的短标题）
        if tl.endswith("）") and len(tl) < 50 and "关于印发" not in tl:
            return False
        return True
    
    for url, province in PROVINCE_SCI_URLS:
        log(f"     {province}: {url}")
        html = fetch(url, encoding="auto")
        if not html:
            continue
        
        links = extract_links(html)
        total_links = len(links)
        matched = 0
        
        for path, title in links:
            tl = title.strip()
            if not is_real_project(tl):
                continue
            
            matched += 1
            cat = classify_china_project(tl)
            url_abs = make_absolute(path, url)
            log(f"       [{cat}] {tl[:60]}")
            if not dry_run:
                r = api_post("/api/auto-demand", {
                    "raw_text": f"{tl}\n来源: {province}",
                    "category": cat,
                    "email": "crawler",
                    "source": label,
                    "source_url": url_abs,
                })
                if r.get("status") == "ok":
                    total += 1
        
        log(f"     → 真实项目: {matched}/{total_links}")
    
    return total


# ============================================================
# 主流程
# ============================================================
def run(dry_run=False, miit_only=False):
    log(f"{'='*60}")
    log(f"  中国部委/省级项目爬虫 v1.0")
    log(f"  时间: {datetime.now().isoformat()}")
    log(f"  模式: {'试跑(不入库)' if dry_run else '入库'}")
    log(f"{'='*60}")
    
    total = 0
    
    if miit_only:
        t = crawl_miit(dry_run) or 0; total += t
    else:
        t = crawl_miit(dry_run) or 0; total += t
        t = crawl_postdoctor(dry_run) or 0; total += t
        t = crawl_cast(dry_run) or 0; total += t
        t = crawl_skl_open(dry_run) or 0; total += t
        t = crawl_province_sci(dry_run) or 0; total += t
    
    log(f"\n{'='*60}")
    log(f"  本次入库: {total} 条")
    log(f"{'='*60}")
    
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    with open(f"china_govt_{ts}.json", "w") as f:
        json.dump({"ts": ts, "source": "中国部委/省级项目", "imported": total}, f)
    
    return total

if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    miit = "--miit" in sys.argv
    run(dry_run=dry, miit_only=miit)
