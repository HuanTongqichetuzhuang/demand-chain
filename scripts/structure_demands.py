"""
批量需求结构化脚本 — 从数据库取出未结构化的需求，调用 LLM 分类 + 结构化。
仅处理 raw_text 不为空且 structured_json 为空的记录。
"""
import asyncio, json, os, sys, time, traceback
from uuid import uuid4

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.shared.database import async_session
from src.shared.models import Demand
from src.shared.classification import classification_service
from src.adapters.llm_client import get_llm
from sqlalchemy import select, update

# 不依赖外部 embedding 的结构化 prompt
STRUCTURE_PROMPT = """你是一个需求分析助手。阅读下面的需求描述，提取关键信息。

输出严格的 JSON（不要其他文字）：

{
  "summary": "一句话中文摘要，不超过100字",
  "target_specs": [{"parameter": "参数名（中文）", "value": "数值", "unit": "单位", "requirement": "min/max/exact"}],
  "application_field": "应用领域（传感器/材料/新能源/AI/生物医药/航空航天/制造/环境/交通/其他）",
  "tags": ["标签1", "标签2", "标签3"],
  "urgency": "紧急/标准/远期",
  "budget_hint": "预算线索，若无填未知"
}

规则：
1. 没有的信息填"未知"
2. 英文需求翻译成中文摘要
3. 技术参数提取可量化指标"""

BATCH_SIZE = 10
DELAY_BETWEEN = 2  # seconds, avoid rate limit


async def structure_one(demand_id: str, raw_text: str) -> dict:
    """对单条需求做结构化"""
    llm = get_llm()
    try:
        response = await llm.chat(STRUCTURE_PROMPT, raw_text[:3000])
        # Parse JSON — strip markdown, handle leading/trailing whitespace
        text = response.strip()
        # Remove markdown fences if present
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text[:-3]
        text = text.strip()
        # Find JSON object bounds
        brace_start = text.find("{")
        brace_end = text.rfind("}")
        if brace_start >= 0 and brace_end > brace_start:
            text = text[brace_start:brace_end + 1]
        return json.loads(text)
    except Exception as e:
        print(f"  LLM error: {e}")
        import traceback
        traceback.print_exc()
        return {"summary": raw_text[:100], "tags": [], "error": str(e)}


async def classify_one(raw_text: str, structured: dict) -> dict | None:
    """对单条需求做多维度分类"""
    try:
        result = await classification_service.classify(raw_text, structured)
        fields = classification_service.to_index_fields(result)
        return fields
    except Exception as e:
        print(f"  分类失败: {e}")
        return None


async def main():
    async with async_session() as session:
        # Get unstructured demands
        result = await session.execute(
            select(Demand.id, Demand.raw_text, Demand.category)
            .where(Demand.raw_text.isnot(None))
            .where(Demand.structured_json.is_(None))
            .limit(200)
        )
        rows = list(result.all())
        total = len(rows)
        print(f"待处理: {total} 条需求")

        success = 0
        for i, (did, raw, cat) in enumerate(rows):
            if not raw or len(raw.strip()) < 10:
                continue

            print(f"\n[{i+1}/{total}] {did[:8]}... {raw[:60]}")

            # 1. Structure
            structured = await structure_one(did, raw)
            if "error" in structured:
                # Minimal fallback
                structured = {
                    "summary": raw[:100],
                    "target_specs": [],
                    "application_field": cat or "其他",
                    "tags": cat.split(",") if cat else [],
                    "urgency": "标准",
                    "budget_hint": "未知",
                }

            # 2. Classify (multi-dimension)
            fields = await classify_one(raw, structured)
            new_category = structured.get("application_field", cat or "其他")

            # 3. Update DB
            try:
                async with async_session() as s2:
                    demand = (await s2.execute(select(Demand).where(Demand.id == did))).scalar_one_or_none()
                    if demand:
                        demand.structured_json = structured
                        demand.category = new_category
                        if fields:
                            demand.classification_json = fields["classification"]
                            demand.search_text = fields["search_text"]
                            demand.discipline_path = fields["discipline_path"]
                            demand.ipc_codes = fields["ipc_codes"]
                            demand.process_categories = fields["process_categories"]
                        await s2.commit()
                        success += 1
                        print(f"  ✓ 分类={new_category}, tags={structured.get('tags', [])}")
            except Exception as e:
                print(f"  ✗ DB 写入失败: {e}")
                traceback.print_exc()

            # Rate limit
            if i < total - 1:
                await asyncio.sleep(DELAY_BETWEEN)

        print(f"\n{'='*50}")
        print(f"完成: {success}/{total} 条已结构化")


if __name__ == "__main__":
    asyncio.run(main())

