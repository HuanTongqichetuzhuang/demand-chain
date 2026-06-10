"""
静态文件服务器 + API 代理 — 服务 HTML 页面和 REST API。
"""
import json
import os
import uvicorn
from starlette.applications import Starlette
from starlette.responses import FileResponse, JSONResponse
from starlette.routing import Route

WEB_ROOT = "/app"

async def serve_file(request, filename):
    path = os.path.join(WEB_ROOT, filename)
    if os.path.exists(path):
        return FileResponse(path)
    return JSONResponse({"error": "not found"}, status_code=404)

async def index(request): return await serve_file(request, "index.html")
async def login_page(request): return await serve_file(request, "login.html")
async def demand_square(request): return await serve_file(request, "demand_square.html")
async def zones(request): return await serve_file(request, "zones.html")
async def forum(request): return await serve_file(request, "forum.html")
async def chat(request): return await serve_file(request, "chat.html")
async def timeline(request): return await serve_file(request, "timeline.html")
async def leaderboard(request): return await serve_file(request, "leaderboard.html")
async def global_search(request): return await serve_file(request, "global_search.html")
async def targeted(request): return await serve_file(request, "targeted_demand.html")
async def discovered(request): return await serve_file(request, "discovered_demands.html")
async def public_demand(request): return await serve_file(request, "public_demand.html")
async def batch_export(request): return await serve_file(request, "batch_export.html")
async def api_docs(request): return await serve_file(request, "api_docs.html")
async def tools_extra(request): return await serve_file(request, "tools_extra.html")
async def tutorial(request): return await serve_file(request, "docs/tutorial.html")

async def static_file(request):
    path = request.path_params.get("path", "")
    if ".." in path:
        return JSONResponse({"error": "forbidden"}, status_code=403)
    filepath = os.path.join(WEB_ROOT, path)
    if os.path.isfile(filepath):
        return FileResponse(filepath)
    return JSONResponse({"error": "not found"}, status_code=404)


# ============================================================
# Auth API
# ============================================================

async def api_register(request):
    """POST /api/register — 注册新人类用户"""
    import hashlib, secrets
    from src.shared.agent_identity import agent_registry, generate_ulid
    try:
        body = await request.json()
        email = body.get("email","").strip()
        name = body.get("name","").strip()
        password = body.get("password","")
        country = body.get("country","")
        email_notify = body.get("email_notify", True)
        
        if not email or not password or len(password) < 6:
            return JSONResponse({"error": "邮箱和密码(至少6位)必填"}, status_code=400)
        
        # Check if already registered
        if email in agent_registry._email_to_human:
            return JSONResponse({"error": "该邮箱已注册"}, status_code=409)
        
        human_id = generate_ulid()
        hashed = hashlib.sha256(password.encode()).hexdigest()
        
        agent_registry._email_to_human[email] = {
            "human_id": human_id,
            "password_hash": hashed,
            "name": name,
            "country": country,
            "email_notify": email_notify,
        }
        
        # Generate API key for agent use
        api_key = hashlib.sha256((human_id + secrets.token_urlsafe(16)).encode()).hexdigest()[:32]
        agent_registry._email_to_human[email]["api_key"] = api_key
        
        # Also store api_key -> human mapping
        agent_registry._api_key_to_human = getattr(agent_registry, "_api_key_to_human", {})
        agent_registry._api_key_to_human[api_key] = human_id
        
        return JSONResponse({
            "status": "ok",
            "human_id": human_id,
            "email": email,
            "name": name,
            "api_key": api_key,
        })
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

async def api_login(request):
    """POST /api/login — 人类登录"""
    import hashlib
    from src.shared.agent_identity import agent_registry
    try:
        body = await request.json()
        email = body.get("email","").strip()
        password = body.get("password","")
        
        entry = agent_registry._email_to_human.get(email)
        if not entry:
            return JSONResponse({"error": "邮箱未注册"}, status_code=401)
        
        hashed = hashlib.sha256(password.encode()).hexdigest()
        if hashed != entry.get("password_hash"):
            return JSONResponse({"error": "密码错误"}, status_code=401)
        
        return JSONResponse({
            "status": "ok",
            "human_id": entry["human_id"],
            "email": email,
            "name": entry.get("name",""),
            "api_key": entry.get("api_key",""),
        })
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

# ============================================================
# REST API — 论坛、需求等数据接口
# ============================================================

