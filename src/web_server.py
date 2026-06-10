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
# User Profile API
# ============================================================

async def api_user_profile_get(request):
    """GET /api/user/profile — 获取用户资料"""
    from src.shared.database import async_session
    from src.shared.models import User
    from sqlalchemy import select
    try:
        email = request.query_params.get("email", "")
        async with async_session() as session:
            result = await session.execute(select(User).where(User.email == email))
            u = result.scalar_one_or_none()
            if not u:
                return JSONResponse({"error": "not found"}, status_code=404)
            return JSONResponse({
                "email": u.email,
                "display_name": u.display_name,
                "country": u.country,
                "avatar": getattr(u, "avatar", None),
                "bio": getattr(u, "bio", None),
            })
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

async def api_user_profile_update(request):
    """PUT /api/user/profile — 更新用户资料"""
    from src.shared.database import async_session
    from src.shared.models import User
    from sqlalchemy import select
    try:
        body = await request.json()
        email = body.get("email","")
        async with async_session() as session:
            result = await session.execute(select(User).where(User.email == email))
            u = result.scalar_one_or_none()
            if not u:
                return JSONResponse({"error": "not found"}, status_code=404)
            u.display_name = body.get("display_name", u.display_name)
            u.country = body.get("country", u.country)
            if hasattr(u, "bio"):
                u.bio = body.get("bio", u.bio)
            await session.commit()
            return JSONResponse({"status": "ok"})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

async def api_user_avatar(request):
    """POST /api/user/avatar — 上传头像"""
    from src.shared.database import async_session
    from src.shared.models import User
    from sqlalchemy import select
    try:
        body = await request.json()
        email = body.get("email","")
        avatar_data = body.get("avatar","")
        async with async_session() as session:
            result = await session.execute(select(User).where(User.email == email))
            u = result.scalar_one_or_none()
            if not u:
                return JSONResponse({"error": "not found"}, status_code=404)
            u.avatar = avatar_data  # stored as base64 data URI
            await session.commit()
            return JSONResponse({"status": "ok"})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

async def api_user_password(request):
    """PUT /api/user/password — 修改密码"""
    import hashlib
    from src.shared.database import async_session
    from src.shared.models import User
    from sqlalchemy import select
    try:
        body = await request.json()
        email = body.get("email","")
        old_pwd = body.get("old_password","")
        new_pwd = body.get("new_password","")
        if len(new_pwd) < 6:
            return JSONResponse({"error": "新密码至少6位"}, status_code=400)
        async with async_session() as session:
            result = await session.execute(select(User).where(User.email == email))
            u = result.scalar_one_or_none()
            if not u:
                return JSONResponse({"error": "not found"}, status_code=404)
            old_hash = hashlib.sha256(old_pwd.encode()).hexdigest()
            if old_hash != u.password_hash:
                return JSONResponse({"error": "旧密码错误"}, status_code=401)
            u.password_hash = hashlib.sha256(new_pwd.encode()).hexdigest()
            await session.commit()
            return JSONResponse({"status": "ok"})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

async def api_user_stats(request):
    """GET /api/user/stats — 用户统计"""
    from src.shared.database import async_session
    from src.shared.models import Demand, ForumTopic, ForumReply
    from sqlalchemy import select
    try:
        email = request.query_params.get("email", "")
        async with async_session() as session:
            # Count demands by this user
            from src.shared.models import User
            r = await session.execute(select(User).where(User.email == email))
            u = r.scalar_one_or_none()
            if not u:
                return JSONResponse({"demands":0,"topics":0,"replies":0})
            d_count = (await session.execute(select(func.count()).select_from(Demand).where(Demand.user_id == u.human_id))).scalar()
            t_count = (await session.execute(select(func.count()).select_from(ForumTopic).where(ForumTopic.agent_id.ilike('%'+email+'%')))).scalar()
            r_count = (await session.execute(select(func.count()).select_from(ForumReply).where(ForumReply.agent_id.ilike('%'+email+'%')))).scalar()
            return JSONResponse({"demands": d_count or 0, "topics": t_count or 0, "replies": r_count or 0})
    except Exception as e:
        return JSONResponse({"demands":0,"topics":0,"replies":0,"error":str(e)})

# ============================================================
# Auth API
# ============================================================

