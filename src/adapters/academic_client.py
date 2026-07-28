"""
学术信息检索客户端 v2 — 包裹 8 个免费学术 API + 1 个资助 API。
新增：arXiv、Europe PMC、DOAJ、Zenodo
原有：PubMed、CrossRef、OpenAlex、Semantic Scholar、Grants.gov
"""
import json
import logging
import re
import asyncio
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# API endpoints
NCBI_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
CROSSREF_BASE = "https://api.crossref.org"
OPENALEX_BASE = "https://api.openalex.org"
SEMANTIC_BASE = "https://api.semanticscholar.org/graph/v1"
GRANTS_BASE = "https://www.grants.gov/api-gateway/v2"
ARXIV_BASE = "https://export.arxiv.org/api/query"
EUROPE_PMC_BASE = "https://www.ebi.ac.uk/europepmc/webservices/rest"
DOAJ_BASE = "https://doaj.org/api"
ZENODO_BASE = "https://zenodo.org/api"


class AcademicClient:
    """统一学术信息检索客户端 v2 — 8论文源 + 1资助源"""

    def __init__(self, ncbi_api_key: str = "", semantic_api_key: str = ""):
        self.ncbi_api_key = ncbi_api_key
        self.semantic_api_key = semantic_api_key
        self._client = httpx.AsyncClient(timeout=30.0)

    # ── 论文搜索（统一入口） ────────────────────────────────

    async def search_papers(
        self, query: str, limit: int = 10, source: str = "all"
    ) -> list[dict]:
        """跨库论文搜索。source: all | pubmed | crossref | openalex | semantic | arxiv | europepmc | doaj | zenodo"""
        tasks = []
        if source in ("all", "pubmed"):
            tasks.append(("PubMed", self._search_pubmed(query, limit)))
        if source in ("all", "crossref"):
            tasks.append(("CrossRef", self._search_crossref(query, limit)))
        if source in ("all", "openalex"):
            tasks.append(("OpenAlex", self._search_openalex(query, limit)))
        if source in ("all", "semantic"):
            tasks.append(("Semantic Scholar", self._search_semantic(query, limit)))
        if source in ("all", "arxiv"):
            tasks.append(("arXiv", self._search_arxiv(query, limit)))
        if source in ("all", "europepmc"):
            tasks.append(("Europe PMC", self._search_europe_pmc(query, limit)))
        if source in ("all", "doaj"):
            tasks.append(("DOAJ", self._search_doaj(query, limit)))
        if source in ("all", "zenodo"):
            tasks.append(("Zenodo", self._search_zenodo(query, limit)))

        results = []
        # 并行执行所有源
        gathered = await asyncio.gather(*[coro for _, coro in tasks], return_exceptions=True)
        for (name, _), result in zip(tasks, gathered):
            if isinstance(result, Exception):
                logger.warning(f"[AcademicClient] source {name} failed: {result}")
            else:
                results.extend(result)

        # 按年份降序去重
        seen_titles = set()
        deduped = []
        for r in sorted(results, key=lambda x: -(x.get("year") or 0)):
            title_norm = (r.get("title") or "").strip().lower()[:80]
            if title_norm and title_norm not in seen_titles:
                seen_titles.add(title_norm)
                deduped.append(r)
        return deduped[:limit] if source == "all" else deduped

    # ── PubMed（NCBI E-utilities） ──────────────────────────

    async def _search_pubmed(self, query: str, limit: int) -> list[dict]:
        params = {"db": "pubmed", "term": query, "retmax": min(limit, 50), "retmode": "json", "sort": "relevance"}
        if self.ncbi_api_key:
            params["api_key"] = self.ncbi_api_key
        r = await self._client.get(f"{NCBI_BASE}/esearch.fcgi", params=params)
        r.raise_for_status()
        id_list = r.json().get("esearchresult", {}).get("idlist", [])
        if not id_list:
            return []

        fetch_params = {"db": "pubmed", "id": ",".join(id_list[:min(limit, 20)]), "retmode": "xml"}
        if self.ncbi_api_key:
            fetch_params["api_key"] = self.ncbi_api_key
        fr = await self._client.get(f"{NCBI_BASE}/efetch.fcgi", params=fetch_params)
        fr.raise_for_status()

        results = []
        for art in re.findall(r"<PubmedArticle>(.*?)</PubmedArticle>", fr.text, re.DOTALL):
            pmid = (re.search(r"<PMID(?:[^>]*)>(\d+)</PMID>", art) or [None, ""])[1]
            title = re.sub(r"<[^>]+>", "", (re.search(r"<ArticleTitle>(.*?)</ArticleTitle>", art, re.DOTALL) or [None, ""])[1] or "").strip()
            journal = re.sub(r"<[^>]+>", "", (re.search(r"<Title>(.*?)</Title>", art) or [None, ""])[1] or "").strip()
            year = (re.search(r"<PubDate>(?:.*?<Year>)?(\d{4})", art) or [None, ""])[1]
            abstract = re.sub(r"<[^>]+>", "", (re.search(r"<AbstractText[^>]*>(.*?)</AbstractText>", art, re.DOTALL) or [None, ""])[1] or "").strip()
            doi = (re.search(r'<ArticleId IdType="doi">(.*?)</ArticleId>', art) or [None, ""])[1]
            results.append({"id": pmid, "title": title or "(无标题)", "journal": journal, "year": int(year) if year and year.isdigit() else 0,
                           "doi": doi, "abstract": abstract[:500], "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else "",
                           "source": "PubMed", "authors": []})
        return results

    # ── CrossRef ───────────────────────────────────────────

    async def _search_crossref(self, query: str, limit: int) -> list[dict]:
        params = {"query": query, "rows": min(limit, 20), "sort": "relevance", "order": "desc"}
        r = await self._client.get(f"{CROSSREF_BASE}/works", params=params)
        r.raise_for_status()
        results = []
        for item in r.json().get("message", {}).get("items", []):
            doi = item.get("DOI", "")
            title = (item.get("title") or [""])[0]
            year = (item.get("published-print") or item.get("published-online") or {}).get("date-parts", [[0]])[0][0]
            authors = [(a.get("given", "") + " " + a.get("family", "")).strip() for a in item.get("author", [])][:5]
            results.append({"id": doi, "title": title or "(无标题)", "journal": (item.get("container-title") or [""])[0],
                           "year": year or 0, "doi": doi, "abstract": (item.get("abstract") or "")[:500],
                           "url": f"https://doi.org/{doi}" if doi else "", "source": "CrossRef", "authors": authors})
        return results

    # ── OpenAlex ───────────────────────────────────────────

    async def _search_openalex(self, query: str, limit: int) -> list[dict]:
        params = {"search": query, "per_page": min(limit, 25), "sort": "relevance_score:desc"}
        r = await self._client.get(f"{OPENALEX_BASE}/works", params=params)
        r.raise_for_status()
        results = []
        for item in r.json().get("results", []):
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
                results.append({"id": item.get("id", ""), "title": item.get("title", "(无标题)"),
                               "journal": source_info.get("display_name", ""), "year": item.get("publication_year") or 0,
                               "doi": doi, "abstract": self._reconstruct_abstract(item.get("abstract_inverted_index")) if item.get("abstract_inverted_index") else "",
                               "url": item.get("doi") or f"https://openalex.org/{item.get('id', '')}",
                               "source": "OpenAlex", "authors": authors[:5], "cited_by": item.get("cited_by_count", 0)})
            except Exception as e:
                logger.warning(f"[OpenAlex] skip: {e}")
        return results

    def _reconstruct_abstract(self, inv_index: dict) -> str:
        if not inv_index:
            return ""
        words = [(pos, word) for word, positions in inv_index.items() for pos in positions]
        words.sort(key=lambda x: x[0])
        return " ".join(w[1] for w in words)[:500]

    # ── Semantic Scholar ───────────────────────────────────

    async def _search_semantic(self, query: str, limit: int) -> list[dict]:
        headers = {}
        if self.semantic_api_key:
            headers["x-api-key"] = self.semantic_api_key
        params = {"query": query, "limit": min(limit, 10), "fields": "title,externalIds,authors,year,journal,abstract,url,citationCount"}
        try:
            await asyncio.sleep(1.1)  # rate limit: 1 req/s without key
            r = await self._client.get(f"{SEMANTIC_BASE}/paper/search", params=params, headers=headers)
            r.raise_for_status()
            results = []
            for item in r.json().get("data", []):
                results.append({"id": item.get("paperId", ""), "title": item.get("title", "(无标题)"),
                               "journal": (item.get("journal") or {}).get("name", ""), "year": item.get("year") or 0,
                               "doi": (item.get("externalIds") or {}).get("DOI", ""),
                               "abstract": (item.get("abstract") or "")[:500], "url": item.get("url", ""),
                               "source": "Semantic Scholar",
                               "authors": [a.get("name", "") for a in (item.get("authors") or [])][:5],
                               "cited_by": item.get("citationCount", 0)})
            return results
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                logger.warning("[Semantic Scholar] rate limited")
            return []

    # ── arXiv（新增） ──────────────────────────────────────

    async def _search_arxiv(self, query: str, limit: int) -> list[dict]:
        """arXiv 预印本搜索 — CS/物理/数学/生物/统计，300万+篇"""
        params = {"search_query": f"all:{query}", "max_results": min(limit, 20), "sortBy": "relevance", "sortOrder": "descending"}
        r = await self._client.get(ARXIV_BASE, params=params)
        r.raise_for_status()

        results = []
        for entry in re.findall(r"<entry>(.*?)</entry>", r.text, re.DOTALL):
            arxiv_id = (re.search(r"<id>(.*?)</id>", entry) or [None, ""])[1].strip()
            # Extract short ID (e.g. 2401.12345 from http://arxiv.org/abs/2401.12345v1)
            if arxiv_id:
                arxiv_id = arxiv_id.split("/abs/")[-1] if "/abs/" in arxiv_id else arxiv_id
            title = re.sub(r"<[^>]+>", "", (re.search(r"<title>(.*?)</title>", entry, re.DOTALL) or [None, ""])[1] or "").strip()
            summary = re.sub(r"<[^>]+>", "", (re.search(r"<summary>(.*?)</summary>", entry, re.DOTALL) or [None, ""])[1] or "").strip()
            published = (re.search(r"<published>(\d{4})", entry) or [None, ""])[1]
            authors = re.findall(r"<name>(.*?)</name>", entry)
            doi = (re.search(r'<arxiv:doi[^>]*>(.*?)</arxiv:doi>', entry) or [None, ""])[1]
            pdf_url = (re.search(r'<link[^>]*title="pdf"[^>]*href="([^"]+)"', entry) or [None, ""])[1]

            # Extract primary category
            cat = (re.search(r'<arxiv:primary_category[^>]*term="([^"]+)"', entry) or [None, ""])[1]

            results.append({
                "id": arxiv_id, "title": title or "(无标题)",
                "journal": f"arXiv [{cat}]" if cat else "arXiv",
                "year": int(published) if published else 0,
                "doi": doi, "abstract": summary[:500],
                "url": f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else "",
                "pdf_url": pdf_url, "source": "arXiv", "authors": authors[:5],
            })
        return results

    # ── Europe PMC（新增） ─────────────────────────────────

    async def _search_europe_pmc(self, query: str, limit: int) -> list[dict]:
        """Europe PMC — 生物医学全文，260万+篇，含开放获取全文链接"""
        params = {"query": query, "format": "json", "pageSize": min(limit, 25)}
        r = await self._client.get(f"{EUROPE_PMC_BASE}/search", params=params)
        r.raise_for_status()
        data = r.json()
        results = []
        for item in data.get("resultList", {}).get("result", []):
            pmid = item.get("pmid", "")
            pmcid = item.get("pmcid", "")
            doi = item.get("doi", "")
            title = item.get("title", "")
            journal = item.get("journalTitle", "")
            year = item.get("pubYear", "")
            abstract = item.get("abstractText", "") or ""
            authors_str = item.get("authorString", "")
            authors = [a.strip() for a in authors_str.split(",")] if authors_str else []

            # Open access full text URL
            url = f"https://europepmc.org/article/{('MED' if pmid else 'PMC')}/{(pmid or pmcid)}" if (pmid or pmcid) else ""
            if doi and not url:
                url = f"https://doi.org/{doi}"

            results.append({
                "id": pmcid or pmid or doi, "title": title or "(无标题)",
                "journal": journal, "year": int(year) if year and year.isdigit() else 0,
                "doi": doi, "abstract": abstract[:500], "url": url,
                "source": "Europe PMC", "authors": authors[:5],
                "cited_by": item.get("citedByCount", 0),
                "is_oa": item.get("isOpenAccess", "N") == "Y",
            })
        return results

    # ── DOAJ（新增） ───────────────────────────────────────

    async def _search_doaj(self, query: str, limit: int) -> list[dict]:
        """DOAJ — 开放获取期刊目录，9万+篇全文开放论文"""
        params = {"pageSize": min(limit, 25), "page": 1}
        r = await self._client.get(f"{DOAJ_BASE}/search/articles/{query}", params=params)
        r.raise_for_status()
        data = r.json()
        results = []
        for item in data.get("results", []):
            bib = item.get("bibjson", {})
            title = bib.get("title", "")
            journal = (bib.get("journal", {}) or {}).get("title", "")
            year = (bib.get("year", "") or "")
            doi = bib.get("identifier", [{}])[0].get("id", "") if bib.get("identifier") else ""
            abstract = bib.get("abstract", "") or ""
            authors = [a.get("name", "") for a in (bib.get("author", {}) or {}).get("authors", [])] if isinstance(bib.get("author"), dict) else [a.get("name", "") for a in bib.get("author", [])]
            links = bib.get("link", [])
            url = links[0].get("url", "") if links else ""

            results.append({
                "id": item.get("id", ""), "title": title or "(无标题)",
                "journal": journal, "year": int(year) if year and year.isdigit() else 0,
                "doi": doi, "abstract": abstract[:500],
                "url": url, "source": "DOAJ", "authors": authors[:5],
                "is_oa": True,
            })
        return results

    # ── Zenodo（新增） ─────────────────────────────────────

    async def _search_zenodo(self, query: str, limit: int) -> list[dict]:
        """Zenodo — 科研数据集/软件/报告/论文，28万+条开放记录"""
        params = {"q": query, "size": min(limit, 25), "sort": "bestmatch"}
        r = await self._client.get(f"{ZENODO_BASE}/records", params=params)
        r.raise_for_status()
        data = r.json()
        results = []
        for hit in data.get("hits", {}).get("hits", []):
            meta = hit.get("metadata", {})
            title = meta.get("title", "")
            doi = hit.get("doi", "") or meta.get("doi", "")
            pub_date = meta.get("publication_date", "")
            year = pub_date[:4] if pub_date else ""
            desc = meta.get("description", "") or ""
            # Clean HTML
            desc = re.sub(r"<[^>]+>", "", desc).strip()
            authors = [c.get("name", "") for c in meta.get("creators", [])][:5]
            resource_type = (meta.get("resource_type", {}) or {}).get("title", "")
            zenodo_id = hit.get("id", "")

            results.append({
                "id": str(zenodo_id), "title": title or "(无标题)",
                "journal": f"Zenodo [{resource_type}]" if resource_type else "Zenodo",
                "year": int(year) if year and year.isdigit() else 0,
                "doi": doi, "abstract": desc[:500],
                "url": f"https://zenodo.org/records/{zenodo_id}" if zenodo_id else "",
                "source": "Zenodo", "authors": authors,
                "is_oa": True,
            })
        return results

    # ── 资助机会搜索 ──────────────────────────────────────

    async def search_funding(self, query: str, limit: int = 10) -> list[dict]:
        results = await self._search_grants_gov(query, limit)
        return results

    async def _search_grants_gov(self, query: str, limit: int) -> list[dict]:
        try:
            params = {"keyword": query, "oppStatuses": "forecasted,posted", "rows": min(limit, 25), "start": 0}
            r = await self._client.get(
                "https://www.grants.gov/grants-api/ws/opportunities/search",
                params=params, headers={"accept": "application/json"}, timeout=15.0,
            )
            if r.status_code == 200:
                items = r.json().get("oppHits", []) or r.json().get("opportunities", [])
                results = []
                for item in items:
                    opp = item.get("opportunity", {}) or item
                    results.append({
                        "id": opp.get("opportunityId", ""), "title": opp.get("opportunityTitle", ""),
                        "agency": opp.get("agency", ""), "status": opp.get("oppStatus", ""),
                        "close_date": opp.get("closeDate", ""), "open_date": opp.get("openDate", ""),
                        "description": (opp.get("description", "") or "")[:500],
                        "url": f"https://www.grants.gov/view-opportunity.html?oppId={opp.get('opportunityId', '')}",
                        "source": "Grants.gov",
                    })
                if results:
                    return results
        except Exception as e:
            logger.warning(f"[Grants.gov] failed: {e}")

        # Fallback: CrossRef Funding
        try:
            params = {"query": f"funding {query}", "rows": min(limit, 10), "sort": "published"}
            r = await self._client.get(f"{CROSSREF_BASE}/works", params=params)
            r.raise_for_status()
            results = []
            for item in r.json().get("message", {}).get("items", []):
                funder_list = item.get("funder") or []
                funder = funder_list[0].get("name", "") if funder_list and funder_list[0] else ""
                if not funder:
                    continue
                doi = item.get("DOI", "")
                results.append({
                    "id": doi, "title": (item.get("title") or [""])[0], "funder": funder,
                    "year": (item.get("published-print") or item.get("published-online") or {}).get("date-parts", [[0]])[0][0],
                    "description": f"相关研究论文: {(item.get('abstract') or '')[:300]}",
                    "url": f"https://doi.org/{doi}", "source": "CrossRef Funding",
                })
            return results
        except Exception as e:
            logger.warning(f"[CrossRef Funding] failed: {e}")
            return []

    # ── 研究总结 ──────────────────────────────────────────

    async def research_summary(self, topic: str, llm_summarize_fn=None) -> dict:
        papers = await self.search_papers(topic, limit=8)
        funding = await self.search_funding(topic, limit=5)

        _STOP_WORDS = {
            "the", "and", "for", "with", "from", "that", "this", "are", "was", "were",
            "been", "have", "has", "had", "not", "but", "its", "all", "can", "new",
            "how", "why", "what", "which", "their", "your", "our", "about", "also",
            "more", "than", "into", "over", "such", "each", "only", "other", "some",
            "using", "based", "through", "between", "during", "before", "after",
            "under", "very", "just", "one", "two", "three", "first", "second", "third",
        }
        keywords = set()
        for p in papers:
            for word in (p.get("title") or "").split():
                word = word.strip(" ,.;:!?()-[]{}'\"")
                if len(word) > 3 and word.lower() not in _STOP_WORDS:
                    keywords.add(word.lower())

        # 按来源统计
        source_counts = {}
        for p in papers:
            src = p.get("source", "unknown")
            source_counts[src] = source_counts.get(src, 0) + 1

        summary_data = {
            "topic": topic, "paper_count": len(papers), "papers": papers[:8],
            "funding_count": len(funding), "funding": funding[:5],
            "keywords": sorted(keywords)[:20],
            "year_range": (
                min((p.get("year") or 9999) for p in papers) if papers else 0,
                max((p.get("year") or 0) for p in papers) if papers else 0,
            ),
            "source_counts": source_counts,
        }

        if llm_summarize_fn and papers:
            try:
                prompt = f"请对以下研究主题进行简要总结（200-300字中文）：\n\n研究主题：{topic}\n\n检索到 {len(papers)} 篇相关论文，年份范围 {summary_data['year_range'][0]}-{summary_data['year_range'][1]}。\n来源分布：{source_counts}\n\n最新论文标题：\n"
                for i, p in enumerate(papers[:5], 1):
                    prompt += f"{i}. {p['title']} ({p['year']}, {p['journal']})\n"
                if funding:
                    prompt += f"\n发现 {len(funding)} 条相关资助机会。\n"
                summary_data["summary"] = await llm_summarize_fn(prompt)
            except Exception as e:
                logger.warning(f"[ResearchSummary] LLM failed: {e}")
                summary_data["summary"] = ""

        return summary_data

    async def close(self):
        await self._client.aclose()
