"""
微信公众号接入端点 — 让人类通过微信直接使用需求链平台。
运行在 0.0.0.0:9000，独立于 MCP Server（8000端口）。

微信后台配置：
  URL: http://demand-chain.duckdns.org:9000/wechat
  Token: 你自己生成一个字符串
  EncodingAESKey: 微信自动生成
"""
import hashlib
import json
import logging
import os
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Optional

import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import Response, PlainTextResponse
from starlette.routing import Route

# ============================================================
# 配置 — 从环境变量读取
# ============================================================
WECHAT_TOKEN = os.environ.get("WECHAT_TOKEN", "demandchain2026")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("wechat_bot")


# ============================================================
# 微信签名验证
# ============================================================

def verify_signature(token: str, timestamp: str, nonce: str, signature: str) -> bool:
    """验证微信服务器发来的签名"""
    arr = sorted([token, timestamp, nonce])
    return hashlib.sha1("".join(arr).encode()).hexdigest() == signature


# ============================================================
# 消息处理 — 用 LLM 理解用户意图，调用平台内部服务
# ============================================================

async def process_message(msg_type: str, content: str, from_user: str) -> str:
    """
    处理用户消息，返回回复文本。
    用 LLM 理解意图，调用平台内部服务。
    """
    # 先检查是否是简单命令
    content = content.strip()

    # 提取关键词并匹配
    from src.shared.database import async_session
    from src.demand.service import DemandService

    try:
        if "搜索" in content or "找" in content or "有" in content:
            # 提取关键词 — 简单的关键词提取
            for prefix in ["搜索", "找", "有没有"]:
                content = content.replace(prefix, "", 1)

            async with async_session() as session:
                svc = DemandService(session)
                demands = await svc.search(keyword=content, limit=5)
                if demands:
                    lines = [f"找到 {len(demands)} 条相关需求："]
                    for d in demands[:5]:
                        txt = (d.structured_json or {}).get("requirement", {}).get("core_need", "") or d.raw_text[:60]
                        lines.append(f"  - {txt}")
                    return "\n".join(lines)
                else:
                    return f"没找到与「{content}」相关的需求。试试换个关键词？"

        elif "发" in content and ("需求" in content or "求" in content):
            return "发布需求需要先注册账号。打开 AI 助手（如 Claude），配置 MCP 地址 http://demand-chain.duckdns.org:8000/sse，让 AI 帮你完成注册和发布。"

        elif "你好" in content or "hello" in content.lower():
            return (
                "你好！我是需求链平台的微信助手。\n\n"
                "你可以：\n"
                "  1. 搜索需求 — 说「搜索XXX」\n"
                "  2. 查看平台 — 说「有什么需求」\n"
                "  3. 了解平台 — 说「是什么」\n\n"
                "深度使用请配置 AI 助手（Claude 等）连接 MCP 地址：\n"
                "  http://demand-chain.duckdns.org:8000/sse"
            )

        elif "是什么" in content or "介绍" in content:
            return (
                "需求链平台是一个 AI 原生的创新匹配网络。\n"
                "简单说：你的 AI 助手帮你把需求和全世界对接。\n\n"
                "开源 · 中立 · 永久免费\n"
                "GitHub: github.com/HuanTongqichetuzhuang/demand-chain"
            )

        else:
            # 用 LLM 理解意图
            from src.adapters.llm_client import get_llm
            try:
                llm = get_llm()
                reply = await llm.chat(
                    "判断用户想做什么，用中文简短回复（50字以内）：\n"
                    "如果是想发布需求，告诉他：打开AI助手配置MCP地址\n"
                    "如果是提问，直接回答。如果是闲聊，回复友好的问候",
                    content,
                )
                return reply[:200]
            except Exception:
                return f"收到你的消息了。深度使用请配置 AI 助手连接 MCP 地址：http://demand-chain.duckdns.org:8000/sse"

    except Exception as e:
        logger.error(f"处理消息失败: {e}")
        return "暂时无法处理，请稍后再试。"


# ============================================================
# 微信路由处理
# ============================================================

async def wechat_verify(request: Request):
    """微信服务器验证（GET请求）"""
    params = dict(request.query_params)
    signature = params.get("signature", "")
    timestamp = params.get("timestamp", "")
    nonce = params.get("nonce", "")
    echostr = params.get("echostr", "")

    logger.info(f"WeChat verify: timestamp={timestamp}, nonce={nonce}")

    if verify_signature(WECHAT_TOKEN, timestamp, nonce, signature):
        return PlainTextResponse(echostr)
    else:
        return PlainTextResponse("verification failed", status_code=403)


async def wechat_message(request: Request):
    """处理微信消息（POST请求）"""
    body = await request.body()
    xml_data = body.decode("utf-8")
    logger.info(f"WeChat message received: {xml_data[:200]}")

    try:
        root = ET.fromstring(xml_data)
        msg_type = root.findtext("MsgType", "")
        content = root.findtext("Content", "")
        from_user = root.findtext("FromUserName", "")
        to_user = root.findtext("ToUserName", "")

        if msg_type == "text":
            reply_text = await process_message(msg_type, content, from_user)
        elif msg_type == "event":
            event = root.findtext("Event", "")
            if event == "subscribe":
                reply_text = "感谢关注需求链平台！你的 AI 助手已经准备好帮你对接全球需求。"
            else:
                reply_text = "收到事件"
        else:
            reply_text = f"暂不支持 {msg_type} 类型消息"

        # 构造 XML 回复
        timestamp = str(int(time.time()))
        reply_xml = f"""<xml>
<ToUserName><![CDATA[{from_user}]]></ToUserName>
<FromUserName><![CDATA[{to_user}]]></FromUserName>
<CreateTime>{timestamp}</CreateTime>
<MsgType><![CDATA[text]]></MsgType>
<Content><![CDATA[{reply_text}]]></Content>
</xml>"""
        return Response(content=reply_xml, media_type="application/xml")

    except Exception as e:
        logger.error(f"处理微信消息异常: {e}")
        return Response(content="success", media_type="text/plain")


# ============================================================
# 健康检查
# ============================================================

async def health(request):
    return Response(
        json.dumps({"status": "ok", "service": "wechat-bot"}),
        media_type="application/json"
    )


# ============================================================
# 启动
# ============================================================

routes = [
    Route("/wechat", wechat_verify, methods=["GET"]),
    Route("/wechat", wechat_message, methods=["POST"]),
    Route("/health", health, methods=["GET"]),
    Route("/", health, methods=["GET"]),
]

app = Starlette(routes=routes)


def run():
    logger.info("微信 Bot 启动中 (0.0.0.0:9000)...")
    uvicorn.run(app, host="0.0.0.0", port=9000, log_level="info")


if __name__ == "__main__":
    run()


