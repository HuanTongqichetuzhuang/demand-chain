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

# ============================================================
# 安全工具函数
# ============================================================

import re

_EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')


def _validate_email(email: str) -> bool:
    """校验邮箱格式"""
    if not email or len(email) > 254:
        return False
    return bool(_EMAIL_RE.match(email))


def _sanitize_like(value: str) -> str:
    """转义 LIKE 模式中的特殊字符 (% 和 _)"""
    return value.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')


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
        if not _validate_email(email):
            return JSONResponse({"error": "无效的邮箱格式"}, status_code=400)
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
        if not _validate_email(email):
            return JSONResponse({"error": "无效的邮箱格式"}, status_code=400)
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
        if not _validate_email(email):
            return JSONResponse({"error": "无效的邮箱格式"}, status_code=400)
        avatar_data = body.get("avatar","")
        if len(avatar_data) > 512 * 1024:  # 512KB max
            return JSONResponse({"error": "头像文件过大，最大512KB"}, status_code=400)
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
        if not _validate_email(email):
            return JSONResponse({"error": "无效的邮箱格式"}, status_code=400)
        old_pwd = body.get("old_password","")
        new_pwd = body.get("new_password","")
        if len(new_pwd) < 6:
            return JSONResponse({"error": "新密码至少6位"}, status_code=400)
        if len(new_pwd) > 128:
            return JSONResponse({"error": "新密码过长"}, status_code=400)
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
    from sqlalchemy import select, func
    try:
        email = request.query_params.get("email", "")
        if not _validate_email(email):
            return JSONResponse({"demands":0,"topics":0,"replies":0})
        async with async_session() as session:
            from src.shared.models import User
            r = await session.execute(select(User).where(User.email == email))
            u = r.scalar_one_or_none()
            if not u:
                return JSONResponse({"demands":0,"topics":0,"replies":0})
            d_count = (await session.execute(select(func.count()).select_from(Demand).where(Demand.user_id == u.human_id))).scalar()
            # 使用参数化绑定替代字符串拼接
            safe_pattern = f'%{_sanitize_like(email)}%'
            t_count = (await session.execute(select(func.count()).select_from(ForumTopic).where(ForumTopic.agent_id.ilike(safe_pattern)))).scalar()
            r_count = (await session.execute(select(func.count()).select_from(ForumReply).where(ForumReply.agent_id.ilike(safe_pattern)))).scalar()
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
        if not _validate_email(email):
            return JSONResponse({"error": "邮箱格式不正确"}, status_code=400)
        if len(password) > 128:
            return JSONResponse({"error": "密码过长"}, status_code=400)
        if len(name) > 100:
            return JSONResponse({"error": "用户名过长"}, status_code=400)
        
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
        if not _validate_email(email):
            return JSONResponse({"error": "邮箱格式不正确"}, status_code=400)
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
    """GET /api/suppliers — 获取公开供应商资料（支持分页+搜索）"""
    from src.shared.database import async_session
    from src.shared.models import CapabilityProfile
    from sqlalchemy import select, func
    try:
        # 分页参数
        page = int(request.query_params.get('page', 1))
        per_page = int(request.query_params.get('per_page', 50))
        keyword = request.query_params.get('keyword', '').strip()
        page = max(1, page)
        per_page = max(1, min(200, per_page))
        offset = (page - 1) * per_page

        async with async_session() as session:
            query = select(CapabilityProfile)
            
            # 关键词搜索（转义 LIKE 特殊字符）
            if keyword:
                safe_kw = _sanitize_like(keyword)
                pattern = f'%{safe_kw}%'
                query = query.where(
                    CapabilityProfile.agent_card_json['name'].as_string().ilike(pattern) |
                    CapabilityProfile.agent_card_json['description'].as_string().ilike(pattern) |
                    CapabilityProfile.agent_card_json['industry'].as_string().ilike(pattern) |
                    CapabilityProfile.agent_card_json['discipline'].as_string().ilike(pattern)
                )
            
            # 总数
            count_result = await session.execute(select(func.count()).select_from(query.subquery()))
            total = count_result.scalar()

            # 分页数据
            result = await session.execute(
                query.order_by(CapabilityProfile.created_at.desc())
                .limit(per_page)
                .offset(offset)
            )
            profiles = result.scalars().all()

            items = [{
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
                'process': p.agent_card_json.get('process',[]),
                'contact': p.agent_card_json.get('contact',{}),
                'trl': p.agent_card_json.get('trl',0),
                'url': p.agent_card_json.get('url',''),
            } for p in profiles]

            return JSONResponse({
                'items': items,
                'total': total,
                'page': page,
                'per_page': per_page,
                'total_pages': (total + per_page - 1) // per_page if total > 0 else 0,
            })
    except Exception as e:
        return JSONResponse({'error':str(e)}, status_code=500)


