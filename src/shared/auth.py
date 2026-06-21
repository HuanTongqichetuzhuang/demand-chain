"""
身份认证 — Agent 必须先注册/登录获取 token，调工具时必须带上。
没有 token 的工具调用直接拒绝。防止未注册的 Agent 无限制访问。

持久化方案：每次创建/验证都写入数据库，同时维护内存缓存保证热路径性能。
"""
import hashlib
import logging
import secrets
import time
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

# 内存缓存: token_hash → {human_id, agent_id, created_at, expires_at}
_token_cache: dict[str, dict] = {}
# 防止验证时每次都查 DB：已从 DB 加载过的 token 记在这里
_loaded_from_db: set[str] = set()


async def _persist_token(token_hash: str, human_id: str, agent_id: str,
                         expires_at: datetime):
    """写入 token 到数据库"""
    from src.shared.database import async_session
    from src.shared.models import AuthToken
    try:
        async with async_session() as session:
            session.add(AuthToken(
                token_hash=token_hash,
                human_id=human_id,
                agent_id=agent_id,
                expires_at=expires_at,
            ))
            await session.commit()
    except Exception as e:
        logger.error(f"Failed to persist token: {e}")


async def _load_token_from_db(token_hash: str) -> dict | None:
    """从数据库加载一个 token"""
    from src.shared.database import async_session
    from src.shared.models import AuthToken
    from sqlalchemy import select
    try:
        async with async_session() as session:
            r = await session.execute(
                select(AuthToken).where(AuthToken.token_hash == token_hash)
            )
            t = r.scalar_one_or_none()
            if t and t.expires_at > datetime.now(timezone.utc):
                return {
                    "human_id": t.human_id,
                    "agent_id": t.agent_id,
                    "created_at": t.created_at.isoformat() if t.created_at else "",
                    "expires_at": t.expires_at.timestamp(),
                }
    except Exception as e:
        logger.error(f"Failed to load token from DB: {e}")
    return None


async def create_token(human_id: str, agent_id: str, expire_hours: int = 48) -> str:
    """创建短期 token（持久化到数据库 + 内存缓存）"""
    raw = f"{human_id}_{agent_id}_{secrets.token_urlsafe(16)}"
    token = hashlib.sha256(raw.encode()).hexdigest()[:32]
    now = time.time()
    expires_dt = datetime.now(timezone.utc) + timedelta(hours=expire_hours)
    entry = {
        "human_id": human_id,
        "agent_id": agent_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": now + expire_hours * 3600,
    }
    # 写入缓存
    _token_cache[token] = entry
    _loaded_from_db.add(token)
    # 异步持久化到 DB（不阻塞返回）
    await _persist_token(token, human_id, agent_id, expires_dt)
    return token


async def verify(token: str) -> dict:
    """
    验证 token。成功返回 {human_id, agent_id, ...}，失败抛异常。
    优先查内存缓存 → 查 DB → 抛异常。
    """
    if not token:
        raise PermissionError(
            "没有提供 session_token。请先让人类注册或登录："
            "register_human(email, display_name, password)"
            " 或 login_human(email, password)"
        )

    # 1. 内存缓存
    entry = _token_cache.get(token)
    if entry:
        if time.time() > entry["expires_at"]:
            _token_cache.pop(token, None)
            raise PermissionError("session_token 已过期（48小时）。请让人类重新登录。")
        return entry

    # 2. 数据库（只查一次，查到后加入缓存）
    if token not in _loaded_from_db:
        entry = await _load_token_from_db(token)
        if entry:
            _token_cache[token] = entry
            _loaded_from_db.add(token)  # ← 只有DB查到才标记，防止瞬态失败导致永久负缓存
            return entry

    raise PermissionError("session_token 无效。请让人类重新登录。")


async def invalidate(token: str):
    """使 token 失效（从缓存和数据库删除）"""
    _token_cache.pop(token, None)
    _loaded_from_db.discard(token)
    from src.shared.database import async_session
    from src.shared.models import AuthToken
    from sqlalchemy import select, delete
    try:
        async with async_session() as session:
            await session.execute(
                delete(AuthToken).where(AuthToken.token_hash == token)
            )
            await session.commit()
    except Exception as e:
        logger.error(f"Failed to delete token from DB: {e}")


async def cleanup_expired_tokens():
    """清理过期 token（由定时任务调用）"""
    from src.shared.database import async_session
    from src.shared.models import AuthToken
    from sqlalchemy import delete
    from datetime import datetime, timezone
    try:
        async with async_session() as session:
            result = await session.execute(
                delete(AuthToken).where(AuthToken.expires_at < datetime.now(timezone.utc))
            )
            await session.commit()
            if result.rowcount:
                logger.info(f"Cleaned up {result.rowcount} expired tokens")
    except Exception as e:
        logger.error(f"Failed to cleanup expired tokens: {e}")

