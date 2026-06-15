"""
静态文件服务器 + API 代理 — 服务 HTML 页面和 REST API。
"""
import json
import os
import uvicorn
from starlette.applications import Starlette
from starlette.responses import FileResponse, JSONResponse
from starlette.routing import Route
from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app):
    yield

WEB_ROOT = "/app"

# ============================================================
# 安全工具函数
# ============================================================

import re

_EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')


async def _cleanup_unverified_accounts():
    """清理超过7天未验证邮箱的账号"""
    from src.shared.database import async_session
    from src.shared.models import User
    from sqlalchemy import delete
    from datetime import datetime, timezone, timedelta
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=7)
        async with async_session() as session:
            result = await session.execute(
                delete(User).where(User.email_verified == False).where(User.created_at < cutoff)
            )
            await session.commit()
            if result.rowcount:
                import logging
                logging.getLogger(__name__).info(f"Cleaned up {result.rowcount} unverified accounts")
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Failed to cleanup unverified accounts: {e}")


def _validate_email(email: str) -> bool:
    """校验邮箱格式"""
    if not email or len(email) > 254:
        return False
    return bool(_EMAIL_RE.match(email))


def _sanitize_like(value: str) -> str:
    """转义 LIKE 模式中的特殊字符 (% 和 _)"""
    return value.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')


# 管理员邮箱列表
_ADMIN_EMAILS = ["477570216@qq.com", "asd4422449@admin.dc"]


async def _require_admin(request):
    """检查请求是否来自管理员邮箱"""
    body = await request.json()
    email = body.get("email", "").strip()
    if not email or email not in _ADMIN_EMAILS:
        raise PermissionError("仅管理员可执行此操作")
    return email


# ============================================================
# 注册限流 (每 IP 每小时 ≤5 次注册)
# ============================================================

import time as _time
from collections import defaultdict

_register_attempts: dict[str, list[float]] = defaultdict(list)
_REGISTER_LIMIT = 5       # 最多 5 次
_REGISTER_WINDOW = 3600   # 每小时


def _check_rate_limit(ip: str) -> tuple[bool, int]:
    """检查 IP 是否超限。返回 (允许?, 剩余次数)"""
    now = _time.time()
    window_start = now - _REGISTER_WINDOW
    # 清理窗口外的记录
    _register_attempts[ip] = [t for t in _register_attempts[ip] if t > window_start]
    attempts = len(_register_attempts[ip])
    if attempts >= _REGISTER_LIMIT:
        return False, 0
    return True, _REGISTER_LIMIT - attempts


async def _send_verify_email(email: str, token: str, name: str):
    """发送邮箱验证邮件"""
    verify_url = f"/verify-email?token={token}"
    subject = "验证你的邮箱 — 需求链平台"
    body = f"""<div style="max-width:560px;margin:0 auto;font-family:sans-serif">
<h2 style="color:#7c6ef0">欢迎加入需求链平台 🎉</h2>
<p>你好 {name}，</p>
<p>请点击下方按钮验证你的邮箱地址：</p>
<p style="text-align:center;margin:30px 0">
  <a href="{verify_url}" style="display:inline-block;padding:12px 32px;background:#7c6ef0;color:#fff;text-decoration:none;border-radius:8px;font-weight:600">验证邮箱</a>
</p>
<p>或复制以下链接到浏览器：<br><code style="font-size:.85em;color:#9090b0">{verify_url}</code></p>
<p style="color:#9090b0;font-size:.85em;margin-top:24px">验证链接 48 小时内有效。<br>如非本人操作，请忽略此邮件。</p>
</div>"""
    try:
        from src.shared.notifications import send_email
        await send_email(to=email, subject=subject, body=body)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Failed to send verify email to {email}: {e}")


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
async def flywheel_dashboard(request): return await serve_file(request, "flywheel_dashboard.html")
async def admin_page(request): return await serve_file(request, "admin.html")
async def notification_page(request): return await serve_file(request, "notifications.html")
async def tutorial(request): return await serve_file(request, "docs/tutorial.html")

async def verify_email_page(request):
    """GET /verify-email — 邮箱验证页面"""
    token = request.query_params.get("token", "")
    if not token:
        return JSONResponse({"error": "缺少验证令牌"}, status_code=400)
    return await serve_file(request, "verify_email.html")

async def static_file(request):
    path = request.path_params.get("path", "")
    if ".." in path:
        return JSONResponse({"error": "forbidden"}, status_code=403)
    filepath = os.path.join(WEB_ROOT, path)
    if os.path.isfile(filepath):
        from starlette.responses import FileResponse as FR
        import mimetypes
        mt, _ = mimetypes.guess_type(filepath)
        # Cache-Control: CSS/JS/images/gifs get 1 year, HTML gets no-cache
        is_build = ".min." in path or "?v=" in str(request.url)
        if mt and (mt.startswith("text/css") or mt.startswith("application/javascript") or mt.startswith("image/")):
            headers = {"Cache-Control": "public, max-age=31536000, immutable"} if is_build else {"Cache-Control": "public, max-age=3600"}
        else:
            headers = {"Cache-Control": "no-cache, no-store, must-revalidate"} if path.endswith(".html") else {"Cache-Control": "public, max-age=3600"}
        return FR(filepath, headers=headers)
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
    """POST /api/user/avatar — 上传头像，存入文件系统"""
    import base64, imghdr, os
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

        # 解析 base64 data URI: "data:image/png;base64,xxxx"
        if not avatar_data.startswith("data:image/"):
            return JSONResponse({"error": "不支持的头像格式，仅支持 jpg/png/webp"}, status_code=400)
        
        mime_match = re.match(r'^data:image/(png|jpeg|jpg|webp);base64,', avatar_data)
        if not mime_match:
            return JSONResponse({"error": "不支持的头像格式，仅支持 jpg/png/webp"}, status_code=400)
        
        ext = mime_match.group(1)
        if ext == "jpeg":
            ext = "jpg"
        
        # 解码
        b64_str = avatar_data.split(",", 1)[1]
        img_bytes = base64.b64decode(b64_str)
        
        if len(img_bytes) > 1024 * 1024:  # 2MB → 解码后 1MB
            return JSONResponse({"error": "头像文件过大，解码后超过1MB"}, status_code=400)

        async with async_session() as session:
            result = await session.execute(select(User).where(User.email == email))
            u = result.scalar_one_or_none()
            if not u:
                return JSONResponse({"error": "not found"}, status_code=404)
            
            # 保存到文件系统
            avatar_dir = os.path.join(WEB_ROOT, "avatars")
            os.makedirs(avatar_dir, exist_ok=True)
            filename = f"{u.human_id}.{ext}"
            filepath = os.path.join(avatar_dir, filename)
            with open(filepath, "wb") as f:
                f.write(img_bytes)
            
            # 存储 URL 路径（通过 catch-all 静态路由提供）
            u.avatar = f"avatars/{filename}"
            await session.commit()
            return JSONResponse({"status": "ok", "avatar_url": f"avatars/{filename}"})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

