#!/usr/bin/env python3
"""
需求链平台 — 联合国采购项目爬虫 v2.1
========================================
由于联合国各大机构（UNGM、WHO、UNDP）皆使用 JavaScript 渲染采购列表，
本爬虫直接运行 smart_crawler 风格的 Firecrawl 搜索查询来获取标书。

用法:
  python scripts/un_procurement_crawler.py            # 正式运行（需Firecrawl额度）
  python scripts/un_procurement_crawler.py --dry-run  # 仅打印搜索词（不入库）
"""
import json, sys, time, urllib.request
from datetime import datetime

# DuckDNS域名有时中断，用IP直连更稳定
API_BASE = "http://8.154.26.92:8080"
FIRECRAWL_KEY = "fc-e97094049296412bb87cc3946d515649"
DEEPSEEK_KEY = "sk-c32415bb5ae44cdc844f1b95f99e4544"

SEARCH_QUERIES = [
    # UNGM 采购招标
    'site:ungm.org "tender" OR "procurement notice" OR "solicitation" 2026',
    'site:ungm.org "expression of interest" OR "request for proposal" 2026',
    # WHO 招标
    'site:who.int "tender" OR "procurement" OR "request for" vaccine OR medicine OR equipment 2026',
    # UNICEF 供应品
    'site:unicef.org "supply" OR "procurement" OR "tender" vaccine OR medicine OR equipment 2026',
    # UNDP 开发计划署
    'site:undp.org procurement OR tender OR "request for proposal" 2026',
    # 联合国其他机构
    'site:fao.org procurement tender OR "invitation to bid" 2026',
    'site:wfp.org procurement tender OR "expression of interest" 2026',
    'site:unhcr.org procurement tender OR "invitation to bid" 2026',
]

DEMAND_PROMPT = """判断以下文本是否是一条真实的采购招标/标书公告。输出JSON:

如果是真实招标:
{"is_demand":true,"title":"中文标题","summary":"100字内中文摘要","category":"分类","tags":["标签"],"org":"发布机构"}

如果不是:
{"is_demand":false,"reason":"原因"}

分类选项: 生物医药|新能源|信息技术|交通运输|环境工程|农业科学|土木工程|安全科学|其他

输出纯JSON，无其他文字。"""

def log(msg):
    print(msg)
    sys.stdout.flush()

def http_post(url, payload, headers=None, timeout=30):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers or {}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))

def deepseek_filter(text):
    try:
        result = http_post(
            "https://api.deepseek.com/v1/chat/completions",
            {"model": "deepseek-chat", "messages": [
                {"role": "system", "content": DEMAND_PROMPT},
                {"role": "user", "content": text[:3000]},
            ], "temperature": 0.1, "max_tokens": 512},
            {"Authorization": f"Bearer {DEEPSEEK_KEY}", "Content-Type": "application/json"},
        )
        content = result["choices"][0]["message"]["content"].strip()
        content = content[content.find("{"):content.rfind("}")+1] if "{" in content else content
        return json.loads(content)
    except Exception as e:
        return {"is_demand": None, "reason": str(e)}

def firecrawl_search(query, limit=3):
    try:
        result = http_post(
            "https://api.firecrawl.dev/v1/search",
            {"query": query, "limit": limit,
             "scrapeOptions": {"formats": ["markdown"], "onlyMainContent": True}},
            {"Authorization": f"Bearer {FIRECRAWL_KEY}", "Content-Type": "application/json"},
        )
        if result.get("success"):
            return [{"url": i.get("url",""), "title": i.get("title",""),
                     "content": (i.get("markdown","") or i.get("description",""))[:2000]}
                    for i in result.get("data", [])]
    except Exception as e:
        log(f"     ⚠️ Firecrawl搜索失败: {e}")
    return []

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

def run(dry_run=False):
    log(f"{'='*60}")
    log(f"  联合国采购项目爬虫 v2.1 (Firecrawl搜索模式)")
    log(f"  时间: {datetime.now().isoformat()}")
    log(f"  模式: {'试跑(打印搜索词)' if dry_run else 'Firecrawl搜索入库'}")
    log(f"{'='*60}")
    
    if dry_run:
        log(f"\n📋 以下是本爬虫使用的 Firecrawl 搜索词:")
        for q in SEARCH_QUERIES:
            log(f"  • {q}")
        log(f"\n将这些搜索词添加到 smart_crawler.py 的 DEMAND_QUERIES 中即可运行。")
        with open("un_procurement_search_queries.txt", "w") as f:
            f.write("\n".join(SEARCH_QUERIES))
        return 0
    
    total = 0
    for query in SEARCH_QUERIES:
        log(f"\n🔍 搜索: {query}")
        results = firecrawl_search(query, limit=2)
        log(f"   结果: {len(results)}")
        for r in results:
            # DeepSeek判断
            analysis = deepseek_filter(f"{r['title']}\n{r['content'][:1000]}")
            if isinstance(analysis, dict) and analysis.get("is_demand"):
                log(f"   ✅ {analysis.get('title','')[:60]}")
                r2 = api_post("/api/auto-demand", {
                    "raw_text": f"{analysis.get('title','')}: {analysis.get('summary','')}\n来源: {analysis.get('org','UN采购')}",
                    "category": analysis.get("category","其他"),
                    "email": "crawler",
                })
                if r2.get("status") == "ok":
                    total += 1
                time.sleep(1)
            else:
                log(f"   ⏭ 非采购标书: {analysis.get('reason','')[:40]}")
    
    log(f"\n{'='*60}")
    log(f"  本次入库: {total} 条")
    log(f"{'='*60}")
    return total

if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    run(dry_run=dry)