async def api_auto_demand(request):
    """POST /api/auto-demand — 自动添加需求（爬虫用），带内容去重"""
    from src.shared.database import async_session
    from src.shared.models import Demand, DemandStatus
    from sqlalchemy import select
    from uuid import uuid4
    try:
        body = await request.json()
        raw_text = body.get("raw_text", "")
        category = body.get("category", "其他")
        email = body.get("email", "crawler")
        if not raw_text:
            return JSONResponse({"error": "empty"}, status_code=400)

        prefix = raw_text[:100]
        async with async_session() as session:
            # 去重：用 raw_text 前 100 字符做前缀匹配
            result = await session.execute(
                select(Demand.id).where(Demand.raw_text.startswith(prefix)).limit(1)
            )
            if result.scalar_one_or_none():
                return JSONResponse({"status": "dup", "message": "duplicate demand"})

            demand = Demand(
                id=str(uuid4()),
                user_id=email,
                raw_text=raw_text,
                category=category,
                status=DemandStatus.OPEN,
                visibility="PUBLIC",
            )
            session.add(demand)
            await session.commit()
            return JSONResponse({"status": "ok", "id": demand.id})
    except Exception as e:
        import logging, traceback
        logger = logging.getLogger(__name__)
        logger.error(f"api_auto_demand error: {e}\n{traceback.format_exc()}")
        return JSONResponse({"error": str(e)}, status_code=500)

async def api_auto_supplier(request):
    """POST /api/auto-supplier — 自动添加供应商（爬虫用），带名称去重"""
    from src.shared.database import async_session
    from src.shared.models import CapabilityProfile
    from sqlalchemy import select
    from uuid import uuid4
    try:
        body = await request.json()
        agent_card = body.get("agent_card", {})
        supplier_name = agent_card.get("name", "")
        if not supplier_name:
            return JSONResponse({"error": "empty name"}, status_code=400)

        async with async_session() as session:
            # 按名称去重
            result = await session.execute(
                select(CapabilityProfile.id).where(
                    CapabilityProfile.agent_card_json["name"].as_string() == supplier_name
                ).limit(1)
            )
            if result.scalar_one_or_none():
                return JSONResponse({"status": "dup", "message": "duplicate supplier"})

            profile = CapabilityProfile(
                id=str(uuid4()),
                user_id=body.get("email", "crawler"),
                profile_type=body.get("profile_type", "COMPANY"),
                country=body.get("country", ""),
                trust_score=body.get("trust_score", 0.5),
                is_claimed=False,
                verified=False,
                agent_card_json=agent_card,
            )
            session.add(profile)
            await session.commit()
            return JSONResponse({"status": "ok", "id": profile.id})
    except Exception as e:
        import logging, traceback
        logger = logging.getLogger(__name__)
        logger.error(f"api_auto_supplier error: {e}\n{traceback.format_exc()}")
        return JSONResponse({"error": str(e)}, status_code=500)

# ============================================================
# REST API — 论坛、需求等数据接口
# ============================================================

async def api_forum_topics(request):
    """GET /api/forum/topics — 论坛帖子列表，支持排序和分类"""
    from src.shared.database import async_session
    from src.shared.models import ForumTopic
    from sqlalchemy import select, func, desc
    try:
        sort = request.query_params.get("sort", "hot")
        # 只接受预定义的排序方式
        if sort not in ("hot", "new", "top"):
            sort = "hot"
        category = request.query_params.get("category", "")
        # category 用白名单校验（业务上分类 slug 不含特殊字符）
        if category and not re.match(r'^[a-zA-Z0-9_\-]{1,50}$', category):
            category = ""
        limit = max(1, min(500, int(request.query_params.get("limit", "200"))))
        offset = max(0, int(request.query_params.get("offset", "0")))

        async with async_session() as session:
            query = select(ForumTopic)
            if category:
                query = query.where(ForumTopic.category == category)
            if sort == "new":
                query = query.order_by(desc(ForumTopic.created_at))
            elif sort == "top":
                query = query.order_by(desc(ForumTopic.upvotes))
            else:  # hot: pinned first, then upvotes
                query = query.order_by(desc(ForumTopic.is_pinned), desc(ForumTopic.upvotes))
            query = query.offset(offset).limit(limit)
            result = await session.execute(query)
            topics = result.scalars().all()
            return JSONResponse([{
                "id": t.id,
                "title": t.title,
                "content": t.body[:200] if t.body else "",
                "category": t.category,
                "author_id": t.agent_id,
                "vote_count": t.upvotes or 0,
                "reply_count": len(t.replies) if t.replies else 0,
                "is_pinned": t.is_pinned,
                "created_at": t.created_at.isoformat() if t.created_at else "",
            } for t in topics])
    except Exception as e:
        return JSONResponse({"error": str(e), "topics": []}, status_code=500)