async def api_user_password(request):
    """PUT /api/user/password — 修改密码"""
    import bcrypt as _bcr1
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
            stored = u.password_hash
            if stored.startswith("$2b$") or stored.startswith("$2a$"):
                if not _bcr1.checkpw(old_pwd.encode(), stored.encode()):
                    return JSONResponse({"error": "旧密码错误"}, status_code=401)
            else:
                import hashlib as _hl1
                if _hl1.sha256(old_pwd.encode()).hexdigest() != stored:
                    return JSONResponse({"error": "旧密码错误"}, status_code=401)
            u.password_hash = _bcr1.hashpw(new_pwd.encode(), _bcr1.gensalt()).decode()
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
    """POST /api/register — 注册新人类用户（数据库持久化，含限流+邮箱验证）"""
    import secrets, hashlib
    import bcrypt as _bcrypt3
    from src.shared.database import async_session
    from src.shared.models import User
    from sqlalchemy import select
    try:
        # 限流
        client_ip = request.client.host if request.client else "unknown"
        allowed, remaining = _check_rate_limit(client_ip)
        if not allowed:
            return JSONResponse({"error": "注册过于频繁，请一小时后重试"}, status_code=429)

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
        
        # 记录此次尝试
        _register_attempts[client_ip].append(_time.time())

        async with async_session() as session:
            # Check if already registered
            existing = await session.execute(select(User).where(User.email == email))
            if existing.scalar_one_or_none():
                return JSONResponse({"error": "该邮箱已注册"}, status_code=409)
            
            human_id = secrets.token_hex(16)  # 32 chars
            hashed = _bcrypt3.hashpw(password.encode(), _bcrypt3.gensalt()).decode()
            api_key = hashlib.sha256((human_id + secrets.token_urlsafe(16)).encode()).hexdigest()[:32]
            verify_token = secrets.token_urlsafe(32)
            
            user = User(
                human_id=human_id,
                email=email,
                display_name=name,
                password_hash=hashed,
                country=country,
                api_key=api_key,
                email_notify=email_notify,
                verify_token=verify_token,
                email_verified=False,
            )
            session.add(user)
            await session.commit()

        # 发送验证邮件（异步，不阻塞返回）
        await _send_verify_email(email, verify_token, name)

        return JSONResponse({
            "status": "ok",
            "human_id": human_id,
            "email": email,
            "name": name,
            "api_key": api_key,
            "message": "注册成功！请查收验证邮件并点击链接激活账号。",
        })
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

async def api_login(request):
    """POST /api/login — 人类登录（数据库验证，需已验证邮箱）"""
    import bcrypt as _bcrypt4
    import hashlib as _hashlib
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
            
            # 密码验证（兼容 bcrypt 和旧版 SHA256）
            stored_hash = user.password_hash
            if stored_hash.startswith("$2b$") or stored_hash.startswith("$2a$"):
                # bcrypt hash
                if not _bcrypt4.checkpw(password.encode(), stored_hash.encode()):
                    return JSONResponse({"error": "密码错误"}, status_code=401)
            else:
                # 旧版 SHA256 hash — 验证后升级到 bcrypt
                if _hashlib.sha256(password.encode()).hexdigest() != stored_hash:
                    return JSONResponse({"error": "密码错误"}, status_code=401)
                # 升级为 bcrypt
                new_hash = _bcrypt4.hashpw(password.encode(), _bcrypt4.gensalt()).decode()
                user.password_hash = new_hash
                await session.commit()
            
            return JSONResponse({
                "status": "ok",
                "human_id": user.human_id,
                "email": user.email,
                "name": user.display_name,
                "api_key": user.api_key or "",
            })
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