async def api_forum_topics(request):
    """GET /api/forum/topics — 论坛帖子列表"""
    from src.shared.database import async_session
    from src.shared.models import ForumTopic
    try:
        async with async_session() as session:
            from sqlalchemy import select
            result = await session.execute(
                select(ForumTopic).order_by(ForumTopic.created_at.desc()).limit(50)
            )
            topics = result.scalars().all()
            return JSONResponse([{
                "id": t.id,
                "title": t.title,
                "content": t.content[:200] if t.content else "",
                "category": t.category,
                "author_id": t.author_id,
                "vote_count": t.vote_count or 0,
                "reply_count": t.reply_count or 0,
                "created_at": t.created_at.isoformat() if t.created_at else "",
            } for t in topics])
    except Exception as e:
        return JSONResponse({"error": str(e), "topics": []}, status_code=500)

async def api_forum_categories(request):
    """GET /api/forum/categories — 论坛分类"""
    return JSONResponse([
        {"id": "tech", "name": "技术讨论", "icon": "tech"},
        {"id": "demand", "name": "需求对接", "icon": "demand"},
        {"id": "collab", "name": "合作招募", "icon": "collab"},
        {"id": "showcase", "name": "成果展示", "icon": "showcase"},
        {"id": "general", "name": "综合讨论", "icon": "general"},
    ])

async def api_forum_topic_detail(request):
    """GET /api/forum/topics/{topic_id}"""
    from src.shared.database import async_session
    from src.shared.models import ForumTopic
    topic_id = request.path_params.get("topic_id", "")
    try:
        async with async_session() as session:
            from sqlalchemy import select
            result = await session.execute(select(ForumTopic).where(ForumTopic.id == topic_id))
            t = result.scalar_one_or_none()
            if not t:
                return JSONResponse({"error": "not found"}, status_code=404)
            return JSONResponse({
                "id": t.id,
                "title": t.title,
                "content": t.content,
                "category": t.category,
                "author_id": t.author_id,
                "vote_count": t.vote_count or 0,
                "reply_count": t.reply_count or 0,
                "created_at": t.created_at.isoformat() if t.created_at else "",
            })
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

async def api_forum_vote(request):
    """POST /api/forum/topics/{topic_id}/vote"""
    from src.shared.database import async_session
    from src.shared.models import ForumTopic
    topic_id = request.path_params.get("topic_id", "")
    try:
        body = await request.json()
        direction = body.get("direction", "up")
        async with async_session() as session:
            from sqlalchemy import select
            result = await session.execute(select(ForumTopic).where(ForumTopic.id == topic_id))
            t = result.scalar_one_or_none()
            if t:
                if direction == "up":
                    t.vote_count = (t.vote_count or 0) + 1
                else:
                    t.vote_count = max(0, (t.vote_count or 0) - 1)
                await session.commit()
                return JSONResponse({"status": "ok", "vote_count": t.vote_count})
        return JSONResponse({"error": "not found"}, status_code=404)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

async def api_demand_list(request):
    """GET /api/demands — 需求列表"""
    from src.shared.database import async_session
    from src.shared.models import Demand
    try:
        async with async_session() as session:
            from sqlalchemy import select
            result = await session.execute(
                select(Demand).order_by(Demand.created_at.desc()).limit(50)
            )
            demands = result.scalars().all()
            return JSONResponse([{
                "id": d.id,
                "raw_text": d.raw_text[:200] if d.raw_text else "",
                "category": d.category,
                "status": d.status.value if d.status else "open",
                "created_at": d.created_at.isoformat() if d.created_at else "",
            } for d in demands])
    except Exception as e:
        return JSONResponse({"error": str(e), "demands": []}, status_code=500)

routes = [
    Route("/", index),
    Route("/login.html", login_page),
    Route("/index.html", index),
    Route("/demand_square.html", demand_square),
    Route("/zones.html", zones),
    Route("/forum.html", forum),
    Route("/chat.html", chat),
    Route("/timeline.html", timeline),
    Route("/leaderboard.html", leaderboard),
    Route("/global_search.html", global_search),
    Route("/targeted_demand.html", targeted),
    Route("/discovered_demands.html", discovered),
    Route("/public_demand.html", public_demand),
    Route("/batch_export.html", batch_export),
    Route("/api_docs.html", api_docs),
    Route("/tools_extra.html", tools_extra),
    Route("/docs/tutorial.html", tutorial),
    # API Routes
    Route("/api/register", api_register, methods=["POST"]),
    Route("/api/login", api_login, methods=["POST"]),
    Route("/api/forum/categories", api_forum_categories),
    Route("/api/forum/topics", api_forum_topics),
    Route("/api/forum/topics/{topic_id}", api_forum_topic_detail),
    Route("/api/forum/topics/{topic_id}/vote", api_forum_vote, methods=["POST"]),
    Route("/api/demands", api_demand_list),
    # Catch-all static
    Route("/{path:path}", static_file),
]

app = Starlette(routes=routes)

def run():
    uvicorn.run(app, host="0.0.0.0", port=80, log_level="info")

if __name__ == "__main__":
    run()