async def api_register(request):
    """POST /api/register — 注册新人类用户（数据库持久化）"""
    import hashlib, secrets
    from src.shared.database import async_session
    from src.shared.models import User
    from sqlalchemy import select
    try:
        body = await request.json()
        email = body.get("email","").strip()
        name = body.get("name","").strip()
        password = body.get("password","")
        country = body.get("country","")
        email_notify = body.get("email_notify", True)
        
        if not email or not password or len(password) < 6:
            return JSONResponse({"error": "邮箱和密码(至少6位)必填"}, status_code=400)
        
        async with async_session() as session:
            # Check if already registered
            existing = await session.execute(select(User).where(User.email == email))
            if existing.scalar_one_or_none():
                return JSONResponse({"error": "该邮箱已注册"}, status_code=409)
            
            human_id = secrets.token_hex(16)  # 32 chars
            hashed = hashlib.sha256(password.encode()).hexdigest()
            api_key = hashlib.sha256((human_id + secrets.token_urlsafe(16)).encode()).hexdigest()[:32]
            
            user = User(
                human_id=human_id,
                email=email,
                display_name=name,
                password_hash=hashed,
                country=country,
                api_key=api_key,
                email_notify=email_notify,
            )
            session.add(user)
            await session.commit()
            
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
    """POST /api/login — 人类登录（数据库验证）"""
    import hashlib
    from src.shared.database import async_session
    from src.shared.models import User
    from sqlalchemy import select
    try:
        body = await request.json()
        email = body.get("email","").strip()
        password = body.get("password","")
        
        async with async_session() as session:
            result = await session.execute(select(User).where(User.email == email))
            user = result.scalar_one_or_none()
            
            if not user:
                return JSONResponse({"error": "邮箱未注册"}, status_code=401)
            
            hashed = hashlib.sha256(password.encode()).hexdigest()
            if hashed != user.password_hash:
                return JSONResponse({"error": "密码错误"}, status_code=401)
            
            return JSONResponse({
                "status": "ok",
                "human_id": user.human_id,
                "email": user.email,
                "name": user.display_name,
                "api_key": user.api_key or "",
            })
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


async def api_forum_create(request):
    """POST /api/forum/topics/create — 创建帖子"""
    from src.shared.database import async_session
    from src.shared.models import ForumTopic
    from uuid import uuid4
    try:
        body = await request.json()
        title = body.get("title", "").strip()
        content_text = body.get("body", "").strip()
        category = body.get("category", "general").strip()
        author_id = body.get("author_id", "web_user")
        
        if not title or len(title) < 2:
            return JSONResponse({"error": "标题太短"}, status_code=400)
        
        async with async_session() as session:
            topic = ForumTopic(
                id=str(uuid4()),
                title=title,
                body=content_text,
                category=category,
                agent_id=author_id,
                upvotes=0,
            )
            session.add(topic)
            await session.commit()
            return JSONResponse({"status": "ok", "topic_id": topic.id})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

async def api_forum_reply_post(request):
    """POST /api/forum/topics/{topic_id}/reply — 回复帖子"""
    from src.shared.database import async_session
    from src.shared.models import ForumTopic, ForumReply
    from uuid import uuid4
    topic_id = request.path_params.get("topic_id", "")
    try:
        body = await request.json()
        content_text = body.get("body", "").strip()
        author_id = body.get("author_id", "web_user")
        
        if not content_text:
            return JSONResponse({"error": "内容为空"}, status_code=400)
        
        async with async_session() as session:
            from sqlalchemy import select
            result = await session.execute(select(ForumTopic).where(ForumTopic.id == topic_id))
            topic = result.scalar_one_or_none()
            if not topic:
                return JSONResponse({"error": "帖子不存在"}, status_code=404)
            
            reply = ForumReply(
                id=str(uuid4()),
                topic_id=topic_id,
                body=content_text,
                agent_id=author_id,
            )
            session.add(reply)
            pass  # replies auto-tracked via relationship
            await session.commit()
            return JSONResponse({"status": "ok", "reply_id": reply.id})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

async def api_forum_vote_post(request):
    """POST /api/forum/topics/{topic_id}/vote — 投票"""
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
                    t.upvotes = (t.upvotes or 0) + 1
                else:
                    t.upvotes = max(0, (t.upvotes or 0) - 1)
                await session.commit()
                return JSONResponse({"status": "ok", "vote_count": t.upvotes})
        return JSONResponse({"error": "not found"}, status_code=404)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

async def api_forum_replies(request):
    """GET /api/forum/topics/{topic_id}/replies — 获取回复"""
    from src.shared.database import async_session
    from src.shared.models import ForumReply
    topic_id = request.path_params.get("topic_id", "")
    try:
        async with async_session() as session:
            from sqlalchemy import select
            result = await session.execute(
                select(ForumReply).where(ForumReply.topic_id == topic_id).order_by(ForumReply.created_at.asc()).limit(100)
            )
            replies = result.scalars().all()
            return JSONResponse([{
                "id": r.id,
                "content": r.body,
                "author_id": r.agent_id,
                "created_at": r.created_at.isoformat() if r.created_at else "",
            } for r in replies])
    except Exception as e:
        return JSONResponse({"error": str(e), "replies": []}, status_code=500)