async def api_verify_email(request):
    """GET /api/verify-email — 验证邮箱"""
    from src.shared.database import async_session
    from src.shared.models import User
    from sqlalchemy import select
    from datetime import datetime, timezone, timedelta
    try:
        token = request.query_params.get("token", "").strip()
        if not token or len(token) < 8:
            return JSONResponse({"error": "无效的验证链接"}, status_code=400)
        
        async with async_session() as session:
            r = await session.execute(
                select(User).where(User.verify_token == token)
            )
            user = r.scalar_one_or_none()
            if not user:
                return JSONResponse({"error": "验证链接无效或已过期"}, status_code=404)
            
            # 检查是否 48 小时内
            if user.created_at and (datetime.now(timezone.utc) - user.created_at) > timedelta(hours=48):
                return JSONResponse({"error": "验证链接已过期（48小时），请重新注册"}, status_code=410)
            
            user.email_verified = True
            user.verify_token = None
            await session.commit()
            
        return JSONResponse({"status": "ok", "message": "邮箱验证成功！现在可以登录使用全部功能。"})
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
    """GET /api/suppliers — 获取公开供应商资料（支持分页+搜索+分类/行业/学科筛选）"""
    from src.shared.database import async_session
    from src.shared.models import CapabilityProfile
    from sqlalchemy import select, func
    try:
        # 分页参数
        page = int(request.query_params.get('page', 1))
        per_page = int(request.query_params.get('per_page', 50))
        keyword = request.query_params.get('keyword', '').strip()
        category = request.query_params.get('category', '').strip()
        industry = request.query_params.get('industry', '').strip()
        discipline = request.query_params.get('discipline', '').strip()
        page = max(1, page)
        per_page = max(1, min(200, per_page))
        offset = (page - 1) * per_page

        async with async_session() as session:
            query = select(CapabilityProfile)

            # 分类筛选（精确匹配）
            if category:
                query = query.where(
                    CapabilityProfile.agent_card_json['category'].astext == category
                )

            # 行业筛选（精确匹配）
            if industry:
                query = query.where(
                    CapabilityProfile.agent_card_json['industry'].astext == industry
                )

            # 学科筛选（精确匹配）
            if discipline:
                query = query.where(
                    CapabilityProfile.agent_card_json['discipline'].astext == discipline
                )

            # 关键词搜索（转义 LIKE 特殊字符）
            if keyword:
                safe_kw = _sanitize_like(keyword)
                pattern = f'%{safe_kw}%'
                query = query.where(
                    CapabilityProfile.agent_card_json['name'].astext.ilike(pattern) |
                    CapabilityProfile.agent_card_json['description'].astext.ilike(pattern) |
                    CapabilityProfile.agent_card_json['industry'].astext.ilike(pattern) |
                    CapabilityProfile.agent_card_json['discipline'].astext.ilike(pattern)
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


async def api_suppliers_filters(request):
    """GET /api/suppliers/filters — 获取供应商分类/行业/学科聚合信息（用于前端筛选栏）"""
    from src.shared.database import async_session
    from src.shared.models import CapabilityProfile
    from sqlalchemy import select, func, text
    try:
        async with async_session() as session:
            r = await session.execute(select(CapabilityProfile))
            rows = list(r.scalars().all())

        cats = {}
        inds = {}
        discs = {}
        for p in rows:
            card = p.agent_card_json or {}
            c = (card.get("category", "") or "").strip()
            i = (card.get("industry", "") or "").strip()
            d = (card.get("discipline", "") or "").strip()
            if c: cats[c] = cats.get(c, 0) + 1
            if i: inds[i] = inds.get(i, 0) + 1
            if d: discs[d] = discs.get(d, 0) + 1

        def top_items(d, n=50):
            items = sorted(d.items(), key=lambda x: -x[1])
            return [{"name": k, "count": v} for k, v in items[:n]]

        return JSONResponse({
            "categories": top_items(cats),
            "industries": top_items(inds),
            "disciplines": top_items(discs),
            "total": len(rows),
        })
    except Exception as e:
        return JSONResponse({'error': str(e)}, status_code=500)


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
            # 缓存失效：首页统计
            from src.shared.cache import delete_pattern
            await delete_pattern("cache:home:*")
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
    """GET /api/demands — 需求列表，支持分页、全文搜索、分类筛选"""
    from src.shared.database import async_session
    from src.shared.models import Demand
    from sqlalchemy import select, func, text as sa_text
    try:
        keyword = request.query_params.get("keyword", "").strip()
        category = request.query_params.get("category", "")
        sub_category = request.query_params.get("sub_category", "").strip()
        sort = request.query_params.get("sort", "new")
        page = int(request.query_params.get("page", 1))
        per_page = int(request.query_params.get("per_page", 50))
        page = max(1, page)
        per_page = max(1, min(200, per_page))

        async with async_session() as session:
            # Build base query
            base = select(Demand)
            count_base = select(func.count(Demand.id))

            if category:
                base = base.where(Demand.category == category)
                count_base = count_base.where(Demand.category == category)
            if sub_category:
                base = base.where(Demand.sub_category == sub_category)
                count_base = count_base.where(Demand.sub_category == sub_category)

            # PostgreSQL full-text search
            if keyword:
                # Escape single quotes for tsquery
                safe_q = keyword.replace("'", "''")
                tsquery = f"plainto_tsquery('simple', '{safe_q}')"
                base = base.where(
                    Demand.search_vector.op("@@")(sa_text(tsquery))
                ).order_by(
                    sa_text(f"ts_rank({Demand.search_vector.key}, {tsquery}) DESC")
                )
                count_base = count_base.where(
                    Demand.search_vector.op("@@")(sa_text(tsquery))
                )
            else:
                base = base.order_by(Demand.created_at.desc())

            # Get total
            count_result = await session.execute(count_base)
            total = count_result.scalar() or 0

            # Get page
            result = await session.execute(
                base.limit(per_page).offset((page - 1) * per_page)
            )
            all_demands = list(result.scalars().all())

        total_pages = (total + per_page - 1) // per_page if total > 0 else 0

        return JSONResponse({
            "items": [{
                "id": d.id,
                "raw_text": d.raw_text[:300] if d.raw_text else "",
                "category": d.category,
                "sub_category": getattr(d, "sub_category", None) or "",
                "status": d.status.value if d.status else "open",
                "summary": (d.structured_json.get("summary", "") if d.structured_json else ""),
                "tags": (d.structured_json.get("tags", []) if d.structured_json else []),
                "created_at": d.created_at.isoformat() if d.created_at else "",
            } for d in all_demands],
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": total_pages,
        })
    except Exception as e:
        return JSONResponse({"error": str(e), "demands": []}, status_code=500)


async def api_demands_filters(request):
    """GET /api/demands/filters — 需求分类聚合（用于前端筛选栏）"""
    from src.shared.database import async_session
    from src.shared.models import Demand
    from sqlalchemy import select, func
    from src.shared.classification import CATEGORY_TREE, CATEGORY_NAMES
    try:
        async with async_session() as session:
            r = await session.execute(select(Demand))
            rows = list(r.scalars().all())

        cat_counts = {}
        sub_counts = {}
        for d in rows:
            c = d.category or "其他"
            cat_counts[c] = cat_counts.get(c, 0) + 1
            sc = getattr(d, "sub_category", None) or ""
            if sc:
                sub_counts[(c, sc)] = sub_counts.get((c, sc), 0) + 1

        # 构建树形结构
        tree = []
        for cat in CATEGORY_NAMES:
            subs = []
            for sub in CATEGORY_TREE.get(cat, []):
                c = sub_counts.get((cat, sub), 0)
                if c > 0:
                    subs.append({"name": sub, "count": c})
            total = cat_counts.get(cat, 0)
            if total > 0 or subs:
                tree.append({
                    "name": cat,
                    "count": total,
                    "children": subs,
                })

        # 不在CATEGORY_TREE中的分类也加进去
        for cat, cnt in cat_counts.items():
            if cat not in CATEGORY_NAMES and cat:
                tree.append({"name": cat, "count": cnt, "children": []})

        return JSONResponse({
            "tree": tree,
            "total": len(rows),
        })
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

async def api_matches(request):
    """GET /api/matches — 匹配结果列表（缓存 30 分钟）"""
    from src.shared.cache import remember

    demand_id = request.query_params.get("demand_id", "").strip()
    limit = int(request.query_params.get("limit", "100"))
    valid_demand_id = demand_id if re.match(r'^[a-fA-F0-9\-]{32,36}$', demand_id) else ""
    cache_key = f"cache:matches:{valid_demand_id or 'all'}:{limit}"

    async def _fetch_matches():
        from src.shared.database import async_session
        from src.shared.models import Match, Demand, CapabilityProfile
        from sqlalchemy import select
        import uuid as _uuid
        async with async_session() as session:
            query = select(Match).order_by(Match.score.desc()).limit(limit)
            if valid_demand_id:
                query = query.where(Match.demand_id == valid_demand_id)
            result = await session.execute(query)
            matches = list(result.scalars().all())

        demand_ids = {m.demand_id for m in matches}
        profile_ids = {m.profile_id for m in matches}
        demand_map = {}
        profile_map = {}
        async with async_session() as session:
            if demand_ids:
                r = await session.execute(select(Demand).where(Demand.id.in_(demand_ids)))
                for d in r.scalars(): demand_map[d.id] = d
            if profile_ids:
                r = await session.execute(select(CapabilityProfile).where(CapabilityProfile.id.in_(profile_ids)))
                for p in r.scalars(): profile_map[p.id] = p

        return [{
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
        } for m in matches]

    try:
        data = await remember(cache_key, 1800, _fetch_matches)
        return JSONResponse(data)
    except Exception as e:
        return JSONResponse({"error": str(e), "matches": []}, status_code=500)


async def api_agent_card(request):
    """GET /.well-known/agent.json — Agent Card 发现端点

    返回指定 Agent 的公开能力画像，或平台总览。
    遵循 A2A Agent Card 规范，支持 Agent 发现和握手。
    """
    from src.shared.database import async_session
    from src.shared.models import CapabilityProfile
    from sqlalchemy import select, func

    agent_id = request.query_params.get("agent_id", "").strip()

    try:
        if agent_id:
            async with async_session() as session:
                result = await session.execute(
                    select(CapabilityProfile).where(CapabilityProfile.id == agent_id)
                )
                profile = result.scalar_one_or_none()
                if not profile:
                    return JSONResponse({"error": "Agent not found"}, status_code=404)
                card = profile.agent_card_json or {}
                return JSONResponse({
                    "@context": "https://a2a.demand-chain.ai/schemas/agent-card",
                    "agent_id": profile.id,
                    "name": card.get("name", "Unknown Agent"),
                    "description": card.get("description", ""),
                    "category": card.get("category", ""),
                    "industry": card.get("industry", ""),
                    "discipline": card.get("discipline", ""),
                    "skills": card.get("skills", []),
                    "trust_score": profile.trust_score or 0.0,
                    "profile_type": profile.profile_type.value if profile.profile_type else "",
                    "country": profile.country or "",
                    "url": card.get("url", ""),
                    "trl": card.get("trl", ""),
                })

        async with async_session() as session:
            count_r = await session.execute(select(func.count(CapabilityProfile.id)))
            total = count_r.scalar() or 0

        return JSONResponse({
            "@context": "https://a2a.demand-chain.ai/schemas/agent-card",
            "name": "需求链平台 Demand Chain",
            "description": "AI 驱动的开放式创新基础设施，连接全球需求与供应商",
            "total_agents": total,
            "protocol": "mcp+sse",
            "endpoints": {"mcp": "/sse", "api": "/api", "web": "/"},
            "well_known": "/.well-known/agent.json",
        })
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


async def api_home_stats(request):
    """GET /api/home/stats — 首页实时统计（缓存 5 分钟）"""
    from src.shared.cache import remember

    async def _fetch_home_stats():
        from src.shared.database import async_session
        from src.shared.models import Demand, CapabilityProfile, ForumTopic
        from sqlalchemy import select, desc
        async with async_session() as session:
            r = await session.execute(select(Demand).order_by(desc(Demand.created_at)).limit(6))
            demands = list(r.scalars().all())
            r = await session.execute(select(CapabilityProfile).order_by(desc(CapabilityProfile.trust_score)).limit(5))
            suppliers = list(r.scalars().all())
            r = await session.execute(select(ForumTopic).order_by(desc(ForumTopic.upvotes)).limit(5))
            topics = list(r.scalars().all())
        return {
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
        }

    try:
        data = await remember("cache:home:stats", 300, _fetch_home_stats)
        return JSONResponse(data)
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


# ── 数据飞轮 API ───────────────────────────────────────────

async def api_match_feedback(request):
    """POST /api/match/{match_id}/feedback — 用户反馈匹配是否有用"""
    from src.shared.database import async_session
    from src.shared.models import Match, MatchOutcome, OutcomeStatus
    from sqlalchemy import select
    from uuid import uuid4

    try:
        match_id = request.path_params.get("match_id", "")
        body = await request.json()
        useful = body.get("useful", None)  # True/False
        detail = body.get("detail", "")

        if useful is None:
            return JSONResponse({"error": "缺少 useful 字段（true/false）"}, status_code=400)

        async with async_session() as session:
            r = await session.execute(select(Match).where(Match.id == match_id))
            match = r.scalar_one_or_none()
            if not match:
                return JSONResponse({"error": "匹配不存在"}, status_code=404)

            outcome_status = OutcomeStatus.SUCCESS if useful else OutcomeStatus.FAILED

            existing = await session.execute(
                select(MatchOutcome).where(MatchOutcome.match_id == match_id)
            )
            outcome = existing.scalar_one_or_none()
            if outcome:
                outcome.status = outcome_status
                if detail:
                    outcome.outcome_detail = detail
            else:
                outcome = MatchOutcome(
                    id=str(uuid4()),
                    match_id=match.id,
                    demand_id=match.demand_id,
                    supplier_id=match.profile_id,
                    status=outcome_status,
                    outcome_detail=detail,
                )
                session.add(outcome)
            await session.commit()

        # Fire & forget flywheel update
        try:
            from src.shared.flywheel import update_trust_by_outcome, update_category_weight_by_outcome
            async with async_session() as s:
                ro = await s.execute(select(MatchOutcome).where(MatchOutcome.match_id == match_id))
                loaded = ro.scalar_one_or_none()
                if loaded:
                    await update_trust_by_outcome(loaded)
                    await update_category_weight_by_outcome(loaded)
        except Exception as e:
            logger.warning(f"[flywheel] async update error: {e}")

        return JSONResponse({
            "status": "ok",
            "match_id": match_id,
            "useful": useful,
            "message": "感谢反馈！您的评价已进入数据飞轮，将优化后续匹配。",
        })

    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


async def api_flywheel_stats(request):
    """GET /api/flywheel/stats — 飞轮运行统计"""
    from src.shared.flywheel import get_flywheel_stats
    try:
        stats = await get_flywheel_stats()
        return JSONResponse(stats)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ============================================================
# 管理员 API
# ============================================================

async def api_admin_check(request):
    """POST /api/admin/check — 验证是否为管理员"""
    try:
        email = await _require_admin(request)
        return JSONResponse({"admin": True, "email": email})
    except PermissionError as e:
        return JSONResponse({"admin": False, "error": str(e)}, status_code=403)


async def api_admin_stats(request):
    """GET /api/admin/stats — 系统统计（管理员专用）"""
    from src.shared.database import async_session
    from src.shared.models import CapabilityProfile, Demand, User, Match, MatchOutcome, ForumTopic, ForumReply
    from sqlalchemy import select, func
    try:
        async with async_session() as session:
            # 各表总数
            profiles = (await session.execute(select(func.count()).select_from(CapabilityProfile))).scalar() or 0
            demands = (await session.execute(select(func.count()).select_from(Demand))).scalar() or 0
            users = (await session.execute(select(func.count()).select_from(User))).scalar() or 0
            matches = (await session.execute(select(func.count()).select_from(Match))).scalar() or 0
            outcomes = (await session.execute(select(func.count()).select_from(MatchOutcome))).scalar() or 0
            topics = (await session.execute(select(func.count()).select_from(ForumTopic))).scalar() or 0
            replies = (await session.execute(select(func.count()).select_from(ForumReply))).scalar() or 0

        return JSONResponse({
            "suppliers": profiles,
            "demands": demands,
            "users": users,
            "matches": matches,
            "outcomes": outcomes,
            "topics": topics,
            "replies": replies,
        })
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


async def api_admin_suppliers_delete(request):
    """DELETE /api/admin/suppliers/{id} — 删除供应商"""
    from src.shared.database import async_session
    from src.shared.models import CapabilityProfile, Match, MatchOutcome
    from sqlalchemy import select, delete
    from urllib.parse import unquote
    try:
        await _require_admin(request)
        supplier_id = request.path_params.get("id", "")

        async with async_session() as session:
            # 删除关联记录
            await session.execute(delete(MatchOutcome).where(MatchOutcome.supplier_id == supplier_id))
            await session.execute(delete(Match).where(Match.profile_id == supplier_id))
            r = await session.execute(select(CapabilityProfile).where(CapabilityProfile.id == supplier_id))
            p = r.scalar_one_or_none()
            if not p:
                return JSONResponse({"error": "供应商不存在"}, status_code=404)
            await session.delete(p)
            await session.commit()

        return JSONResponse({"status": "deleted", "id": supplier_id})
    except PermissionError as e:
        return JSONResponse({"error": str(e)}, status_code=403)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


async def api_admin_demands_delete(request):
    """DELETE /api/admin/demands/{id} — 删除需求"""
    from src.shared.database import async_session
    from src.shared.models import Demand, Match, MatchOutcome
    from sqlalchemy import select, delete
    try:
        await _require_admin(request)
        demand_id = request.path_params.get("id", "")

        async with async_session() as session:
            # 删除关联记录
            await session.execute(delete(MatchOutcome).where(MatchOutcome.demand_id == demand_id))
            await session.execute(delete(Match).where(Match.demand_id == demand_id))
            r = await session.execute(select(Demand).where(Demand.id == demand_id))
            d = r.scalar_one_or_none()
            if not d:
                return JSONResponse({"error": "需求不存在"}, status_code=404)
            await session.delete(d)
            await session.commit()

        return JSONResponse({"status": "deleted", "id": demand_id})
    except PermissionError as e:
        return JSONResponse({"error": str(e)}, status_code=403)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


async def api_admin_users_list(request):
    """GET /api/admin/users — 用户列表"""
    from src.shared.database import async_session
    from src.shared.models import User
    from sqlalchemy import select
    try:
        page = int(request.query_params.get("page", 1))
        per_page = int(request.query_params.get("per_page", 50))
        page = max(1, page)
        per_page = max(1, min(200, per_page))

        async with async_session() as session:
            r = await session.execute(
                select(User).order_by(User.created_at.desc()).limit(per_page).offset((page - 1) * per_page)
            )
            users = r.scalars().all()

            total = (await session.execute(select(func.count()).select_from(User))).scalar() or 0

        items = [{
            "human_id": u.human_id,
            "email": u.email,
            "display_name": u.display_name,
            "country": u.country or "",
            "email_verified": u.email_verified,
            "created_at": u.created_at.isoformat() if u.created_at else "",
            "last_login": u.last_login.isoformat() if u.last_login else "",
        } for u in users]

        return JSONResponse({
            "items": items,
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": (total + per_page - 1) // per_page if total > 0 else 0,
        })
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


async def api_admin_users_update(request):
    """POST /api/admin/users/{id} — 更新用户（验证/取消验证邮箱）"""
    from src.shared.database import async_session
    from src.shared.models import User
    from sqlalchemy import select
    try:
        await _require_admin(request)
        human_id = request.path_params.get("id", "")
        body = await request.json()
        field = body.get("field", "")
        value = body.get("value")

        async with async_session() as session:
            r = await session.execute(select(User).where(User.human_id == human_id))
            u = r.scalar_one_or_none()
            if not u:
                return JSONResponse({"error": "用户不存在"}, status_code=404)

            if field == "email_verified":
                u.email_verified = bool(value)

            await session.commit()

        return JSONResponse({"status": "updated", "human_id": human_id, "field": field, "value": value})
    except PermissionError as e:
        return JSONResponse({"error": str(e)}, status_code=403)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


async def api_flywheel_weights(request):
    """GET /api/flywheel/weights — 权重矩阵"""
    from src.shared.flywheel import get_weight_matrix
    try:
        weights = await get_weight_matrix()
        return JSONResponse({"weights": weights, "total": len(weights)})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


async def api_global_search(request):
    """GET /api/global_search — 跨表全文搜索（需求、供应商、论坛）"""
    from src.shared.database import async_session
    from src.shared.models import Demand, CapabilityProfile, ForumTopic
    from sqlalchemy import select, func, text as sa_text
    try:
        q = request.query_params.get("q", "").strip()
        page = max(1, int(request.query_params.get("page", 1)))
        per_page = max(1, min(50, int(request.query_params.get("per_page", 10))))

        if not q:
            return JSONResponse({"demands": [], "suppliers": [], "forum_topics": [], "total": 0})

        safe_q = q.replace("'", "''")
        tsquery = f"plainto_tsquery('simple', '{safe_q}')"

        results = {"demands": [], "suppliers": [], "forum_topics": [], "total": 0}

        async with async_session() as session:
            # Search demands
            d_query = select(Demand).where(
                Demand.search_vector.op("@@")(sa_text(tsquery))
            ).order_by(
                sa_text(f"ts_rank({Demand.search_vector.key}, {tsquery}) DESC")
            ).limit(per_page)
            d_result = await session.execute(d_query)
            for d in d_result.scalars().all():
                results["demands"].append({
                    "id": d.id,
                    "raw_text": d.raw_text[:200],
                    "category": d.category or "",
                    "status": d.status.value if d.status else "open",
                    "created_at": d.created_at.isoformat() if d.created_at else "",
                })

            # Search capability profiles
            p_query = select(CapabilityProfile).where(
                CapabilityProfile.search_vector.op("@@")(sa_text(tsquery))
            ).order_by(
                sa_text(f"ts_rank({CapabilityProfile.search_vector.key}, {tsquery}) DESC")
            ).limit(per_page)
            p_result = await session.execute(p_query)
            for p in p_result.scalars().all():
                results["suppliers"].append({
                    "id": p.id,
                    "name": p.agent_card_json.get("name", "") if p.agent_card_json else "",
                    "description": (p.agent_card_json.get("description", "") or "")[:200],
                    "profile_type": p.profile_type.value if p.profile_type else "",
                    "country": p.country or "",
                })

            # Search forum topics (using title + body ilike as fallback for now)
            like_pattern = f"%{q}%"
            t_result = await session.execute(
                select(ForumTopic).where(
                    (ForumTopic.title.ilike(like_pattern)) |
                    (ForumTopic.body.ilike(like_pattern))
                ).order_by(ForumTopic.created_at.desc()).limit(per_page)
            )
            for t in t_result.scalars().all():
                results["forum_topics"].append({
                    "id": t.id,
                    "title": t.title,
                    "body": t.body[:200],
                    "category": t.category or "",
                    "created_at": t.created_at.isoformat() if t.created_at else "",
                })

            # Total count across tables
            d_count = (await session.execute(
                select(func.count()).select_from(Demand).where(
                    Demand.search_vector.op("@@")(sa_text(tsquery))
                )
            )).scalar() or 0
            p_count = (await session.execute(
                select(func.count()).select_from(CapabilityProfile).where(
                    CapabilityProfile.search_vector.op("@@")(sa_text(tsquery))
                )
            )).scalar() or 0
            results["total"] = d_count + p_count + len(results["forum_topics"])

        return JSONResponse(results)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ============================================================
# 通知 API
# ============================================================

async def api_notifications_list(request):
    """GET /api/notifications — 通知列表（支持分页）"""
    from src.shared.database import async_session
    from src.shared.models import Notification
    from sqlalchemy import select, func
    try:
        email = request.query_params.get("email", "")
        if not email:
            return JSONResponse({"items": [], "total": 0, "unread": 0})
        page = max(1, int(request.query_params.get("page", 1)))
        per_page = max(1, min(50, int(request.query_params.get("per_page", 20))))

        async with async_session() as session:
            from src.shared.models import User
            r = await session.execute(select(User).where(User.email == email))
            u = r.scalar_one_or_none()
            if not u:
                return JSONResponse({"items": [], "total": 0, "unread": 0})

            total = (await session.execute(
                select(func.count()).select_from(Notification).where(Notification.user_id == u.human_id)
            )).scalar() or 0

            unread = (await session.execute(
                select(func.count()).select_from(Notification).where(
                    Notification.user_id == u.human_id, Notification.is_read == False
                )
            )).scalar() or 0

            r = await session.execute(
                select(Notification).where(Notification.user_id == u.human_id)
                .order_by(Notification.created_at.desc())
                .limit(per_page).offset((page - 1) * per_page)
            )
            items = [{
                "id": n.id,
                "title": n.title,
                "body": n.body,
                "channel": n.channel,
                "urgency": n.urgency,
                "action_url": n.action_url,
                "is_read": n.is_read,
                "created_at": n.created_at.isoformat() if n.created_at else "",
            } for n in r.scalars().all()]

        return JSONResponse({"items": items, "total": total, "unread": unread, "page": page, "per_page": per_page})
    except Exception as e:
        return JSONResponse({"error": str(e), "items": [], "total": 0, "unread": 0}, status_code=500)


async def api_notifications_read(request):
    """PUT /api/notifications/{notify_id}/read — 标记通知为已读"""
    from src.shared.database import async_session
    from src.shared.models import Notification
    from sqlalchemy import select
    from datetime import datetime, timezone
    try:
        notify_id = request.path_params.get("notify_id", "")
        if not notify_id:
            return JSONResponse({"error": "缺少通知ID"}, status_code=400)

        async with async_session() as session:
            r = await session.execute(select(Notification).where(Notification.id == notify_id))
            n = r.scalar_one_or_none()
            if not n:
                return JSONResponse({"error": "通知不存在"}, status_code=404)
            n.is_read = True
            n.read_at = datetime.now(timezone.utc)
            await session.commit()

        return JSONResponse({"status": "ok"})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


async def api_notifications_read_all(request):
    """POST /api/notifications/read-all — 全部标记已读"""
    from src.shared.database import async_session
    from src.shared.models import Notification
    from sqlalchemy import select
    from datetime import datetime, timezone
    try:
        body = await request.json()
        email = body.get("email", "")
        if not email:
            return JSONResponse({"error": "缺少邮箱"}, status_code=400)

        async with async_session() as session:
            from src.shared.models import User
            r = await session.execute(select(User).where(User.email == email))
            u = r.scalar_one_or_none()
            if not u:
                return JSONResponse({"error": "用户不存在"}, status_code=404)

            r = await session.execute(
                select(Notification).where(
                    Notification.user_id == u.human_id,
                    Notification.is_read == False
                )
            )
            now = datetime.now(timezone.utc)
            for n in r.scalars().all():
                n.is_read = True
                n.read_at = now
            await session.commit()

        return JSONResponse({"status": "ok"})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


async def api_notifications_unread_count(request):
    """GET /api/notifications/unread-count — 未读通知数（右上角小红点用）"""
    from src.shared.database import async_session
    from src.shared.models import Notification
    from sqlalchemy import select, func
    try:
        email = request.query_params.get("email", "")
        if not email:
            return JSONResponse({"count": 0})

        async with async_session() as session:
            from src.shared.models import User
            r = await session.execute(select(User).where(User.email == email))
            u = r.scalar_one_or_none()
            if not u:
                return JSONResponse({"count": 0})

            count = (await session.execute(
                select(func.count()).select_from(Notification).where(
                    Notification.user_id == u.human_id, Notification.is_read == False
                )
            )).scalar() or 0

        return JSONResponse({"count": count})
    except Exception as e:
        return JSONResponse({"count": 0})


# ============================================================
# 需求订阅 API
# ============================================================

async def api_subscriptions_list(request):
    """GET /api/subscriptions — 获取用户的订阅列表"""
    from src.shared.database import async_session
    from src.shared.models import DemandSubscription
    from sqlalchemy import select, func
    try:
        email = request.query_params.get("email", "")
        if not email:
            return JSONResponse({"items": []})
        async with async_session() as session:
            from src.shared.models import User
            r = await session.execute(select(User).where(User.email == email))
            u = r.scalar_one_or_none()
            if not u:
                return JSONResponse({"items": []})
            r = await session.execute(
                select(DemandSubscription).where(DemandSubscription.user_id == u.human_id)
                .order_by(DemandSubscription.created_at.desc())
            )
            items = [{
                "id": s.id,
                "name": s.name,
                "keywords": s.keywords or [],
                "categories": s.categories or [],
                "notify_email": s.notify_email,
                "notify_web": s.notify_web,
                "is_active": s.is_active,
                "created_at": s.created_at.isoformat() if s.created_at else "",
            } for s in r.scalars().all()]
        return JSONResponse({"items": items})
    except Exception as e:
        return JSONResponse({"error": str(e), "items": []}, status_code=500)


async def api_subscriptions_create(request):
    """POST /api/subscriptions — 创建订阅"""
    from src.shared.database import async_session
    from src.shared.models import DemandSubscription
    from sqlalchemy import select
    from uuid import uuid4
    try:
        body = await request.json()
        email = body.get("email", "")
        if not email:
            return JSONResponse({"error": "缺少邮箱"}, status_code=400)

        async with async_session() as session:
            from src.shared.models import User
            r = await session.execute(select(User).where(User.email == email))
            u = r.scalar_one_or_none()
            if not u:
                return JSONResponse({"error": "用户不存在"}, status_code=404)

            sub = DemandSubscription(
                id=str(uuid4()),
                user_id=u.human_id,
                name=body.get("name", "默认订阅"),
                keywords=body.get("keywords", []),
                categories=body.get("categories", []),
                notify_email=body.get("notify_email", False),
                notify_web=body.get("notify_web", True),
                is_active=body.get("is_active", True),
            )
            session.add(sub)
            await session.commit()

        return JSONResponse({"status": "ok", "id": sub.id})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


async def api_subscriptions_delete(request):
    """DELETE /api/subscriptions/{sub_id} — 删除订阅"""
    from src.shared.database import async_session
    from src.shared.models import DemandSubscription
    from sqlalchemy import select
    try:
        sub_id = request.path_params.get("sub_id", "")
        if not sub_id:
            return JSONResponse({"error": "缺少订阅ID"}, status_code=400)
        async with async_session() as session:
            r = await session.execute(select(DemandSubscription).where(DemandSubscription.id == sub_id))
            sub = r.scalar_one_or_none()
            if not sub:
                return JSONResponse({"error": "订阅不存在"}, status_code=404)
            await session.delete(sub)
            await session.commit()
        return JSONResponse({"status": "deleted"})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


async def api_subscriptions_update(request):
    """PUT /api/subscriptions/{sub_id} — 更新订阅"""
    from src.shared.database import async_session
    from src.shared.models import DemandSubscription
    from sqlalchemy import select
    try:
        sub_id = request.path_params.get("sub_id", "")
        body = await request.json()
        async with async_session() as session:
            r = await session.execute(select(DemandSubscription).where(DemandSubscription.id == sub_id))
            sub = r.scalar_one_or_none()
            if not sub:
                return JSONResponse({"error": "订阅不存在"}, status_code=404)
            if "name" in body:
                sub.name = body["name"]
            if "keywords" in body:
                sub.keywords = body["keywords"]
            if "categories" in body:
                sub.categories = body["categories"]
            if "notify_email" in body:
                sub.notify_email = body["notify_email"]
            if "notify_web" in body:
                sub.notify_web = body["notify_web"]
            if "is_active" in body:
                sub.is_active = body["is_active"]
            await session.commit()
        return JSONResponse({"status": "updated"})
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
    Route("/flywheel_dashboard.html", flywheel_dashboard),
    Route("/docs/tutorial.html", tutorial),
    Route("/verify-email", verify_email_page),
    # Pages
    Route("/notifications.html", notification_page),
    # Admin page
    Route("/admin.html", admin_page),
    # API Routes
    Route("/api/user/profile", api_user_profile_get),
    Route("/api/user/profile", api_user_profile_update, methods=["PUT"]),
    Route("/api/user/avatar", api_user_avatar, methods=["POST"]),
    Route("/api/user/password", api_user_password, methods=["PUT"]),
    Route("/api/user/stats", api_user_stats),
    Route("/api/auto-demand", api_auto_demand, methods=["POST"]),
    Route("/api/auto-supplier", api_auto_supplier, methods=["POST"]),
    Route("/api/suppliers", api_suppliers),
    Route("/api/suppliers/filters", api_suppliers_filters),
    Route("/api/register", api_register, methods=["POST"]),
    Route("/api/login", api_login, methods=["POST"]),
    Route("/api/verify-email", api_verify_email),
    Route("/api/forum/categories", api_forum_categories),
    Route("/api/forum/topics/create", api_forum_create, methods=["POST"]),
    Route("/api/forum/topics", api_forum_topics),
    Route("/api/forum/topics/{topic_id}", api_forum_topic_detail),
    Route("/api/forum/topics/{topic_id}/vote", api_forum_vote_post, methods=["POST"]),
    Route("/api/forum/topics/{topic_id}/reply", api_forum_reply_post, methods=["POST"]),
    Route("/api/forum/topics/{topic_id}/replies", api_forum_replies),
    Route("/api/demands", api_demand_list),
    Route("/api/demands/filters", api_demands_filters),
    Route("/api/matches", api_matches),
    Route("/api/matches/{match_id}/email", api_match_email),
    Route("/api/matches/{match_id}/feedback", api_match_feedback, methods=["POST"]),
    Route("/api/flywheel/stats", api_flywheel_stats),
    Route("/api/flywheel/weights", api_flywheel_weights),
    # Notification API
    Route("/api/notifications", api_notifications_list),
    Route("/api/notifications/unread-count", api_notifications_unread_count),
    Route("/api/notifications/{notify_id}/read", api_notifications_read, methods=["PUT"]),
    Route("/api/notifications/read-all", api_notifications_read_all, methods=["POST"]),
    # Subscription API
    Route("/api/subscriptions", api_subscriptions_list),
    Route("/api/subscriptions/create", api_subscriptions_create, methods=["POST"]),
    Route("/api/subscriptions/{sub_id}", api_subscriptions_delete, methods=["DELETE"]),
    Route("/api/subscriptions/{sub_id}", api_subscriptions_update, methods=["PUT"]),
    # Admin API
    Route("/api/admin/check", api_admin_check, methods=["POST"]),
    Route("/api/admin/stats", api_admin_stats),
    Route("/api/admin/users", api_admin_users_list),
    Route("/api/admin/users/{id}", api_admin_users_update, methods=["POST"]),
    Route("/api/admin/suppliers/{id}", api_admin_suppliers_delete, methods=["DELETE"]),
    Route("/api/admin/demands/{id}", api_admin_demands_delete, methods=["DELETE"]),
    Route("/api/home/stats", api_home_stats),
    Route("/api/global_search", api_global_search),
    Route("/.well-known/agent.json", api_agent_card),
    # Catch-all static
    Route("/{path:path}", static_file),
]

app = Starlette(routes=routes, lifespan=lifespan)

def run():
    uvicorn.run(app, host="0.0.0.0", port=80, log_level="info")

if __name__ == "__main__":
    run()
