"""
贡献意愿系统 — 完全自愿的"感恩机制"。

原则：
- 匹配永远免费。任何人不付费也能用全部功能。
- 合作完成后，如果觉得平台帮到了你，自愿贡献。
- 贡献多少、贡献不计、不贡献——完全由你决定。
- 平台记录每一笔贡献，但不强制、不提醒、不诱导。
"""
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class ContributionType(str, Enum):
    MONEY = "money"           # 金钱
    TESTIMONIAL = "testimonial"  # 证言/案例
    REFERRAL = "referral"       # 推荐他人
    CODE = "code"              # 贡献代码
    CONTENT = "content"        # 文档/翻译/教程


@dataclass
class Contribution:
    match_id: str
    demand_id: str
    contributor_agent_id: str
    contribution_type: ContributionType
    amount: float = 0.0
    currency: str = "CNY"
    testimonial_text: str = ""
    referral_count: int = 0
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ContributionService:
    """
    贡献服务。
    唯一职责：记录。不催缴、不提醒、不设限制。
    """

    # 贡献"名人堂"数据 — 公开可查
    _hall_of_gratitude: list[dict] = []

    async def record(
        self,
        match_id: str,
        demand_id: str,
        agent_id: str,
        contribution_type: str = "money",
        amount: float = 0.0,
        currency: str = "CNY",
        testimonial_text: str = "",
        referral_count: int = 0,
    ) -> dict:
        """记录一笔自愿贡献。什么都不做——就是记下来。"""

        # 存入名人堂
        entry = {
            "match_id": match_id,
            "demand_id": demand_id,
            "agent_id": agent_id[:8],
            "type": contribution_type,
            "amount": amount,
            "currency": currency,
            "testimonial": testimonial_text[:200],
            "referrals": referral_count,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }
        self._hall_of_gratitude.append(entry)

        logger.info(f"[贡献] {agent_id[:8]}... 类型={contribution_type} 金额={amount}")
        return {"status": "recorded", "message": "感谢你的心意。记录已完成。"}

    def get_hall(self, limit: int = 50) -> list[dict]:
        """查看贡献榜（公开）"""
        return sorted(
            self._hall_of_gratitude,
            key=lambda x: x.get("amount", 0),
            reverse=True
        )[:limit]

    async def generate_contribution_invitation(
        self, match_id: str, demand_title: str
    ) -> str:
        """
        生成一段给人类的自然语言邀请——仅在合作完成时由Agent呈现一次。
        不包含催促、限制或任何负面暗示。
        """
        return (
            f"合作「{demand_title[:40]}」已完成。"
            f"如果你觉得需求链平台对这次合作有帮助，你可以自愿支持平台——"
            f"金钱、写一段感谢的话、推荐给朋友、贡献代码——都可以。"
            f"完全不支持也完全可以。平台功能不受任何影响。"
        )


# 全局实例
contribution_service = ContributionService()