async def api_forum_categories(request):
    """GET /api/forum/categories — 论坛分类及帖子数统计"""
    from src.shared.database import async_session
    from src.shared.models import ForumTopic
    from sqlalchemy import select, func
    from src.forum.service import CATEGORIES
    try:
        async with async_session() as session:
            result = await session.execute(
                select(ForumTopic.category, func.count(ForumTopic.id))
                .group_by(ForumTopic.category)
            )
            db_counts = dict(result.all())
            # Merge standard categories with actual counts
            cats = []
            for key, label in CATEGORIES.items():
                cats.append({"id": key, "name": label, "count": db_counts.get(key, 0)})
            # Add any unlisted categories that exist in DB
            for cat, cnt in db_counts.items():
                if cat not in CATEGORIES:
                    cats.append({"id": cat, "name": cat, "count": cnt})
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

async def api_demand_list(request):
    """GET /api/demands — 需求列表，支持分页、语义搜索"""
    from src.shared.database import async_session
    from src.shared.models import Demand
    from src.shared.semantic_search import demand_search, TfidfSearch
    from sqlalchemy import select, func
    try:
        keyword = request.query_params.get("keyword", "").strip()
        category = request.query_params.get("category", "")
        sort = request.query_params.get("sort", "new")
        page = int(request.query_params.get("page", 1))
        per_page = int(request.query_params.get("per_page", 50))
        page = max(1, page)
        per_page = max(1, min(200, per_page))
        offset = (page - 1) * per_page

        async with async_session() as session:
            # Get total count
            count_result = await session.execute(select(func.count(Demand.id)))
            total = count_result.scalar()

            result = await session.execute(
                select(Demand).order_by(Demand.created_at.desc()).limit(2000)
            )
            all_demands = list(result.scalars().all())

        # Filter by category
        if category:
            all_demands = [d for d in all_demands if d.category == category]

        # Semantic search
        if keyword:
            search = TfidfSearch()
            for d in all_demands:
                text = (d.raw_text or "") + " " + (d.category or "")
                if d.search_text:
                    text += " " + d.search_text
                if d.structured_json:
                    s = d.structured_json
                    text += " " + (s.get("summary", "") or "")
                    text += " " + " ".join(s.get("tags", []))
                search.add(d.id, text)
            search.build_index()
            scored = search.search(keyword, top_k=len(all_demands))
            id_to_d = {d.id: d for d in all_demands}
            ranked = [id_to_d[did] for did, score in scored if did in id_to_d]
            seen = {d.id for d in ranked}
            for d in all_demands:
                if d.id not in seen and keyword.lower() in (d.raw_text or "").lower():
                    ranked.append(d)
            all_demands = ranked

        # Sort
        if sort == "old":
            all_demands.reverse()

        total = len(all_demands)
        total_pages = (total + per_page - 1) // per_page if total > 0 else 0
        page_items = all_demands[offset:offset + per_page]

        return JSONResponse({
            "items": [{
                "id": d.id,
                "raw_text": d.raw_text[:300] if d.raw_text else "",
                "category": d.category,
                "status": d.status.value if d.status else "open",
                "summary": (d.structured_json.get("summary", "") if d.structured_json else ""),
                "tags": (d.structured_json.get("tags", []) if d.structured_json else []),
                "created_at": d.created_at.isoformat() if d.created_at else "",
            } for d in page_items],
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": total_pages,
        })
    except Exception as e:
        return JSONResponse({"error": str(e), "demands": []}, status_code=500)

async def api_matches(request):
    """GET /api/matches — 匹配结果列表"""
    from src.shared.database import async_session
    from src.shared.models import Match, Demand, CapabilityProfile
    try:
        demand_id = request.query_params.get("demand_id", "").strip()
        # demand_id 为可选的 UUID 格式过滤，非 UUID 时忽略
        limit = int(request.query_params.get("limit", "100"))
        import uuid as _uuid
        valid_demand_id = demand_id if re.match(r'^[a-fA-F0-9\-]{32,36}$', demand_id) else ""

        async with async_session() as session:
            from sqlalchemy import select
            query = select(Match).order_by(Match.score.desc()).limit(limit)
            if valid_demand_id:
                query = query.where(Match.demand_id == valid_demand_id)
            result = await session.execute(query)
            matches = list(result.scalars().all())

        # Collect parent demand/profile IDs
        demand_ids = {m.demand_id for m in matches}
        profile_ids = {m.profile_id for m in matches}

        # Fetch demands and profiles in bulk
        demand_map = {}
        profile_map = {}
        async with async_session() as session:
            if demand_ids:
                r = await session.execute(select(Demand).where(Demand.id.in_(demand_ids)))
                for d in r.scalars(): demand_map[d.id] = d
            if profile_ids:
                r = await session.execute(select(CapabilityProfile).where(CapabilityProfile.id.in_(profile_ids)))
                for p in r.scalars(): profile_map[p.id] = p

        return JSONResponse([{
            "id": m.id,
            "demand_id": m.demand_id,
            "profile_id": m.profile_id,
            "score": m.score,
            "status": m.status.value if m.status else "pending",
            "demand_title": (demand_map.get(m.demand_id).raw_text[:80] if m.demand_id in demand_map else ""),
            "demand_category": (demand_map.get(m.demand_id).category if m.demand_id in demand_map else ""),
            "supplier_name": (profile_map.get(m.profile_id).agent_card_json.get("name", "") if m.profile_id in profile_map else ""),
            "supplier_category": (profile_map.get(m.profile_id).agent_card_json.get("category", "") if m.profile_id in profile_map else ""),
            "created_at": m.created_at.isoformat() if m.created_at else "",
        } for m in matches])
    except Exception as e:
        return JSONResponse({"error": str(e), "matches": []}, status_code=500)

