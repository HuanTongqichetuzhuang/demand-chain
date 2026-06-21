#!/usr/bin/env python3
"""
需求链平台 — 清理低质量数据 v1.0
==================================
从数据库中删除：
- 低质量需求（新闻、政策解读、领导讲话等非真实项目）
- 信息不全的供应商（名称/描述/分类中任一项缺失或模糊）

用法:
  python scripts/cleanup_low_quality.py
  python scripts/cleanup_low_quality.py --dry-run  # 只列出不删除
"""
import json, re, sys, time, urllib.request

API = "http://8.154.26.92:8080"
ADMIN_EMAIL = "477570216@qq.com"

def fetch(endpoint, max_pages=20):
    items = []
    for page in range(1, max_pages + 1):
        try:
            req = urllib.request.Request(f"{API}{endpoint}?page={page}&per_page=200")
            with urllib.request.urlopen(req, timeout=10) as r:
                data = json.loads(r.read())
                batch = data.get("items", [])
                if not batch:
                    break
                items.extend(batch)
        except Exception as e:
            print(f"  分页{page}出错: {e}")
            break
    return items

def api_del(endpoint, eid):
    payload = json.dumps({"email": ADMIN_EMAIL}).encode("utf-8")
    req = urllib.request.Request(f"{API}{endpoint}/{eid}", data=payload,
        headers={"Content-Type": "application/json"}, method="DELETE")
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status == 200
    except:
        return False

def log(msg):
    print(msg)
    sys.stdout.flush()

# ============================================================
# 负向标题 — 这些不是真实需求
# ============================================================
BAD_TITLE_KEYWORDS = [
    # 领导活动/调研（纯活动报道，无项目实质）
    "调研", "座谈会", "党课", "党建", "学习会", "学习教育",
    "贯彻", "精神", "安全生产", "大讲堂", "培训班",
    "书记", "厅长", "局长", "主任",
    "总书记", "习近平", "重要讲话", "重要讲话",
    "党纪", "作风", "巡视", "巡察", "审计",
    "公务员", "遴选", "录用", "招聘",
    "预算", "决算",
    "退休", "老干部",
    "处罚", "举报", "信用",
    # 政策说明类（不产生实际项目）
    "政策解读", "一图读懂",
    "民声热线", "倡议书", "回信", "反响",
    "青春", "体育", "健身",
    # 非项目新闻
    "记者会", "新闻发布会", "媒体",
    "宣传", "普法",
    "财务", "采购",
]

# 真正项目需求的标志性词汇
REAL_DEMAND_KEYWORDS = [
    "申报", "征集", "立项", "揭榜挂帅",
    "项目指南", "专项资金", "重点研发",
    "科技计划", "技术攻关", "重大专项",
    "自然科学基金", "联合基金",
    "技术需求", "成果转化",
    "领军人才", "青年人才", "创新人才",
    "揭榜", "招标",
    "项目申报", "项目立项",
    "课题", "经费", "资助", "补助", "奖励",
    "示范", "试点",
]

def is_low_quality_demand(d):
    text = d.get("raw_text", "") or ""
    source = d.get("source", "") or ""
    title = text[:100]
    cat = d.get("category", "") or ""
    created = d.get("created_at", "") or ""
    
    # 来源标记为有问题的
    bad_sources = [
        "ERC欧洲研究委员会资助", "UKRI英国研究与创新资助",
        "WHO世界卫生组织招标", "UNGM",
        "中国科学技术协会", "国家自然科学基金委",
    ]
    if source in bad_sources:
        if len(text) < 60:
            return True, "来源低质+内容过短"
    
    # 标题含负向词 + 不含正向词
    has_bad = any(k in title for k in BAD_TITLE_KEYWORDS)
    has_good = any(k in title for k in REAL_DEMAND_KEYWORDS)
    
    if has_bad and not has_good:
        return True, f"含负向词({[k for k in BAD_TITLE_KEYWORDS if k in title][:2]})"
    
    # 太短的内容
    if len(text) < 20:
        return True, "内容过短"
    
    # 看起来像导航/菜单/页脚的
    nav_patterns = ["首页", "联系我们", "网站地图", "设为首页", "登录", "注册", "隐私声明"]
    if any(p in title for p in nav_patterns) and not has_good:
        return True, "导航链接"
    
    # 来源是各省科技厅但没有项目关键词的 — 仅当内容很短时判定为噪声
    if "科技厅" in source and not has_good and not has_bad:
        if len(text) < 40:
            return True, "科技厅短新闻"
        # 含"通知"且长度在40-80之间，检查是否有具体项目
        if "通知" in title and len(text) < 60:
            return True, "通知无项目实质"
    
    return False, ""

