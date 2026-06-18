"""
学术信息检索客户端 — 包裹 PubMed、CrossRef、OpenAlex、Semantic Scholar、Grants.gov 等免费 API。
为科研工作台和 MCP 工具提供统一查询接口。
"""
import json
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# NCBI E-utilities 频率：无 key 3 req/s，有 key 10 req/s
NCBI_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
CROSSREF_BASE = "https://api.crossref.org"
OPENALEX_BASE = "https://api.openalex.org"
SEMANTIC_BASE = "https://api.semanticscholar.org/graph/v1"
GRANTS_BASE = "https://www.grants.gov/api-gateway/v2"


class AcademicClient:
    """统一学术信息检索客户端"""

    def __init__(self, ncbi_api_key: str = "", semantic_api_key: str = ""):
        self.ncbi_api_key = ncbi_api_key
        self.semantic_api_key = semantic_api_key
        self._client = httpx.AsyncClient(timeout=30.0)

    # ── 论文搜索 ──────────────────────────────────────────

    async def search_papers(
        self, query: str, limit: int = 10, source: str = "all"
    ) -> list[dict]:
        """跨库论文搜索。source: all | pubmed | crossref | openalex | semantic"""
        tasks = []
        if source in ("all", "pubmed"):
            tasks.append(("pubmed", self._search_pubmed(query, limit)))
        if source in ("all", "crossref"):
            tasks.append(("crossref", self._search_crossref(query, limit)))
        if source in ("all", "openalex"):
            tasks.append(("openalex", self._search_openalex(query, limit)))
        if source in ("all", "semantic"):
            tasks.append(("semantic", self._search_semantic(query, limit)))

        results = []
        for name, coro in tasks:
            try:
                results.extend(await coro)
            except Exception as e:
                logger.warning(f"[AcademicClient] source {name} failed: {e}")
                import traceback
                logger.debug(traceback.format_exc())

        # 按年份降序去重
        seen_titles = set()
        deduped = []
        for r in sorted(results, key=lambda x: -(x.get("year") or 0)):
            title_norm = (r.get("title") or "").strip().lower()[:80]
            if title_norm and title_norm not in seen_titles:
                seen_titles.add(title_norm)
                deduped.append(r)
        return deduped[:limit]

    async def _search_pubmed(self, query: str, limit: int) -> list[dict]:
        """PubMed 搜索（NCBI E-utilities）"""
        params = {
            "db": "pubmed",
            "term": query,
            "retmax": min(limit, 50),
            "retmode": "json",
            "sort": "relevance",
        }
        if self.ncbi_api_key:
            params["api_key"] = self.ncbi_api_key

        r = await self._client.get(f"{NCBI_BASE}/esearch.fcgi", params=params)
        r.raise_for_status()
        data = r.json()
        id_list = data.get("esearchresult", {}).get("idlist", [])
        if not id_list:
            return []

        # 获取详情
        fetch_params = {
            "db": "pubmed",
            "id": ",".join(id_list[:min(limit, 20)]),
            "retmode": "xml",
        }
        if self.ncbi_api_key:
            fetch_params["api_key"] = self.ncbi_api_key

        fr = await self._client.get(f"{NCBI_BASE}/efetch.fcgi", params=fetch_params)
        fr.raise_for_status()
        xml_text = fr.text

        # 简易 XML 解析（提取标题、期刊、年份、PMID、摘要）
        results = []
        import re

        articles = re.findall(r"<PubmedArticle>(.*?)</PubmedArticle>", xml_text, re.DOTALL)
        for art in articles:
            pmid = (re.search(r"<PMID(?:[^>]*)>(\d+)</PMID>", art) or [None, ""]).group(1)
            title = (re.search(r"<ArticleTitle>(.*?)</ArticleTitle>", art, re.DOTALL) or [None, ""]).group(1)
            journal = (re.search(r"<Title>(.*?)</Title>", art) or [None, ""]).group(1)
            year = (re.search(r"<PubDate>(?:.*?<Year>)?(\d{4})", art) or [None, ""]).group(1)
            abstract = (re.search(r"<AbstractText[^>]*>(.*?)</AbstractText>", art, re.DOTALL) or [None, ""]).group(1)
            doi_tag = re.search(r"<ArticleId IdType=\"doi\">(.*?)</ArticleId>", art)
            doi = doi_tag.group(1) if doi_tag else ""

            # 清洗 HTML 标签
            title = re.sub(r"<[^>]+>", "", title).strip() if title else ""
            abstract = re.sub(r"<[^>]+>", "", abstract).strip() if abstract else ""
            journal = re.sub(r"<[^>]+>", "", journal).strip() if journal else ""

            results.append({
                "id": pmid,
                "title": title or "(无标题)",
                "journal": journal or "",
                "year": int(year) if year and year.isdigit() else 0,
                "doi": doi,
                "abstract": abstract[:500] if abstract else "",
                "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else "",
                "source": "PubMed",
                "authors": [],
            })
        return results

    async def _search_crossref(self, query: str, limit: int) -> list[dict]:
        """CrossRef 搜索"""
        params = {
            "query": query,
            "rows": min(limit, 20),
            "sort": "relevance",
            "order": "desc",
        }
        r = await self._client.get(f"{CROSSREF_BASE}/works", params=params)
        r.raise_for_status()
        data = r.json()
        items = data.get("message", {}).get("items", [])
        results = []
        for item in items:
            doi = item.get("DOI", "")
            title = (item.get("title") or [""])[0]
            year = (item.get("published-print") or item.get("published-online") or {}).get("date-parts", [[0]])[0][0]
            authors = [
                (a.get("given", "") + " " + a.get("family", "")).strip()
                for a in item.get("author", [])
            ][:5]
            results.append({
                "id": doi,
                "title": title or "(无标题)",
                "journal": (item.get("container-title") or [""])[0],
                "year": year or 0,
                "doi": doi,
                "abstract": (item.get("abstract") or "")[:500],
                "url": f"https://doi.org/{doi}" if doi else "",
                "source": "CrossRef",
                "authors": authors,
            })
        return results

    async def _search_openalex(self, query: str, limit: int) -> list[dict]:
        """OpenAlex 搜索（完全免费，无 key 要求）"""
        params = {
            "search": query,
            "per_page": min(limit, 25),
            "sort": "relevance_score:desc",
        }
        r = await self._client.get(f"{OPENALEX_BASE}/works", params=params)
        r.raise_for_status()
        data = r.json()
        results = []
        for item in data.get("results", []):
            try:
                doi = (item.get("doi") or "").replace("https://doi.org/", "")
                primary_loc = item.get("primary_location") or {}
                source_info = (primary_loc.get("source") or {}) if isinstance(primary_loc, dict) else {}
                authors = []
                for a in (item.get("authorships") or []):
                    if isinstance(a, dict):
                        author = a.get("author") or {}
                        if isinstance(author, dict):
                            authors.append(author.get("display_name", ""))
                results.append({
                    "id": item.get("id", ""),
                    "title": item.get("title", "(无标题)"),
                    "journal": source_info.get("display_name", ""),
                    "year": item.get("publication_year") or 0,
                    "doi": doi,
                    "abstract": (item.get("abstract_inverted_index") and self._reconstruct_abstract(item["abstract_inverted_index"])) or "",
                    "url": item.get("doi") or f"https://openalex.org/{item.get('id', '')}",
                    "source": "OpenAlex",
                    "authors": authors[:5],
                    "cited_by": item.get("cited_by_count", 0),
                })
            except Exception as e:
                logger.warning(f"[OpenAlex] 跳过一条结果: {e}")
                continue
        return results

    def _reconstruct_abstract(self, inv_index: dict) -> str:
        """从 inverted index 重建摘要文本"""
        if not inv_index:
            return ""
        words = []
        for word, positions in inv_index.items():
            for pos in positions:
                words.append((pos, word))
        words.sort(key=lambda x: x[0])
        return " ".join(w[1] for w in words)[:500]

    async def _search_semantic(self, query: str, limit: int) -> list[dict]:
        """Semantic Scholar 搜索（无 key 限制 1 req/s，建议每次调用间隔 1s）"""
        headers = {}
        if self.semantic_api_key:
            headers["x-api-key"] = self.semantic_api_key
        params = {
            "query": query,
            "limit": min(limit, 10),
            "fields": "title,externalIds,authors,year,journal,abstract,url,citationCount",
        }
        try:
            # Semantic Scholar 无 key 时限制 1 req/s
            import asyncio
            await asyncio.sleep(1.1)  # 确保不触发限流

            r = await self._client.get(
                f"{SEMANTIC_BASE}/paper/search", params=params, headers=headers
            )
            r.raise_for_status()
            data = r.json()
            results = []
            for item in data.get("data", []):
                results.append({
                    "id": item.get("paperId", ""),
                    "title": item.get("title", "(无标题)"),
                    "journal": (item.get("journal") or {}).get("name", ""),
                    "year": item.get("year") or 0,
                    "doi": (item.get("externalIds") or {}).get("DOI", ""),
                    "abstract": (item.get("abstract") or "")[:500],
                    "url": item.get("url", ""),
                    "source": "Semantic Scholar",
                    "authors": [a.get("name", "") for a in (item.get("authors") or [])][:5],
                    "cited_by": item.get("citationCount", 0),
                })
            return results
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                logger.warning("[Semantic Scholar] rate limited, skipping")
            return []

    # ── 资助机会搜索 ──────────────────────────────────────

    async def search_funding(self, query: str, limit: int = 10) -> list[dict]:
        """资助机会搜索（Grants.gov API）"""
        results = await self._search_grants_gov(query, limit)
        return results

    async def _search_grants_gov(self, query: str, limit: int) -> list[dict]:
        """Grants.gov API v2 搜索 + CrossRef Funding fallback"""
        # 先试 Grants.gov
        try:
            params = {
                "keyword": query,
                "oppStatuses": "forecasted,posted",
                "rows": min(limit, 25),
                "start": 0,
            }
            r = await self._client.get(
                "https://www.grants.gov/grants-api/ws/opportunities/search",
                params=params,
                headers={"accept": "application/json"},
                timeout=15.0,
            )
            if r.status_code == 200:
                data = r.json()
                items = data.get("oppHits", []) or data.get("opportunities", [])
                results = []
                for item in items:
                    opp = item.get("opportunity", {}) or item
                    results.append({
                        "id": opp.get("opportunityId", ""),
                        "title": opp.get("opportunityTitle", ""),
                        "agency": opp.get("agency", ""),
                        "status": opp.get("oppStatus", ""),
                        "close_date": opp.get("closeDate", ""),
                        "open_date": opp.get("openDate", ""),
                        "description": (opp.get("description", "") or "")[:500],
                        "url": f"https://www.grants.gov/view-opportunity.html?oppId={opp.get('opportunityId', '')}",
                        "source": "Grants.gov",
                    })
                if results:
                    return results
        except Exception as e:
            logger.warning(f"[Grants.gov] API 查询失败: {e}")

        # Fallback: 用 CrossRef 查询基金资助相关论文
        params = {"query": f"funding {query}", "rows": min(limit, 10), "sort": "published"}
        try:
            r = await self._client.get(f"{CROSSREF_BASE}/works", params=params)
            r.raise_for_status()
            data = r.json()
            items = data.get("message", {}).get("items", [])
            results = []
            for item in items:
                funder_list = item.get("funder") or []
                funder = funder_list[0].get("name", "") if funder_list and funder_list[0] else ""
                award_list = item.get("award") or []
                award = award_list[0] if award_list else ""
                if not funder and not award:
                    continue
                results.append({
                    "id": item.get("DOI", ""),
                    "title": (item.get("title") or [""])[0],
                    "funder": funder,
                    "award_number": award,
                    "year": (item.get("published-print") or item.get("published-online") or {}).get("date-parts", [[0]])[0][0],
                    "description": f"相关研究论文: {(item.get('abstract') or '')[:300]}",
                    "url": f"https://doi.org/{item.get('DOI', '')}",
                    "source": "CrossRef Funding",
                })
            return results
        except Exception as e:
            logger.warning(f"[CrossRef Funding] 查询失败: {e}")
            return []

    # ── 研究总结 ──────────────────────────────────────────

    async def research_summary(self, topic: str, llm_summarize_fn=None) -> dict:
        """对研究主题进行综合检索并返回结构化总结。
        如果提供了 llm_summarize_fn，则用 LLM 生成总结文本。
        """
        # 并行搜索论文
        papers = await self.search_papers(topic, limit=8)

        # 并行搜索资助机会
        funding = await self.search_funding(topic, limit=5)

        # 提取关键词（从论文标题中提取，过滤停用词）
        _STOP_WORDS = {
            "the", "and", "for", "with", "from", "that", "this", "are",
            "was", "were", "been", "have", "has", "had", "not", "but",
            "its", "all", "can", "new", "how", "why", "what", "which",
            "their", "your", "our", "about", "also", "more", "than",
            "into", "over", "such", "each", "only", "other", "some",
            "using", "based", "through", "between", "during", "before",
            "after", "under", "very", "just", "one", "two", "three",
            "first", "second", "third", "this", "that",
        }
        keywords = set()
        for p in papers:
            for word in (p.get("title") or "").split():
                word = word.strip(" ,.;:!?()-[]{}'\"")
                if len(word) > 3 and word.lower() not in _STOP_WORDS:
                    keywords.add(word.lower())

        summary_data = {
            "topic": topic,
            "paper_count": len(papers),
            "papers": papers[:8],
            "funding_count": len(funding),
            "funding": funding[:5],
            "keywords": sorted(keywords)[:20],
            "year_range": (
                min((p.get("year") or 9999) for p in papers) if papers else 0,
                max((p.get("year") or 0) for p in papers) if papers else 0,
            ),
        }

        # 如果用 LLM 生成摘要
        if llm_summarize_fn and papers:
            try:
                prompt = f"""请对以下研究主题进行简要总结（200-300字中文）：

研究主题：{topic}

检索到 {len(papers)} 篇相关论文，年份范围 {summary_data['year_range'][0]}-{summary_data['year_range'][1]}。

最新论文标题：
"""
                for i, p in enumerate(papers[:5], 1):
                    prompt += f"{i}. {p['title']} ({p['year']}, {p['journal']})\n"

                if funding:
                    prompt += f"\n发现 {len(funding)} 条相关资助机会。\n"

                summary_text = await llm_summarize_fn(prompt)
                summary_data["summary"] = summary_text
            except Exception as e:
                logger.warning(f"[ResearchSummary] LLM 总结失败: {e}")
                summary_data["summary"] = ""

        return summary_data

    async def close(self):
        await self._client.aclose()
