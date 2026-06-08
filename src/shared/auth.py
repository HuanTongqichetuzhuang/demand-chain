"""
身份认证 — Agent 必须先注册/登录获取 token，调工具时必须带上。
没有 token 的工具调用直接拒绝。防止未注册的 Agent 无限制访问。
"""
import hashlib
import logging
import secrets
import time
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# token → {human_id, agent_id, created_at, expires_at}
_tokens: dict[str, dict] = {}


def create_token(human_id: str, agent_id: str, expire_hours: int = 48) -> str:
    """创建短期 token"""
    raw = f"{human_id}_{agent_id}_{secrets.token_urlsafe(16)}"
    token = hashlib.sha256(raw.encode()).hexdigest()[:32]
    now = time.time()
    _tokens[token] = {
        "human_id": human_id,
        "agent_id": agent_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": now + expire_hours * 3600,
    }
    return token


def verify(token: str) -> dict:
    """
    验证 token。成功返回 human_id，失败抛异常。
    """
    if not token:
        raise PermissionError(
            "没有提供 session_token。请先让人类注册或登录："
            "register_human(email, display_name, password)"
            " 或 login_human(email, password)"
        )
    entry = _tokens.get(token)
    if not entry:
        raise PermissionError("session_token 无效。请让人类重新登录。")
    if time.time() > entry["expires_at"]:
        _tokens.pop(token, None)
        raise PermissionError("session_token 已过期（48小时）。请让人类重新登录。")
    return entry


def invalidate(token: str):
    _tokens.pop(token, None)