async def api_home_stats(request):
    """GET /api/home/stats — 首页实时统计"""
    from src.shared.database import async_session
    from src.shared.models import Demand, CapabilityProfile, ForumTopic
    try:
        async with async_session() as session:
            from sqlalchemy import select, desc
            r = await session.execute(select(Demand).order_by(desc(Demand.created_at)).limit(6))
            demands = list(r.scalars().all())
            r = await session.execute(select(CapabilityProfile).order_by(desc(CapabilityProfile.trust_score)).limit(5))
            suppliers = list(r.scalars().all())
            r = await session.execute(select(ForumTopic).order_by(desc(ForumTopic.upvotes)).limit(5))
            topics = list(r.scalars().all())

        return JSONResponse({
            "latest_demands": [{
                "id": d.id,
                "title": (d.structured_json.get("summary","") if d.structured_json else "") or (d.raw_text or "")[:60],
                "category": d.category,
                "tags": (d.structured_json.get("tags", []) if d.structured_json else []),
                "created_at": d.created_at.isoformat() if d.created_at else "",
            } for d in demands],
            "top_suppliers": [{
                "id": p.id,
                "name": p.agent_card_json.get("name",""),
                "category": p.agent_card_json.get("category",""),
                "trust_score": p.trust_score,
            } for p in suppliers],
            "hot_topics": [{
                "id": t.id,
                "title": t.title,
                "upvotes": t.upvotes,
                "reply_count": len(t.replies) if t.replies else 0,
            } for t in topics],
        })
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

async def api_match_email(request):
    """GET /api/match/{match_id}/email — 生成邮件模板，用户复制后自己发"""
    from src.shared.database import async_session
    from src.shared.models import Match, Demand, CapabilityProfile
    from src.shared.email_templates import email_generator
    try:
        match_id = request.path_params.get("match_id", "")
        async with async_session() as session:
            from sqlalchemy import select
            r = await session.execute(select(Match).where(Match.id == match_id))
            m = r.scalar_one_or_none()
            if not m:
                return JSONResponse({"error": "匹配不存在"}, status_code=404)

            r = await session.execute(select(Demand).where(Demand.id == m.demand_id))
            d = r.scalar_one_or_none()
            r = await session.execute(select(CapabilityProfile).where(CapabilityProfile.id == m.profile_id))
            p = r.scalar_one_or_none()

        demand_title = (d.structured_json.get("summary","") if d and d.structured_json else "") or (d.raw_text[:80] if d else "需求")
        demand_body = d.raw_text[:500] if d else ""
        supplier_name = p.agent_card_json.get("name","") if p else "供应商"
        supplier_desc = p.agent_card_json.get("description","")[:200] if p else ""
        reason = f"我们的AI匹配引擎发现贵方与需求\"{demand_title}\"的匹配度为{m.score:.0%}。贵方在{supplier_desc or supplier_name}方面的能力与此需求高度相关。"

        template = email_generator.generate(
            demand_title=demand_title,
            demand_body=demand_body,
            match_reason=reason,
            company_name=supplier_name,
            demand_name="需求方",
        )
        template["match_id"] = match_id
        template["score"] = m.score
        template["supplier_name"] = supplier_name
        return JSONResponse(template)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

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
    Route("/api/auto-demand", api_auto_demand, methods=["POST"]),
    Route("/api/auto-supplier", api_auto_supplier, methods=["POST"]),
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
    Route("/api/matches", api_matches),
    Route("/api/matches/{match_id}/email", api_match_email),
    Route("/api/home/stats", api_home_stats),
    # Catch-all static
    Route("/{path:path}", static_file),
]

app = Starlette(routes=routes)

def run():
    uvicorn.run(app, host="0.0.0.0", port=80, log_level="info")

if __name__ == "__main__":
    run()
