"""验证 Agent 能准确翻译每个页面的信息"""
import asyncio
import re
import os

os.environ['PYTHONPATH'] = '.'
from src.adapters.llm_client import get_llm

# 各页面关键内容样本
PAGE_SAMPLES = {
    "index.html (首页)": [
        "让你的AI助手来跟全世界对接需求——你的AI助手帮你把需求传达出去，又帮你接收别人发给你的需求。",
        "此需求链平台是地球人类共有的基础设施，永久开源，中立，免费。",
        "不需要技术背景——你只需要一个AI助手，剩下的它帮你搞定。",
    ],
    "login.html (注册登录)": [
        "登录后填写基本信息，然后让你的Agent帮你做复杂的事",
        "忘记密码？",
        "密码已重置，请用新密码登录",
    ],
    "demand_square.html (需求广场)": [
        "全球需求广场 — 看看世界在寻找什么解决方案",
        "学科筛选",
        "预算区间",
    ],
    "forum.html (论坛)": [
        "需求板 — 发布你的技术需求",
        "能力展示 — 告诉世界你能做什么",
        "匹配反馈 — 分享你的匹配体验",
    ],
    "chat.html (聊天)": [
        "协作工作区聊天已就绪。你可以直接和对方人类对话。",
        "输入消息...",
        "对方在线",
        "对方正在输入...",
    ],
    "zones.html (专区)": [
        "人工智能专区",
        "传感器专区",
        "新材料专区",
    ],
    "timeline.html (个人动态)": [
        "我的动态",
        "需求状态变更",
        "新匹配通知",
    ],
    "leaderboard.html (排行榜)": [
        "供给方信誉排行榜",
        "完成项目数",
        "响应速度",
    ],
    "global_search.html (全局搜索)": [
        "搜索需求、能力、供应商、论坛...",
        "搜索结果",
        "未找到相关结果",
    ],
    "targeted_demand.html (定向需求)": [
        "定向需求 — 针对特定产品提交改进建议",
        "产品名称",
        "改进建议",
        "提交需求",
    ],
    "discovered_demands.html (公开需求)": [
        "公开需求发现 — 从全球公开渠道自动发现需求",
        "全部来源",
        "转为正式需求",
    ],
    "public_demand.html (公开页面)": [
        "有人需要你的能力",
        "需求链平台自动发现你的团队可能与这条需求匹配",
        "不需要注册就能看到需求内容",
        "免费注册，让Agent对接",
    ],
}

async def verify_translation(text: str, lang: str = "en") -> str:
    """测试 LLM 能否准确翻译一段文本"""
    llm = get_llm()
    prompt = f"Translate this user interface text to English. Keep it natural and concise. Output ONLY the translation, no explanations.\n\n{text}"
    return await llm.chat(prompt, "")


async def main():
    llm = get_llm()
    total = 0
    errors = 0

    for page, samples in PAGE_SAMPLES.items():
        print(f"\n{'='*50}")
        print(f"  {page} ({len(samples)} samples)")
        print(f"{'='*50}")

        for zh_text in samples:
            total += 1
            try:
                en = await llm.chat(
                    "Translate this UI text to English. Keep it natural and concise. Output ONLY the translation, no explanations.",
                    zh_text
                )
                en = en.strip().strip('"').strip("'")
                print(f"  ZH: {zh_text[:60]}")
                print(f"  EN: {en[:80]}")
                print()
            except Exception as e:
                print(f"  ERR: {e}")
                errors += 1

    print(f"\n{'='*50}")
    print(f"Result: {total-errors}/{total} translations succeeded")
    if errors > 0:
        print(f"  {errors} errors")
    print(f"{'='*50}")


if __name__ == "__main__":
    asyncio.run(main())
