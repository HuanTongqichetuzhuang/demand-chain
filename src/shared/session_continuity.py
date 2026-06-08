"""
会话连续性 — Agent上下文无缝切换协议。

当LLM上下文窗口快满时，Agent自动保存会话状态，
在新窗口中以压缩形式恢复，人类无需重复表述。
"""
import json
import hashlib
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional


# ============================================================
# 会话状态结构
# ============================================================

@dataclass
class SessionState:
    """Agent在任意时刻的完整状态快照"""
    session_id: str
    agent_id: str
    human_id: str

    # 身份与偏好
    human_name: str = ""
    human_role: str = ""           # individual | team | company | research
    human_country: str = ""
    notification_config: dict = field(default_factory=dict)
    info_levels: dict = field(default_factory=dict)  # L0-L4偏好

    # 当前上下文
    active_demands: list[str] = field(default_factory=list)      # 活跃需求ID列表
    active_matches: list[dict] = field(default_factory=list)     # 待处理匹配
    pending_confirmations: list[dict] = field(default_factory=list)  # 待L3确认

    # 对话摘要
    conversation_summary: str = ""   # 100字以内的当前对话压缩
    last_user_intent: str = ""       # 人类上一次想做什么
    key_decisions: list[str] = field(default_factory=list)   # 本次会话关键决策

    # 时间戳
    saved_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    context_usage_pct: int = 0      # 保存时上下文窗口使用率
    window_number: int = 1          # 这是第几个窗口


class SessionContinuity:
    """
    会话连续性管理器。
    当Agent检测到上下文窗口快满时（>80%），触发保存。
    """

    CONTEXT_THRESHOLD = 80   # 使用率超过此值触发保存
    SUMMARY_MAX_CHARS = 5000  # 摘要最大字数

    def __init__(self):
        self.sessions: dict[str, SessionState] = {}

    def should_checkpoint(self, context_usage_pct: int) -> bool:
        """判断是否需要保存会话状态"""
        return context_usage_pct >= self.CONTEXT_THRESHOLD

    def create_checkpoint(
        self,
        agent_id: str,
        human_id: str,
        conversation_history: list[dict],
        active_demands: list[str],
        active_matches: list[dict],
        context_usage_pct: int,
        state: Optional[SessionState] = None,
    ) -> SessionState:
        """
        创建会话检查点。
        压缩对话历史 → 提取关键信息 → 保存为可恢复状态。
        """
        if state is None:
            state = self._load_or_create(agent_id, human_id)

        # 更新动态状态
        state.active_demands = active_demands
        state.active_matches = active_matches
        state.context_usage_pct = context_usage_pct
        state.window_number += 1
        state.saved_at = datetime.now(timezone.utc).isoformat()

        # 压缩对话历史
        state.conversation_summary = self._summarize(conversation_history)
        state.last_user_intent = self._extract_intent(conversation_history)
        state.key_decisions = self._extract_decisions(conversation_history)

        # 持久化
        self.sessions[state.session_id] = state

        return state

    def generate_handoff_prompt(self, state: SessionState) -> str:
        """
        生成新窗口的初始化提示词。
        Agent在新窗口中粘贴此文本，无缝恢复上下文。
        """
        return f"""## 会话恢复 — 窗口 #{state.window_number}

你正在继续与 {state.human_name or '用户'} 的对话。
以下是之前会话的状态摘要：

### 用户身份
- 角色：{state.human_role or '未设定'}
- 国家：{state.human_country or '未设定'}
- 信息分享偏好：{json.dumps(state.info_levels, ensure_ascii=False) if state.info_levels else '未设定'}

### 上次对话摘要
{state.conversation_summary}

### 上次人类想做什么
{state.last_user_intent}

### 活跃需求
{', '.join(state.active_demands) if state.active_demands else '无'}

### 待处理匹配
{json.dumps(state.active_matches, ensure_ascii=False, indent=2) if state.active_matches else '无'}

### 关键决策
{chr(10).join('- ' + d for d in state.key_decisions) if state.key_decisions else '无'}

### 通知配置
{json.dumps(state.notification_config, ensure_ascii=False) if state.notification_config else '未设定'}

---
现在用自然语言告知人类：
"之前的对话太长了，我开了一个新的对话窗口，所有重要信息我都记住了。我们继续——你刚才想{state.last_user_intent}。"

然后继续对话。"""
    
    def generate_human_summary(self, state: SessionState) -> str:
        """生成给人类看的恢复摘要（简短）"""
        return (
            f"对话窗口 #{state.window_number}\n"
            f"上一次你提到：{state.last_user_intent}\n"
            f"活跃需求：{len(state.active_demands)} 条\n"
            f"待处理：{len(state.active_matches)} 条匹配\n"
        )

    def _load_or_create(self, agent_id: str, human_id: str) -> SessionState:
        """加载已有状态或创建新的"""
        for s in self.sessions.values():
            if s.agent_id == agent_id:
                return s

        session_id = hashlib.sha256(
            f"{agent_id}|{datetime.now(timezone.utc).isoformat()}".encode()
        ).hexdigest()[:16]

        state = SessionState(
            session_id=session_id,
            agent_id=agent_id,
            human_id=human_id,
            window_number=1,
        )
        return state

    def _summarize(self, history: list[dict]) -> str:
        """
        压缩对话历史为简短摘要。
        Phase 1: 规则提取；Phase 2: LLM压缩。
        """
        # 取最后5轮对话的关键信息
        recent = history[-10:] if len(history) > 10 else history
        user_msgs = [m["content"][:100] for m in recent if m.get("role") == "user"]
        assistant_actions = [m["content"][:80] for m in recent if m.get("role") == "assistant"]

        summary = "用户关注：" + "；".join(user_msgs[-3:]) if user_msgs else "无对话记录"
        if assistant_actions:
            summary += " | Agent执行：" + assistant_actions[-1]
        return summary[:self.SUMMARY_MAX_CHARS]

    def _extract_intent(self, history: list[dict]) -> str:
        """提取用户最后意图"""
        for m in reversed(history):
            if m.get("role") == "user":
                return m["content"][:150]
        return "继续之前的话题"

    def _extract_decisions(self, history: list[dict]) -> list[str]:
        """提取本次会话的关键决策"""
        decisions = []
        for m in history:
            content = m.get("content", "")
            if m.get("role") == "assistant":
                if any(kw in content for kw in ["已发布", "已匹配", "已确认", "已拒绝", "已接受"]):
                    decisions.append(content[:120])
        return decisions[-5:]  # 保留最近5条


# ============================================================
# 全局实例
# ============================================================

session_continuity = SessionContinuity()
