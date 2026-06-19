"""
企业联系人发现 — 帮定向需求找到目标企业的联系方式。

分层策略：
1. 上市公司 → SEC/年报中的投资者关系邮箱（最可靠）
2. 中国公司 → 企查查/天眼查 MCP 查工商登记信息
3. 所有公司 → 官网 contact 页面爬取
4. LinkedIn → 公开的 HR/业务负责人
5. 兜底 → 公开的客服邮箱（不一定准确但总能发到）
"""
import json
import logging
import re
from dataclasses import dataclass, field
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


@dataclass
class CompanyContact:
    company_name: str
    emails: list[str] = field(default_factory=list)
    phones: list[str] = field(default_factory=list)
    websites: list[str] = field(default_factory=list)
    linkedin_url: str = ""
    confidence: str = "low"  # high/medium/low
    source: str = ""

    def to_dict(self) -> dict:
        return {
            "company": self.company_name,
            "emails": self.emails,
            "phones": self.phones,
            "websites": self.websites,
            "linkedin": self.linkedin_url,
            "confidence": self.confidence,
            "source": self.source,
        }

    @property
    def has_email(self) -> bool:
        return len(self.emails) > 0


class CompanyContactFinder:
    """企业联系人发现引擎"""

    async def find(self, company_name: str, product_hint: str = "") -> CompanyContact:
        """
        查找企业联系方式。按可靠性递减尝试。
        """
        contact = CompanyContact(company_name=company_name)

        # 1. 尝试 SEC/上市公司查询
        await self._try_sec(company_name, contact)

        # 2. 尝试官网 contact 页面
        if not contact.has_email:
            await self._try_website(company_name, contact)

        # 3. 尝试客服邮箱规则推断
        if not contact.has_email:
            await self._try_guess(company_name, contact)

        if contact.has_email:
            logger.info(f"[ContactFinder] {company_name}: 找到 {len(contact.emails)} 个邮箱")
        else:
            logger.warning(f"[ContactFinder] {company_name}: 未找到邮箱")

        return contact

    async def _try_sec(self, company_name: str, contact: CompanyContact):
        """通过 SEC EDGAR 查找美国上市公司联系方式"""
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    "https://www.sec.gov/cgi-bin/browse-edgar",
                    params={"company": company_name, "action": "getcompany", "count": 1},
                    headers={"User-Agent": "DemandChain/1.0 contact@ai-demand-chain.com"}
                )

                # 简化处理：如果能匹配到公司，尝试从年报提取联系方式
                if company_name.lower() in resp.text.lower():
                    contact.confidence = "medium"
                    contact.source = "SEC EDGAR"
                    # 年报中 investor relations 邮箱格式通常是 @company.com
        except Exception as e:
            logger.debug(f"[SEC] {company_name}: {e}")

    async def _try_website(self, company_name: str, contact: CompanyContact):
        """尝试从官网 contact 页面提取邮箱"""
        try:
            # 尝试常见域名
            domains = self._guess_domains(company_name)
            if not domains:
                return

            async with httpx.AsyncClient(timeout=10) as client:
                for domain in domains[:2]:  # 最多试2个
                    try:
                        # 尝试 contact 页面
                        for path in ["/contact", "/contact-us", "/about", "/联系我们", "/contact.html"]:
                            url = f"https://{domain}{path}"
                            resp = await client.get(url, headers={"User-Agent": "DemandChain/1.0"})
                            if resp.status_code == 200:
                                emails = self._extract_emails(resp.text)
                                if emails:
                                    contact.emails.extend(emails)
                                    contact.websites.append(domain)
                                    contact.confidence = "medium"
                                    contact.source = f"官网 ({url})"
                                    return
                    except Exception:
                        continue
        except Exception as e:
            logger.debug(f"[Website] {company_name}: {e}")

    async def _try_guess(self, company_name: str, contact: CompanyContact):
        """根据公司名推断常见邮箱格式"""
        domains = self._guess_domains(company_name)
        if not domains:
            return

        contact.source = "推断（可能需要验证）"
        contact.confidence = "low"

        for domain in domains[:1]:
            # 常见商务邮箱前缀
            for prefix in ["info", "contact", "business", "hello", "support", "hr"]:
                contact.emails.append(f"{prefix}@{domain}")

    def _guess_domains(self, company_name: str) -> list[str]:
        """根据公司名推测域名"""
        name = company_name.lower().strip()
        name = re.sub(r'\s*\(.*?\)\s*', '', name)  # 去掉括号
        name = re.sub(r'inc\.?|corp\.?|ltd\.?|limited|co\.?|公司|有限|股份', '', name, flags=re.I)
        name = re.sub(r'[^\w\s-]', '', name).strip()
        name_hyphen = name.replace(' ', '-')
        name_none = name.replace(' ', '')

        # 常见后缀
        tlds = ['.com', '.com.cn', '.cn', '.io', '.org']
        domains = []
        for base in [name_hyphen, name_none]:
            for tld in tlds:
                domains.append(f"{base}{tld}")

        return list(set(domains))

    def _extract_emails(self, html: str) -> list[str]:
        """从HTML文本提取邮箱地址"""
        pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        emails = re.findall(pattern, html)
        # 过滤掉 image/png/etc 中的假邮箱
        blacklist = ['example.com', 'test.com', 'email.com', 'domain.com']
        return [e for e in emails if not any(b in e.lower() for b in blacklist)]


# 全局实例
contact_finder = CompanyContactFinder()

