"""
需求发现引擎 — 从公开数据源自动爬取需求信息。

与供应商发现引擎对称：从公开渠道采集需求 → LLM结构化 → 去重 → 入库。
"""
import hashlib
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class DiscoveredDemand:
    """从公开渠道发现的需求"""
    def __init__(self, source: str, source_url: str, raw_text: str,
                 inferred_category: str = "未知", inferred_discipline: str = "",
                 deadline: str = "", budget_hint: str = "", organization: str = ""):
        self.source = source
        self.source_url = source_url
        self.raw_text = raw_text
        self.inferred_category = inferred_category
        self.inferred_discipline = inferred_discipline
        self.deadline = deadline
        self.budget_hint = budget_hint
        self.organization = organization

    @property
    def fingerprint(self) -> str:
        raw = f"{self.raw_text[:200].lower()}|{self.source_url}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def to_db_dict(self) -> dict:
        return {
            "id": str(uuid4()),
            "source": self.source,
            "source_url": self.source_url,
            "raw_text": self.raw_text,
            "inferred_category": self.inferred_category,
            "inferred_discipline": self.inferred_discipline,
            "deadline": self.deadline,
            "budget_hint": self.budget_hint,
            "organization": self.organization,
            "discovered_at": datetime.utcnow(),
            "fingerprint": self.fingerprint,
        }


class PublicDemandCrawler(ABC):
    @abstractmethod
    async def search(self, keywords: list[str] = None, limit: int = 50) -> list[DiscoveredDemand]:
        ...

    @property
    @abstractmethod
    def source_name(self) -> str:
        ...


class GovernmentProcurementCrawler(PublicDemandCrawler):
    """
    政府采购需求爬虫。
    数据源: http://www.ccgp.gov.cn/
    采集各级政府部门的采购需求公告。
    """
    @property
    def source_name(self) -> str:
        return "政府采购需求公告"

    async def search(self, keywords: list[str] = None, limit: int = 50) -> list[DiscoveredDemand]:
        logger.info(f"[ProcurementDemand] 搜索政府采购需求")
        # 中国政府采购网公开数据
        # 实际使用 Crawl4AI 解析 HTML 搜索结果
        # 格式: 项目名称 + 采购内容 + 预算 + 截止日期
        return []


class OpenInnovationCrawler(PublicDemandCrawler):
    """
    开放创新挑战平台爬虫。
    数据源:
    - HeroX (herox.com) — 全球创新挑战
    - XPRIZE (xprize.org) — 重大挑战
    - InnoCentive (innocentive.com) — 企业技术需求
    - 中国技术交易平台
    """
    @property
    def source_name(self) -> str:
        return "开放创新挑战"

    async def search(self, keywords: list[str] = None, limit: int = 50) -> list[DiscoveredDemand]:
        logger.info(f"[OpenInnovation] 搜索创新挑战")
        candidates = []

        # HeroX API (公开，RSS格式)
        try:
            import httpx
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get("https://www.herox.com/challenges/rss")
                if resp.status_code == 200:
                    # 解析 RSS → 提取标题/描述/奖励/截止日期
                    import xml.etree.ElementTree as ET
                    root = ET.fromstring(resp.text)
                    for item in root.findall(".//item")[:limit]:
                        title = item.findtext("title", "")
                        desc = item.findtext("description", "")
                        link = item.findtext("link", "")
                        if title and desc:
                            candidates.append(DiscoveredDemand(
                                source="HeroX",
                                source_url=link,
                                raw_text=f"{title}: {desc[:500]}",
                                inferred_category="方案征集",
                            ))
        except Exception as e:
            logger.warning(f"[HeroX] 爬取失败: {e}")

        logger.info(f"[OpenInnovation] 发现 {len(candidates)} 条挑战")
        return candidates


class ResearchFundingCrawler(PublicDemandCrawler):
    """
    科研基金指南爬虫。
    数据源:
    - 国家自然科学基金 (nsfc.gov.cn) 项目指南
    - 国家重点研发计划指南
    - EU Horizon Europe calls
    - NSF funding opportunities
    """
    @property
    def source_name(self) -> str:
        return "科研基金指南"

    async def search(self, keywords: list[str] = None, limit: int = 50) -> list[DiscoveredDemand]:
        logger.info(f"[ResearchFunding] 搜索科研基金指南")
        # 基金指南本质上就是"国家/机构的需求"——他们需要解决特定科学问题
        return []