def is_incomplete_supplier(s):
    name = s.get("name", "") or ""
    desc = s.get("description", "") or s.get("agent_card", {}).get("description", "") or ""
    category = s.get("category", "") or s.get("agent_card", {}).get("category", "") or ""
    industry = s.get("industry", "") or s.get("agent_card", {}).get("industry", "") or ""
    
    # 名称为空/占位符
    if not name or len(name) < 2:
        return True, "无名称"
    if name in ["未知", "Unknown", "N/A", "-", "公司名称", "Company"]:
        return True, "占位符名称"
    
    # 导航类/非供应商
    nav_names = ["首页", "登录", "注册", "InnovationQ+", "Startup",
                 "Load More Startups", "Add Startup", "View all"]
    if name in nav_names:
        return True, "导航/非供应商"
    
    # 缺少关键信息
    if not desc or len(desc) < 5:
        return True, "无描述"
    if not category and not industry:
        return True, "无分类"
    
    # 描述是占位符
    if desc in ["暂无描述", "暂无简介", "description", "公司简介"]:
        return True, "占位符描述"
    
    return False, ""


def main(dry_run=False):
    log(f"{'='*60}")
    log(f"  低质量数据清理 v1.0")
    log(f"  时间: {datetime.now().isoformat()}")
    log(f"  模式: {'试跑(仅列出)' if dry_run else '删除'}")
    log(f"{'='*60}")
    
    # 获取全部需求
    log(f"\n📋 获取需求列表...")
    demands = fetch("/api/demands")
    log(f"   共 {len(demands)} 条需求")
    
    bad_demands = []
    for d in demands:
        is_bad, reason = is_low_quality_demand(d)
        if is_bad:
            bad_demands.append((d["id"], d.get("raw_text","")[:60], reason))
    
    log(f"\n📋 获取供应商列表...")
    suppliers = fetch("/api/suppliers")
    log(f"   共 {len(suppliers)} 个供应商")
    
    bad_suppliers = []
    for s in suppliers:
        is_bad, reason = is_incomplete_supplier(s)
        if is_bad:
            bad_suppliers.append((s["id"], s.get("name","")[:40], reason))
    
    log(f"\n{'='*60}")
    log(f"待删除低质量需求: {len(bad_demands)} 条")
    for did, txt, reason in bad_demands[:30]:
        log(f"  ❌ [{reason}] {txt}")
    if len(bad_demands) > 30:
        log(f"  ... 还有 {len(bad_demands)-30} 条")
    
    log(f"\n待删除不完整供应商: {len(bad_suppliers)} 个")
    for sid, name, reason in bad_suppliers[:30]:
        log(f"  ❌ [{reason}] {name}")
    if len(bad_suppliers) > 30:
        log(f"  ... 还有 {len(bad_suppliers)-30} 个")
    
    if dry_run or not bad_demands:
        log(f"\n{'='*60}")
        log(f"  试跑模式，未执行删除")
        log(f"{'='*60}")
        return
    
    log(f"\n{'='*60}")
    log(f"  执行删除...")
    log(f"{'='*60}")
    
    ok_d = 0
    for did, _, reason in bad_demands:
        if api_del("/api/admin/demands", did):
            ok_d += 1
            log(f"  ✅ 已删需求 {did[:8]}")
        else:
            log(f"  ❌ 删除失败 {did[:8]}")
        time.sleep(0.1)
    
    ok_s = 0
    for sid, _, reason in bad_suppliers:
        if api_del("/api/admin/suppliers", sid):
            ok_s += 1
            log(f"  ✅ 已删供应商 {sid[:8]}")
        else:
            log(f"  ❌ 删除失败 {sid[:8]}")
        time.sleep(0.1)
    
    log(f"\n{'='*60}")
    log(f"  需求删除: {ok_d}/{len(bad_demands)}")
    log(f"  供应商删除: {ok_s}/{len(bad_suppliers)}")
    log(f"{'='*60}")

if __name__ == "__main__":
    from datetime import datetime
    dry = "--dry-run" in sys.argv
    main(dry_run=dry)
