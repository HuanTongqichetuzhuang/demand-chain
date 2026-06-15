"""GitHub Issues 需求发现爬虫"""
import urllib.request, json, time, asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

QUERIES = [
    "feature request state:open label:enhancement repo:pytorch/pytorch",
    "feature request state:open label:enhancement repo:kubernetes/kubernetes",
    "feature request state:open label:enhancement repo:rust-lang/rust",
    "feature request state:open label:enhancement repo:golang/go",
    "feature request state:open label:enhancement repo:microsoft/vscode",
    "feature request state:open label:enhancement repo:home-assistant/core",
    "feature request state:open label:enhancement repo:opencv/opencv",
    "feature request state:open label:enhancement repo:godotengine/godot",
]

def classify(text):
    tl = text.lower()
    rules = [
        ("人工智能", ["machine learning", "deep learning", "neural network", "nlp", "computer vision", "llm", "transformer", "gpt", "object detection"]),
        ("信息技术", ["api", "sdk", "cli", "rest api", "websocket", "docker", "kubernetes", "backend", "database", "sql", "cache", "monitoring"]),
        ("传感器技术", ["sensor", "iot", "embedded", "arduino", "raspberry pi", "camera", "lidar", "firmware"]),
        ("机器人与智能系统", ["robot", "automation", "autonomous", "drone", "ros", "control system"]),
        ("电子科学与技术", ["fpga", "asic", "verilog", "microcontroller", "rtos", "hardware"]),
        ("安全科学", ["security", "encryption", "authentication", "vulnerability"]),
        ("环境工程", ["climate", "renewable", "solar", "wind", "co2"]),
        ("生物医药", ["medical", "healthcare", "clinical", "diagnostic", "imaging", "genome"]),
    ]
    for cat, kws in rules:
        if any(kw in tl for kw in kws):
            return cat
    return "信息技术"


async def save_demand(raw_text):
    from src.shared.database import async_session
    from src.shared.models import Demand, DemandStatus
    from src.shared.classification import classify_text
    from uuid import uuid4
    from datetime import datetime, timezone
    from sqlalchemy import select, func

    cat, sub = classify_text(raw_text)

    async with async_session() as s:
        prefix = raw_text[:60].replace("'", "''")
        r = await s.execute(
            select(func.count(Demand.id)).where(Demand.raw_text.ilike(prefix[:40] + "%"))
        )
        cnt = r.scalar()
        if cnt and cnt > 0:
            return None

        demand = Demand(
            id=str(uuid4()),
            user_id="crawler",
            raw_text=raw_text[:500],
            category=cat,
            sub_category=sub,
            status="open",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        s.add(demand)
        await s.commit()
        return demand.id


async def main():
    print("="*50)
    print("GitHub Issues 需求发现爬虫")
    print("="*50)
    total_found = 0
    total_new = 0

    for i, query in enumerate(QUERIES):
        repo = query.split("repo:")[-1]
        url = f"https://api.github.com/search/issues?q={urllib.request.quote(query)}&sort=updated&per_page=5"
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "DemandChainBot/1.0",
                "Accept": "application/vnd.github.v3+json",
            })
            resp = urllib.request.urlopen(req, timeout=10)
            data = json.loads(resp.read())
            items = data.get("items", [])
            total_found += len(items)
            print(f"\n--- {repo} ({len(items)}) ---")
            for item in items:
                title = item.get("title","")[:80]
                body = (item.get("body","") or "")[:200]
                raw_text = f"{title}. {body}"[:400]
                did = await save_demand(raw_text)
                if did:
                    total_new += 1
                    print(f"  ✅ {classify(raw_text)}: {title[:50]}...")
                else:
                    print(f"  ⏭ {title[:40]}... (dup)")
            time.sleep(1.2)
        except Exception as e:
            print(f"  ❌ {str(e)[:60]}")

    print(f"\n{'='*50}")
    print(f"完成: 发现 {total_found}, 新增 {total_new}")
    print(f"{'='*50}")

if __name__ == "__main__":
    asyncio.run(main())