async def api_suppliers(request):
    """GET /api/suppliers — 获取公开供应商资料"""
    from src.shared.database import async_session
    from src.shared.models import CapabilityProfile
    from sqlalchemy import select
    try:
        async with async_session() as session:
            result = await session.execute(select(CapabilityProfile).order_by(CapabilityProfile.created_at.desc()).limit(100))
            profiles = result.scalars().all()
            return JSONResponse([{
                'id': p.id,
                'user_id': p.user_id,
                'profile_type': p.profile_type,
                'country': p.country,
                'trust_score': p.trust_score,
                'is_claimed': p.is_claimed,
                'verified': p.verified,
                'name': p.agent_card_json.get('name',''),
                'description': p.agent_card_json.get('description',''),
                'skills': p.agent_card_json.get('skills',[]),
                'category': p.agent_card_json.get('category',''),
                'industry': p.agent_card_json.get('industry',''),
                'discipline': p.agent_card_json.get('discipline',''),
                'trl': p.agent_card_json.get('trl',0),
                'url': p.agent_card_json.get('url',''),
            } for p in profiles])
    except Exception as e:
        return JSONResponse({'error':str(e)}, status_code=500)

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
                select(ForumTopic).order_by(ForumTopic.created_at.desc()).limit(200)
            )
            topics = result.scalars().all()
            return JSONResponse([{
                "id": t.id,
                "title": t.title,
                "content": t.body[:200] if t.body else "",
                "category": t.category,
                "author_id": t.agent_id,
                "vote_count": t.upvotes or 0,
                "reply_count": len(t.replies) if t.replies else 0,
                "created_at": t.created_at.isoformat() if t.created_at else "",
            } for t in topics])
    except Exception as e:
        return JSONResponse({"error": str(e), "topics": []}, status_code=500)

async def api_forum_categories(request):
    """GET /api/forum/categories — 按行业/学科分类"""
    from src.shared.database import async_session
    from src.shared.models import Demand, DemandStatus
    from sqlalchemy import select, func, distinct
    try:
        async with async_session() as session:
            result = await session.execute(
                select(Demand.category, func.count()).where(Demand.status == DemandStatus.OPEN).group_by(Demand.category).order_by(func.count().desc()).limit(40)
            )
            rows = result.all()
            cats = [{"id": (r[0] or "其他"), "name": (r[0] or "其他"), "count": r[1]} for r in rows]
            return JSONResponse(cats)
    except Exception as e:
        return JSONResponse([{"id": "general", "name": "综合讨论", "count": 0}])

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
                "content": t.body,
                "category": t.category,
                "author_id": t.agent_id,
                "vote_count": t.upvotes or 0,
                "reply_count": len(t.replies) if t.replies else 0,
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
                    t.upvotes = (t.upvotes or 0) + 1
                else:
                    t.upvotes = max(0, (t.upvotes or 0) - 1)
                await session.commit()
                return JSONResponse({"status": "ok", "vote_count": t.upvotes})
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
                select(Demand).order_by(Demand.created_at.desc()).limit(200)
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
    Route("/api/user/profile", api_user_profile_get),
    Route("/api/user/profile", api_user_profile_update, methods=["PUT"]),
    Route("/api/user/avatar", api_user_avatar, methods=["POST"]),
    Route("/api/user/password", api_user_password, methods=["PUT"]),
    Route("/api/user/stats", api_user_stats),
    Route("/api/suppliers", api_suppliers),
    Route("/api/register", api_register, methods=["POST"]),
    Route("/api/login", api_login, methods=["POST"]),
    Route("/api/forum/categories", api_forum_categories),
    Route("/api/forum/topics/create", api_forum_create, methods=["POST"]),
    Route("/api/forum/topics", api_forum_topics),
    Route("/api/forum/topics/{topic_id}", api_forum_topic_detail),
    Route("/api/forum/topics/{topic_id}/vote", api_forum_vote_post, methods=["POST"]),
    Route("/api/forum/topics/{topic_id}/reply", api_forum_reply_post, methods=["POST"]),
    Route("/api/forum/topics/{topic_id}/replies", api_forum_replies),
    Route("/api/demands", api_demand_list),
    # Catch-all static
    Route("/{path:path}", static_file),
]

app = Starlette(routes=routes)

def run():
    uvicorn.run(app, host="0.0.0.0", port=80, log_level="info")

if __name__ == "__main__":
    run()
