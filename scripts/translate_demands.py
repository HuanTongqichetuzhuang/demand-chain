"""翻译英文需求为中文 — 使用 DeepSeek API"""
import asyncio, sys
sys.path.insert(0, '/app')
from src.shared.database import async_session
from src.shared.models import Demand
from sqlalchemy import select
from src.adapters.llm_client import get_llm

def is_english(text):
    if not text or len(text.strip()) < 20:
        return False
    cjk = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    total = max(len(text.strip()), 1)
    return (cjk / total) < 0.1

TRANSLATE_PROMPT = """你是一个专业的技术文档翻译。将以下英文技术需求/公告翻译为中文。

要求：
- 专业术语保留英文原文（如 GPU、API、Python、NASA、DARPA、NIH）
- 机构名称首次出现时括号保留英文缩写
- 保持技术准确性和正式语气
- 只输出翻译结果，不要加任何说明
- 金额数字格式保持原样（如 $250,000）

原文："""

async def main():
    async with async_session() as s:
        r = await s.execute(select(Demand).where(Demand.user_id == 'crawler'))
        demands = list(r.scalars().all())
    
    english = [d for d in demands if is_english(d.raw_text)]
    print(f"待翻译: {len(english)} 条\n")
    
    llm = get_llm()
    
    for i, d in enumerate(english, 1):
        text_to_translate = d.raw_text[:800]
        print(f"[{i}/{len(english)}] {d.id[:8]}...", end=" ")
        sys.stdout.flush()
        
        try:
            result = await llm.chat(TRANSLATE_PROMPT, text_to_translate)
            result = result.strip().strip('"\'')
            
            if result and len(result) > 10:
                async with async_session() as s2:
                    d2 = await s2.get(Demand, d.id)
                    if d2:
                        d2.raw_text = result[:1000]
                        await s2.commit()
                print(f"✅ {result[:50]}...")
            else:
                print(f"❌ 翻译结果太短: {result}")
        except Exception as e:
            print(f"❌ {e}")

asyncio.run(main())