class TechForumCrawler(PublicDemandCrawler):
    """
    技术论坛求助帖爬虫。
    数据源:
    - Stack Overflow / Stack Exchange (技术问题)
    - 知乎 / CSDN 技术求助
    - GitHub Issues (功能请求 = 需求)
    """
    @property
    def source_name(self) -> str:
        return "技术社区求助"

    async def search(self, keywords: list[str] = None, limit: int = 50) -> list[DiscoveredDemand]:
        logger.info(f"[TechForum] 搜索技术求助")
        return []


# ============================================================
# 主引擎
# ============================================================

class DemandDiscoveryEngine:
    """需求发现主引擎"""

    def __init__(self):
        self.crawlers: list[PublicDemandCrawler] = [
            GovernmentProcurementCrawler(),
            OpenInnovationCrawler(),
            ResearchFundingCrawler(),
            TechForumCrawler(),
        ]

    async def run(self, keywords: list[str] = None, limit: int = 100,
                  domains: list[str] = None) -> list[DiscoveredDemand]:
        """
        运行需求发现流程。
        domains: 筛选特定数据源 (procurement / innovation / research / forum)
        """
        all_results = []

        for crawler in self.crawlers:
            if domains and crawler.source_name not in domains:
                continue
            try:
                results = await crawler.search(keywords, limit=limit)
                all_results.extend(results)
                logger.info(f"[DemandDiscovery] {crawler.source_name}: {len(results)} 条")
            except Exception as e:
                logger.error(f"[DemandDiscovery] {crawler.source_name} 异常: {e}")

        # 去重
        seen = set()
        deduped = []
        for d in all_results:
            fp = d.fingerprint
            if fp not in seen:
                seen.add(fp)
                deduped.append(d)

        logger.info(f"[DemandDiscovery] 去重后: {len(deduped)} 条 (原始: {len(all_results)})")
        return deduped

    async def discover_and_publish(self, keywords: list[str] = None,
                                     limit: int = 100, auto_publish: bool = False):
        """发现需求并入库 (标记为公开发现)"""
        demands = await self.run(keywords, limit)
        results = []
        for d in demands:
            results.append(d.to_db_dict())
            logger.info(f"[DemandDiscovery] 发现需求: {d.raw_text[:60]}... [来源: {d.source}]")
        return results


# ============================================================
# 数据源总览（文档用）
# ============================================================

DATA_SOURCES = {
    "政府采购": {
        "url": "http://www.ccgp.gov.cn/",
        "type": "公开招标需求",
        "content": "项目名称、采购内容、预算金额、截止日期、采购单位",
        "update_frequency": "每日更新",
        "language": "zh",
    },
    "HeroX": {
        "url": "https://www.herox.com/",
        "type": "全球创新挑战",
        "content": "挑战标题、详细描述、奖金额度、截止日期、主办方",
        "update_frequency": "实时",
        "language": "en",
    },
    "XPRIZE": {
        "url": "https://www.xprize.org/",
        "type": "重大全球挑战",
        "content": "挑战目标、规则、奖金、时间线",
        "update_frequency": "按需发布",
        "language": "en",
    },
    "InnoCentive": {
        "url": "https://www.innocentive.com/",
        "type": "企业技术需求",
        "content": "问题描述、求解要求、奖励",
        "update_frequency": "实时",
        "language": "en",
    },
    "国家自然科学基金": {
        "url": "https://www.nsfc.gov.cn/",
        "type": "科研基金指南",
        "content": "资助方向、研究目标、经费额度、申请要求",
        "update_frequency": "年度发布",
        "language": "zh",
    },
    "NSF": {
        "url": "https://www.nsf.gov/funding/",
        "type": "科研资助",
        "content": "Funding opportunities, program descriptions",
        "update_frequency": "持续更新",
        "language": "en",
    },
    "EU Horizon": {
        "url": "https://ec.europa.eu/info/funding-tenders/",
        "type": "欧盟科研资助",
        "content": "Call topics, budgets, deadlines",
        "update_frequency": "按周期发布",
        "language": "en",
    },
    "Stack Exchange": {
        "url": "https://stackexchange.com/",
        "type": "技术求助",
        "content": "问题标题、详细描述、标签",
        "update_frequency": "实时",
        "language": "en",
    },
    "GitHub Issues": {
        "url": "https://github.com/",
        "type": "功能需求",
        "content": "Feature requests, bug reports, enhancement proposals",
        "update_frequency": "实时",
        "language": "en",
    },
}

demand_discovery_engine = DemandDiscoveryEngine()
