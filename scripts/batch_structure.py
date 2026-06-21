"""
需求数据的一次性快速结构化 — 对全部 raw_text 不为空的 OPEN 需求直接通过 DeepSeek 做一次性提取摘要+分类+标签。
通过 cursor 分批处理，每批20条，批次间间隔10s。总计约需5-10分钟。
"""
import asyncio
import json
import sys
import os
import traceback
from uuid import uuid4

sys.path.insert(0, "/app")

from src.shared.database import async_session
from src.shared.models import Demand
from src.adapters.llm_client import get_llm
from sqlalchemy import select, text

BATCH = 20
DELAY = 10  # seconds between batches

PROMPT = """分析以下需求描述，输出JSON（只输出JSON，无其他文字）：
{
  "summary": "中文一句话摘要，不超过80字",
  "application_field": "传感器/材料/新能源/AI/生物医药/航空航天/制造/环境/交通/其他 中选一个",
  "tags": ["标签1","标签2","标签3"],
  "urgency": "标准/紧急/远期",
  "budget_hint": "预算信息或填未知"
}
英文需求请翻译成中文摘要输出。"""

llm = get_llm()


async def structure_one(raw_text: str) -> dict:
    try:
        resp = await llm.chat(PROMPT, raw_text[:3000])
        text = resp.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
        # find JSON
        b = text.find("{")
        e = text.rfind("}")
        if b >= 0 and e > b:
            text = text[b:e + 1]
        return json.loads(text)
    except Exception:
        # fallback: minimal
        return {
            "summary": raw_text[:80],
            "application_field": "其他",
            "tags": [],
            "urgency": "标准",
            "budget_hint": "未知",
        }


async def main():
    async with async_session() as session:
        # Get total count
        total_row = await session.execute(
            text("SELECT count(*) FROM demands WHERE raw_text IS NOT NULL AND (structured_json IS NULL)")
        )
        total = total_row.scalar()
        print(f"待处理: {total} 条")

        # Get all IDs
        rows = await session.execute(
            text("SELECT id, raw_text FROM demands WHERE raw_text IS NOT NULL AND (structured_json IS NULL) ORDER BY created_at")
        )
        all_rows = list(rows.fetchall())
        print(f"实际获取: {len(all_rows)} 条")

    success = 0
    for i, (did, raw) in enumerate(all_rows):
        if not raw or len(raw.strip()) < 10:
            continue

        structured = await structure_one(raw)
        new_cat = structured.get("application_field", "其他")

        try:
            async with async_session() as s2:
                await s2.execute(
                    text("UPDATE demands SET structured_json = :sj, category = :cat WHERE id = :id"),
                    {"sj": json.dumps(structured, ensure_ascii=False), "cat": new_cat, "id": did}
                )
                await s2.commit()
                success += 1
                if (i + 1) % 10 == 0:
                    print(f"[{i + 1}/{len(all_rows)}] {raw[:50]}... -> {new_cat} {structured.get('tags', [])}")
        except Exception as e:
            print(f"DB write error: {e}")

        # Rate limit
        if (i + 1) % BATCH == 0 and i < len(all_rows) - 1:
            print(f"批次 {(i + 1) // BATCH} 完成, 等待 {DELAY}s...")
            await asyncio.sleep(DELAY)

    print(f"\n完成: {success}/{len(all_rows)} 条结构化")


if __name__ == "__main__":
    asyncio.run(main())

