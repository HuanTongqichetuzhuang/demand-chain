"""
MCP 会话追踪 — 哪个 Agent 连上来、有没有注册。
每个 SSE 连接是一个 session。注册/登录后 session 绑到人类账号。
"""
import logging

logger = logging.getLogger(__name__)

class SessionTracker:
    """追踪 MCP 会话状态"""

    def __init__(self):
        # session_id → {human_id, agent_id, email, connected_at}
        self._sessions: dict[str, dict] = {}

    def create(self, session_id: str):
        """新连接建立"""
        from datetime import datetime, timezone
        self._sessions[session_id] = {
            "connected_at": datetime.now(timezone.utc).isoformat(),
            "human_id": None,
            "agent_id": None,
            "email": None,
        }
        logger.info(f"[Session] 新连接: {session_id[:12]}...")

    def destroy(self, session_id: str):
        self._sessions.pop(session_id, None)

    def bind(self, session_id: str, human_id: str, agent_id: str, email: str = ""):
        """会话绑定到人类账号"""
        if session_id not in self._sessions:
            self.create(session_id)
        self._sessions[session_id]["human_id"] = human_id
        self._sessions[session_id]["agent_id"] = agent_id
        self._sessions[session_id]["email"] = email
        logger.info(f"[Session] {session_id[:12]}... → {email}")

    def is_authenticated(self, session_id: str) -> bool:
        return (
            session_id in self._sessions
            and self._sessions[session_id]["human_id"] is not None
        )

    def get(self, session_id: str) -> dict:
        return self._sessions.get(session_id, {})

    def require_human(self, session_id: str) -> str:
        """返回 human_id，如果没注册则抛出异常"""
        if not self.is_authenticated(session_id):
            raise PermissionError(
                "未注册或未登录。请先让人类提供邮箱和密码，"
                "你调用 register_human 或 login_human 完成身份验证。"
            )
        return self._sessions[session_id]["human_id"]


session_tracker = SessionTracker()

