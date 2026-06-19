"""
需求链分解引擎 — 使用 LLM 将复杂需求自动分解为可执行的子需求链。
依赖现有的分类体系 (classification.py) 和 LLM 客户端 (llm_client.py)。
"""
import json
import logging
from typing import Optional

from src.adapters.llm_client import get_llm

logger = logging.getLogger(__name__)


DECOMPOSE_PROMPT = """你是需求工程专家。你的任务是将一个复杂的技术需求分解为更小、更可执行的子需求。

分析输入需求，判断可以从哪些维度分解：
1. **技术模块** — 如果需求涉及多个技术领域，按模块拆分
2. **工程阶段** — 如果需求涉及多个阶段，按阶段拆分（如：调研→设计→原型→测试→量产）
3. **组件层级** — 如果需求是一个系统，按子系统/组件拆分
4. **并行任务** — 如果子需求可以并行执行，优先并行拆分

输出格式（JSON数组）：
[
  {{
    "title": "子需求简短名称",
    "description": "子需求的详细描述（50-200字）",
    "category": "所属行业分类（从分类体系中选择最匹配的）",
    "decomposition_reason": "为什么这样拆分"
  }}
]

约束：
- 每个需求的原始文本不要超过200字
- 输出 2-5 条子需求
- 子需求之间应该能并行或顺序执行
- 子需求整体应该覆盖原始需求的全部范围
- 使用中文输出
"""


async def auto_decompose(demand_id: str, raw_text: str, category: Optional[str] = None) -> list[dict]:
    """使用 LLM 将需求文本自动分解为子需求列表。
    
    Args:
        demand_id: 原始需求 ID
        raw_text: 原始需求文本
        category: 原始需求的行业分类（可选）
    
    Returns:
        子需求列表，每个元素包含 title/description/category/decomposition_reason
    """
    if not raw_text or len(raw_text.strip()) < 20:
        logger.warning(f"[Decomposer] 需求文本过短 ({len(raw_text or '')} chars)，跳过分解")
        return []

    user_msg = f"## 需求文本\n{raw_text}\n"
    if category:
        user_msg += f"\n## 所属行业分类\n{category}\n"
    user_msg += "\n请将上述需求分解为 2-5 个可执行的子需求。"

    try:
        llm = get_llm()
        result = await llm.chat(DECOMPOSE_PROMPT, user_msg)
        
        # Parse JSON from LLM response
        result = result.strip()
        # Handle markdown code blocks
        if result.startswith("```"):
            lines = result.split("\n")
            start = 0
            for i, line in enumerate(lines):
                if line.strip().startswith("```"):
                    start = i + 1
                    break
            end = len(lines)
            for i in range(len(lines) - 1, start, -1):
                if lines[i].strip().startswith("```"):
                    end = i
                    break
            result = "\n".join(lines[start:end])

        sub_demands = json.loads(result)
        if not isinstance(sub_demands, list):
            logger.warning(f"[Decomposer] LLM 返回非数组: {type(sub_demands)}")
            return []

        # Validate and filter
        valid = []
        for item in sub_demands:
            if isinstance(item, dict) and item.get("title") and item.get("description"):
                valid.append({
                    "title": item["title"][:100],
                    "description": item["description"][:500],
                    "category": item.get("category", category or ""),
                    "decomposition_reason": item.get("decomposition_reason", ""),
                })
            else:
                logger.warning(f"[Decomposer] 跳过无效子需求: {item}")

        logger.info(f"[Decomposer] 需求 {demand_id[:8]}... → 分解为 {len(valid)} 个子需求")
        return valid

    except json.JSONDecodeError as e:
        logger.error(f"[Decomposer] JSON 解析失败: {e}\n原始输出: {result[:500]}")
        return []
    except Exception as e:
        logger.error(f"[Decomposer] LLM 调用失败: {e}")
        return []

