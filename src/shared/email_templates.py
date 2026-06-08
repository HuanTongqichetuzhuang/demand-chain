"""
邮件模板生成 — 需求方用自己的邮箱发给供给方。

不用平台发邮件——生成一封包含需求内容+平台推广的邮件模板，
需求方复制后用自己的邮箱发给供给方。更可信、不会被拦截、免费。
"""
import json
import logging

logger = logging.getLogger(__name__)

TEMPLATE_ZH = """主题：关于「{demand_title}」的合作可能 —— 来自需求链平台

{company_name} 你好：

我是{demand_name}，在需求链平台（ai-demand-chain.com）上发布了一条需求。

【需求简介】
{demand_body}

【为什么找到你们】
{match_reason}

【关于需求链平台】
需求链是一个开源的、AI Agent 原生的需求匹配基础设施。注册后你的 AI 助手可以：
- 自动接收来自全球的需求匹配
- 与需求方 Agent 直接沟通（不需要交换微信/邮箱）
- 将需求拆分、延伸，形成完整的需求链

你的 AI 助手接入只需一步：将以下 MCP 地址复制给你的 AI 助手：
{base_url}/sse

如果你感兴趣，可以让你的 AI 助手接入平台查看完整需求，或者直接回复此邮件与我沟通。

如果我发错了，抱歉打扰。
此致

{demand_name}
"""

TEMPLATE_EN = """Subject: Potential Collaboration on "{demand_title}" — via Demand Chain Platform

Hi {company_name},

I'm {demand_name}, posting this demand on the Demand Chain platform (ai-demand-chain.com).

[The Need]
{demand_body}

[Why I'm Reaching Out to You]
{match_reason}

[About Demand Chain]
Demand Chain is an open-source, AI Agent-native demand matching infrastructure.
Once registered, your AI assistant can:
- Automatically receive global demand matches
- Communicate directly with demand-side agents (no WeChat/email exchange needed)
- Split and extend demands into full demand chains

Your AI assistant connects in one step — give it this MCP address:
{base_url}/sse

If you're interested, let your AI assistant join the platform to see the full demand, or reply to this email.

Apologies if this reached the wrong person.
Best,

{demand_name}
"""


class OutreachEmailGenerator:
    """生成供需求方自己发送的邮件模板"""

    def __init__(self, base_url: str = "http://8.154.26.92:8000"):
        self.base_url = base_url

    def generate(
        self,
        demand_title: str,
        demand_body: str,
        match_reason: str,
        company_name: str,
        demand_name: str = "",
        lang: str = "zh",
    ) -> dict:
        """
        生成邮件模板。

        返回:
        {
            "subject": "邮件主题",
            "body": "邮件正文（直接复制到邮件客户端即可）",
            "to": "建议的收件人",
            "cc": "抄送（可选）",
            "copy_text": "一键复制的完整文本（含主题+正文）",
        }
        """
        if lang.startswith("en"):
            template = TEMPLATE_EN
        else:
            template = TEMPLATE_ZH

        body = template.format(
            demand_title=demand_title,
            demand_body=demand_body,
            match_reason=match_reason,
            company_name=company_name,
            demand_name=demand_name or "需求方",
            base_url=self.base_url,
        )

        # 提取主题行（第一行）
        lines = body.strip().split("\n")
        subject = ""
        if lines[0].startswith("主题："):
            subject = lines[0].replace("主题：", "").strip()
        elif lines[0].startswith("Subject: "):
            subject = lines[0].replace("Subject: ", "").strip()

        # 完整复制文本（含主题）
        copy_text = body.strip()

        logger.info(f"[EmailGen] 生成邮件模板: {subject[:40]}...")

        return {
            "subject": subject,
            "body": body,
            "copy_text": copy_text,
            "mcp_link": f"{self.base_url}/sse",
            "platform_link": self.base_url.replace(":8000", ""),
        }


# 全局实例
email_generator = OutreachEmailGenerator()
