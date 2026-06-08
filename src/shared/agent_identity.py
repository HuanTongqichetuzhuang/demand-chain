"""
Agent 身份系统 — 唯一识别码生成、身份绑定、认证验证。

基于 A2A AgentCard 标准，使用 ULID 作为 agent_id。
Phase 1：API Key 认证；Phase 2：Ed25519 签名认证。
"""
import hashlib
import hmac
import secrets
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


# ============================================================
# Agent 身份数据结构
# ============================================================

@dataclass
class AgentIdentity:
    """
    一个 Agent 的唯一身份。
    agent_id: ULID格式，26字符，Crockford Base32编码
    human_id: 这个Agent代表的人类/组织ID
    display_name: 人类可读名称
    created_at: 身份创建时间
    """
    agent_id: str
    human_id: str
    display_name: str
    api_key_hash: str = ""
    public_key: Optional[str] = None  # Phase 2: Ed25519公钥
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def mask(self) -> str:
        """返回可安全展示的身份摘要"""
        return f"{self.display_name} ({self.agent_id[:8]}...)"


# ============================================================
# API Key 生成与验证（Phase 1）
# ============================================================

def generate_api_key() -> tuple[str, str]:
    """
    生成 API Key 和其哈希。
    返回 (原始key, 哈希值)。原始key只展示一次给人类。
    """
    raw = f"dc_{secrets.token_urlsafe(32)}"
    hashed = hashlib.sha256(raw.encode()).hexdigest()
    return raw, hashed


def verify_api_key(raw_key: str, stored_hash: str) -> bool:
    """验证 API Key 是否匹配存储的哈希"""
    return hmac.compare_digest(
        hashlib.sha256(raw_key.encode()).hexdigest(),
        stored_hash
    )


# ============================================================
# 身份注册流程
# ============================================================

class AgentRegistry:
    """
    Agent 身份注册表。
    管理 Agent 的注册、查询、验证。
    """

    def __init__(self):
        # 内存存储（生产环境用数据库）
        self._agents: dict[str, AgentIdentity] = {}
        self._human_agents: dict[str, list[str]] = {}  # human_id → [agent_id, ...]

    def register(
        self,
        human_id: str,
        display_name: str,
        agent_id: Optional[str] = None,
    ) -> tuple[AgentIdentity, str]:
        """
        注册一个新 Agent。
        返回 (AgentIdentity, 原始API Key)。API Key只返回这一次。
        """
        if agent_id is None:
            agent_id = generate_ulid()

        api_key, api_key_hash = generate_api_key()

        identity = AgentIdentity(
            agent_id=agent_id,
            human_id=human_id,
            display_name=display_name,
            api_key_hash=api_key_hash,
        )

        self._agents[agent_id] = identity
        if human_id not in self._human_agents:
            self._human_agents[human_id] = []
        self._human_agents[human_id].append(agent_id)

        return identity, api_key

    def authenticate(self, agent_id: str, api_key: str) -> Optional[AgentIdentity]:
        """验证 Agent 身份。返回 AgentIdentity 或 None。"""
        identity = self._agents.get(agent_id)
        if identity and verify_api_key(api_key, identity.api_key_hash):
            return identity
        return None

    def get(self, agent_id: str) -> Optional[AgentIdentity]:
        return self._agents.get(agent_id)

    def list_for_human(self, human_id: str) -> list[AgentIdentity]:
        """列出某个人类拥有的所有 Agent"""
        return [self._agents[aid] for aid in self._human_agents.get(human_id, []) if aid in self._agents]


# ============================================================
# ULID 生成器（简版，Phase 2用完整 ulid-py 库）
# ============================================================

def generate_ulid() -> str:
    """
    生成 ULID 格式的唯一标识符。
    26字符，Crockford Base32编码。
    ULID = 48位时间戳 + 80位随机数
    """
    import os
    timestamp = int(time.time() * 1000)
    random_bytes = os.urandom(10)

    # Crockford Base32 编码
    alphabet = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
    value = (timestamp << 80) | int.from_bytes(random_bytes, "big")

    chars = []
    for _ in range(26):
        chars.append(alphabet[value & 0x1F])
        value >>= 5
    return "".join(reversed(chars))


# ============================================================
# 全局实例
# ============================================================

agent_registry = AgentRegistry()
