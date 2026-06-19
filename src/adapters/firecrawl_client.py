"""
Firecrawl 适配器 — 替换 crawl4ai 作为主要爬虫。
支持网页抓取、全网搜索、结构化数据提取。
"""
import json
import logging
import os
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

FIRECRAWL_API_KEY = os.environ.get("FIRECRAWL_API_KEY", "")
FIRECRAWL_BASE = "https://api.firecrawl.dev/v1"


class FirecrawlClient:
    """Firecrawl API 客户端"""

    def __init__(self, api_key: str = ""):
        self.api_key = api_key or FIRECRAWL_API_KEY
        self.client = httpx.AsyncClient(
            base_url=FIRECRAWL_BASE,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            timeout=60.0,
        )

    async def scrape_url(self, url: str, extract_schema: dict = None) -> dict:
        """抓取单页 URL，可选提取结构化数据"""
        payload = {"url": url, "formats": ["markdown"], "onlyMainContent": True}
        if extract_schema:
            payload["formats"] = [{"type": "json", "schema": extract_schema, "prompt": "Extract the key information from this page"}]

        try:
            r = await self.client.post("/scrape", json=payload)
            r.raise_for_status()
            data = r.json()
            if data.get("success"):
                return {
                    "status": "ok",
                    "url": url,
                    "title": (data.get("data", {}).get("metadata", {}) or {}).get("title", ""),
                    "content": (data.get("data", {}) or {}).get("markdown", "")[:3000],
                }
            return {"status": "error", "reason": str(data)}
        except Exception as e:
            logger.error(f"Firecrawl scrape failed: {e}")
            return {"status": "error", "reason": str(e)}

    async def search_web(self, query: str, limit: int = 5) -> list[dict]:
        """全网搜索，返回结果列表"""
        try:
            r = await self.client.post("/search", json={
                "query": query,
                "limit": min(limit, 20),
                "lang": "zh",
                "scrapeOptions": {"formats": ["markdown"], "onlyMainContent": True},
            })
            r.raise_for_status()
            data = r.json()
            if data.get("success"):
                results = []
                for item in data.get("data", []):
                    results.append({
                        "url": item.get("url", ""),
                        "title": item.get("title", ""),
                        "description": item.get("description", "")[:300],
                    })
                return results
            return []
        except Exception as e:
            logger.error(f"Firecrawl search failed: {e}")
            return []

    async def search_patents(self, keywords: str, limit: int = 5) -> list[dict]:
        """搜索专利数据库"""
        queries = [
            f"site:patents.google.com OR site:epo.org {keywords}",
            f"site:cnipa.gov.cn OR site:cnpat.com.cn {keywords}",
            f"site:worldwide.espacenet.com {keywords}",
        ]
        results = []
        for q in queries:
            items = await self.search_web(q, limit=3)
            results.extend(items)
            if len(results) >= limit:
                break
        return results[:limit]

    async def search_procurement(self, keywords: str, limit: int = 5) -> list[dict]:
        """搜索政府采购"""
        queries = [
            f"site:ccgp.gov.cn {keywords}",
            f"site:gov.cn 采购 {keywords}",
        ]
        results = []
        for q in queries:
            items = await self.search_web(q, limit=3)
            results.extend(items)
            if len(results) >= limit:
                break
        return results[:limit]

    async def search_academic(self, keywords: str, limit: int = 5) -> list[dict]:
        """搜索学术论文"""
        queries = [
            f"site:arxiv.org {keywords}",
            f"site:scholar.google.com OR site:semanticscholar.org {keywords}",
        ]
        results = []
        for q in queries:
            items = await self.search_web(q, limit=3)
            results.extend(items)
            if len(results) >= limit:
                break
        return results[:limit]

    async def check_credits(self) -> dict:
        """检查剩余额度"""
        try:
            r = await self.client.get("/account/credits")
            r.raise_for_status()
            return r.json()
        except:
            return {"status": "error", "reason": "Failed to check credits"}


_firecrawl = None


def get_firecrawl() -> FirecrawlClient:
    global _firecrawl
    if _firecrawl is None:
        _firecrawl = FirecrawlClient()
    return _firecrawl

