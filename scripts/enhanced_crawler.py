"""
增强爬虫配置 — 新增中文数据源和更好的分类
"""
import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ── 新增中文数据源配置 ──────────────────────────────────────────
NEW_DATA_SOURCES = {
    "中国招标投标公共服务平台": {
        "url": "http://www.cebpubservice.com/",
        "type": "公开招标/采购需求",
        "content": "招标标题、采购内容、预算金额、截止日期、采购单位",
        "update_frequency": "每日更新",
        "language": "zh",
        "search_url": "http://www.cebpubservice.com/ctpsp/search?keywords={keyword}",
    },
    "1688 采购寻源": {
        "url": "https://page.1688.com/",
        "type": "企业采购需求",
        "content": "采购标题、规格要求、数量、预算",
        "update_frequency": "每日更新",
        "language": "zh",
        "search_url": "https://s.1688.com/youyuan/offer_search.htm?keywords={keyword}",
    },
    "中国政府采购网(省级)": {
        "url": "http://www.ccgp.gov.cn/",
        "type": "政府采购需求",
        "content": "采购公告、项目需求、技术规格、预算",
        "update_frequency": "每日更新",
        "language": "zh",
        "search_url": "http://search.ccgp.gov.cn/bxsearch?searchtype=1&bidType=0&keywords={keyword}",
    },
    "中国科学院 成果转化需求": {
        "url": "https://www.cas.cn/",
        "type": "科研合作/成果转化",
        "content": "技术需求、合作方向、研发课题",
        "update_frequency": "不定期",
        "language": "zh",
    },
    "知乎 技术/科技话题": {
        "url": "https://www.zhihu.com/topic/",
        "type": "技术需求讨论",
        "content": "技术问题、研究求助、行业讨论",
        "update_frequency": "实时",
        "language": "zh",
    },
    "企查查 招投标信息": {
        "url": "https://www.qichacha.com/",
        "type": "企业中标/招标",
        "content": "招标公告、中标结果、采购需求",
        "update_frequency": "每日更新",
        "language": "zh",
    },
}

# ── 源需求文本 → 中文招标源 ──────────────────────────────────
PROCUREMENT_CATEGORIES = {
    "智能制造": ["数控机床", "工业机器人", "自动化产线", "MES系统", "智能仓储"],
    "新能源": ["光伏电站", "风电设备", "储能系统", "氢能设备"],
    "生物医药": ["医疗设备", "药品采购", "诊断试剂", "临床试验"],
    "环境工程": ["污水处理", "废气治理", "垃圾分类", "环境监测"],
    "信息技术": ["信息化系统", "软件开发", "网络安全", "云计算"],
    "传感器技术": ["传感器", "检测设备", "监测系统"],
    "航空航天": ["无人机", "卫星导航", "航空设备"],
    "交通运输": ["新能源汽车", "智能交通", "充电桩"],
}


async def discover_procurement_demands(keywords: list[str] = None, limit: int = 50):
    """发现政府采购/招标需求"""
    import httpx
    from bs4 import BeautifulSoup
    from src.discovery.demand_crawler import DiscoveredDemand
    from src.shared.classification import classify_text
    import uuid

    if keywords is None:
        # 从各分类取关键词
        keywords = []
        for cat_kws in PROCUREMENT_CATEGORIES.values():
            keywords.extend(cat_kws)
        keywords = list(set(keywords))[:30]

    demands = []
    # 搜索中国招标投标公共服务平台
    for kw in keywords[:10]:
        search_url = f"http://www.cebpubservice.com/ctpsp/search?keywords={kw}"
        try:
            async with httpx.AsyncClient(timeout=15, verify=False) as client:
                resp = await client.get(search_url, headers={
                    "User-Agent": "Mozilla/5.0 (compatible; DemandChainBot/1.0)"
                })
                html = resp.text
                # 简单解析标题
                soup = BeautifulSoup(html, "html.parser")
                for item in soup.select(".item-title, .title, h3, a[href*='notice']")[:5]:
                    title = item.get_text(strip=True)
                    if title and len(title) > 5 and not any(s in title for s in ["登录", "注册", "首页", "关于我们"]):
                        cat, sub = classify_text(title)
                        d = DiscoveredDemand(
                            source="中国招标投标公共服务平台",
                            source_url=search_url,
                            raw_text=title,
                            category=cat,
                            sub_category=sub,
                        )
                        demands.append(d)
        except Exception as e:
            print(f"  [WARN] {kw}: {e}")

    print(f"发现 {len(demands)} 条招标需求")
    return demands[:limit]


if __name__ == "__main__":
    asyncio.run(discover_procurement_demands())
