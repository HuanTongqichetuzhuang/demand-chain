"""
需求领域服务：处理需求的发布、结构化、查询。
"""
import json
import logging
from typing import Optional
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.models import Demand, DemandStatus
from src.adapters.llm_client import get_llm
from src.shared.classification import classification_service, ClassificationResult

logger = logging.getLogger(__name__)

STRUCTURING_PROMPT_ZH = """你是需求分析助手。将用户的自然语言需求按以下模板结构化输出为JSON。你必须填满所有字段——如果用户没说就填"未知"或空数组。

# 模板（严格按此结构输出）：
{
  "classification": {
    "demand_type": "产品改良 | 全新发明 | 技术攻关 | 方案征集 | 信息查询 | 产能合作 | 实验验证 | 人才招募",
    "industry": "传感器技术 | 材料科学 | 生物医药 | 信息技术 | 新能源 | 机械制造 | 化工 | 农业食品 | 航空航天 | 环境工程 | 建筑工程 | 交通运输 | 教育培训 | 金融科技 | 其他",
    "application_scenario": "一句话描述应用场景",
    "sub_industry_tags": ["标签1", "标签2"]
  },
  "problem": {
    "pain_point": "当前遇到的痛点",
    "current_solution": "现有方案和不足",
    "why_now": "为什么现在需要解决"
  },
  "requirement": {
    "core_need": "一句话概括需求核心",
    "technical_specs": [{"parameter": "参数名", "value": "值", "unit": "单位", "requirement": "min或max或exact"}],
    "deliverable": "方案设计 | 原型样机 | 小批量试产 | 量产供应 | 研究报告 | 技术咨询",
    "volume": {"initial_batch": 0, "annual_forecast": 0, "unit": "数量单位"}
  },
  "constraints": {
    "budget_range": "<50万 | 50-200万 | 200-500万 | 500-2000万 | >2000万 | 未定",
    "timeline": {"urgency": "紧急 | 标准 | 规划 | 远期", "expected_delivery": "时间"},
    "geographic": {"user_country": "用户所在国", "user_region": "地区"},
    "ip_terms": {"ownership": "需求方独有 | 双方共有 | 供给方可保留 | 待协商", "nda_required": true},
    "compliance": ["标准或法规"]
  },
  "evidence": {
    "has_existing_data": false,
    "has_experiment_video": false,
    "has_technical_drawing": false,
    "prior_attempts": "之前尝试过的方法",
    "references": [{"type": "patent或paper", "id": "编号", "relevance": "相关性说明"}]
  },
  "matching_preferences": {
    "prefer_experienced": true,
    "accept_academic": true,
    "accept_individual": true,
    "accept_startup": true
  }
}

# 规则：
1. 用户没明确说的字段，填"未知"或false或空数组
2. technical_specs 尽可能从文本中提取可量化的指标
3. 推断 industry 和 demand_type 时要准确，不要猜错
4. 输出纯JSON，不要有其他文字"""

STRUCTURING_PROMPT_EN = """You are a demand analysis assistant. Structure the user's natural language demand into the following JSON template. Fill ALL fields - use "unknown" or empty arrays if the user didn't mention it.

# Template (output strictly in this structure):
{
  "classification": {
    "demand_type": "product_improvement | new_invention | tech_breakthrough | solution_solicitation | info_query | capacity_cooperation | experiment_verification | talent_recruitment",
    "industry": "sensor_tech | materials_science | biomedicine | information_tech | new_energy | mechanical_mfg | chemical | agrifood | aerospace | environmental | construction | transportation | education | fintech | other",
    "application_scenario": "One sentence describing the use case",
    "sub_industry_tags": ["tag1", "tag2"]
  },
  "problem": {
    "pain_point": "What pain point exists",
    "current_solution": "Current solution and its shortcomings",
    "why_now": "Why this needs solving now"
  },
  "requirement": {
    "core_need": "One sentence: what exactly is needed",
    "technical_specs": [{"parameter": "name", "value": "val", "unit": "unit", "requirement": "min|max|exact"}],
    "deliverable": "design_proposal | prototype | small_batch | mass_production | research_report | consulting",
    "volume": {"initial_batch": 0, "annual_forecast": 0, "unit": "unit"}
  },
  "constraints": {
    "budget_range": "<500K | 500K-2M | 2M-5M | 5M-20M | >20M | unknown",
    "timeline": {"urgency": "urgent | standard | planned | long_term", "expected_delivery": "date"},
    "geographic": {"user_country": "country", "user_region": "region"},
    "ip_terms": {"ownership": "buyer_owned | shared | supplier_retains | to_negotiate", "nda_required": true},
    "compliance": ["standard or regulation"]
  },
  "evidence": {
    "has_existing_data": false,
    "has_experiment_video": false,
    "has_technical_drawing": false,
    "prior_attempts": "What was tried before",
    "references": [{"type": "patent|paper", "id": "id", "relevance": "how it relates"}]
  },
  "matching_preferences": {
    "prefer_experienced": true,
    "accept_academic": true,
    "accept_individual": true,
    "accept_startup": true
  }
}

# Rules:
1. Fields not mentioned by user: fill "unknown" or false or empty array
2. Extract quantifiable specs from text into technical_specs
3. Infer industry and demand_type accurately, do not guess wrong
4. Output pure JSON only, no extra text"""


class DemandService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.llm = get_llm()

    async def publish(self, user_id: str, raw_text: str, lang: str = "zh") -> Demand:
        demand = Demand(
            id=str(uuid4()),
            user_id=user_id,
            raw_text=raw_text,
            status=DemandStatus.STRUCTURING,
        )
        self.session.add(demand)
        await self.session.commit()

        try:
            structured = await self._structure(raw_text)
            demand.structured_json = structured
            demand.category = (
                structured.get("classification", {}).get("industry", "未知")
            )
            demand.status = DemandStatus.OPEN
            logger.info(f"[{demand.id}] 结构化完成，行业={demand.category}")

            # 多维度学科/技术分类
            try:
                result = await classification_service.classify(raw_text, structured)
                fields = classification_service.to_index_fields(result)
                demand.classification_json = fields["classification"]
                demand.search_text = fields["search_text"]
                demand.discipline_path = fields["discipline_path"]
                demand.ipc_codes = fields["ipc_codes"]
                demand.process_categories = fields["process_categories"]
                logger.info(f"[{demand.id}] 分类完成: {fields['discipline_path']}")
            except Exception as e2:
                logger.warning(f"[{demand.id}] 分类失败（不影响发布）: {e2}")

        except Exception as e:
            logger.error(f"[{demand.id}] 结构化失败: {e}")
            demand.status = DemandStatus.OPEN

        await self.session.commit()
        return demand

    async def _structure(self, raw_text: str, lang: str = "zh") -> dict:
        prompt = STRUCTURING_PROMPT_ZH if lang == "zh" else STRUCTURING_PROMPT_EN
        response = await self.llm.chat(prompt, raw_text)
        return json.loads(response)

    async def get(self, demand_id: str) -> Optional[Demand]:
        result = await self.session.execute(
            select(Demand).where(Demand.id == demand_id)
        )
        return result.scalar_one_or_none()

    async def search(
        self,
        keyword: Optional[str] = None,
        category: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 20,
    ) -> list[Demand]:
        query = select(Demand)
        if keyword:
            query = query.where(Demand.raw_text.ilike(f"%{keyword}%"))
        if category:
            query = query.where(Demand.category == category)
        if status:
            query = query.where(Demand.status == status)
        query = query.order_by(Demand.created_at.desc()).limit(limit)
        result = await self.session.execute(query)
        return list(result.scalars().all())
