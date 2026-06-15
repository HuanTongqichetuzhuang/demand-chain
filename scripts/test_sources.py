"""测试各种公开需求数据源的可用性"""
import urllib.request, json, sys

sources = []

# 1. GitHub API — feature request issues
sources.append(("GitHub Issues (feature requests)",
    "https://api.github.com/search/issues?q=feature+request+label:enhancement+state:open&sort=updated&per_page=5"))

# 2. Hacker News API — new stories
sources.append(("Hacker News (latest)",
    "https://hacker-news.firebaseio.com/v0/newstories.json?print=pretty"))

# 3. Hugging Face — community requests
sources.append(("Hugging Face (community requests)",
    "https://huggingface.co/api/discussions?limit=5"))

# 4. Kaggle — competitions
sources.append(("Kaggle (active competitions)",
    "https://www.kaggle.com/api/v1/competitions/list?sortBy=latest&page=1&pageSize=5"))

# 5. Reddit — r/AskEngineers, r/AskScience
sources.append(("Reddit (tech subreddits)",
    "https://www.reddit.com/r/AskEngineers/hot.json?limit=5"))

# 6. 知乎热榜
sources.append(("知乎热榜",
    "https://www.zhihu.com/api/v3/feed/topstory/hot-lists/total?limit=5"))

# 7. Product Hunt
sources.append(("Product Hunt (tech products)",
    "https://api.producthunt.com/v1/posts?sort_by=votes_count&per_page=5"))

print("="*60)
print("需求数据源可用性测试")
print("="*60)

for name, url in sources:
    print(f"\n--- {name} ---")
    print(f"  URL: {url[:70]}...")
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (compatible; DemandChainBot/1.0)",
            "Accept": "application/json",
        })
        resp = urllib.request.urlopen(req, timeout=8)
        data = json.loads(resp.read())
        # Basic result extraction
        if isinstance(data, dict):
            items = data.get("items") or data.get("data") or data.get("results") or []
            if isinstance(items, list):
                print(f"  ✅ OK — {len(items)} items")
                for item in items[:3]:
                    title = item.get("title","") or item.get("name","") or str(item)[:60]
                    print(f"     • {str(title)[:60]}")
            else:
                print(f"  ✅ OK — {len(data)} top-level keys")
                print(f"     Keys: {list(data.keys())[:5]}")
        elif isinstance(data, list):
            print(f"  ✅ OK — {len(data)} items")
            for item in data[:3]:
                print(f"     • {str(item)[:60]}")
        else:
            print(f"  ✅ OK — {str(data)[:60]}")
    except Exception as e:
        print(f"  ❌ Error: {str(e)[:80]}")
