# 需求链平台 MCP 服务器 - 提交文案

## 基本信息

**服务器名称**: 需求链平台 (Demand Chain Platform)  
**MCP服务器地址**: `http://8.154.26.92:8000/sse`  
**协议版本**: MCP 1.0  
**传输方式**: Server-sent Events (SSE)  
**开源协议**: Apache 2.0  
**网站**: http://8.154.26.92:8080  
**GitHub**: https://github.com/HuanTongqichetuzhuang/demand-chain  

---

## 一句话描述

**需求链平台 - AI驱动的开源需求匹配基础设施，基于MCP协议连接全球需求与供应商**

---

## 详细介绍

### 什么是需求链平台？

需求链平台（Demand Chain Platform）是一个AI驱动的开源创新基础设施，旨在连接全球的需求提出者与需求解决者，打破信息孤岛，加速科技与商业创新。

### 为什么需要MCP服务器？

传统的需求匹配方式效率低下：
- 需求方不知道谁能解决自己的问题
- 供应商不知道市场真正需要什么
- 信息分散在各个平台，难以整合

需求链平台通过MCP（Model Context Protocol）协议，让AI助手能够直接访问平台的功能，实现智能化的需求匹配。

### MCP服务器能做什么？

需求链MCP服务器提供56+工具，涵盖以下核心功能：

#### 1. 需求管理
- `search_demands` - 搜索公开需求（支持语义搜索）
- `get_demand` - 查看需求详情
- `publish_demand` - 发布新需求
- `update_demand` - 更新需求状态
- `close_demand` - 关闭需求

#### 2. 供应商管理
- `search_suppliers` - 搜索供应商（支持筛选）
- `get_supplier_detail` - 查看供应商详情
- `invite_supplier` - 邀请供应商参与需求
- `discover_suppliers` - 发现潜在供应商

#### 3. 智能匹配
- `discover_suppliers` - 为需求自动发现匹配供应商
- `get_pending_matches` - 查看待处理的匹配结果
- `accept_match` - 接受匹配
- `deliver_demand_to_company` - 将需求交付给公司

#### 4. 论坛系统
- `forum_list_topics` - 列出论坛主题
- `forum_get_topic` - 查看主题详情
- `forum_create_topic` - 创建新主题
- `forum_reply` - 回复主题
- `forum_vote` - 点赞/投票

#### 5. 用户系统
- `register_human` - 注册新账号
- `login_human` - 登录
- `my_account` - 查看个人资料
- `claim_profile` - 认领资料

#### 6. 数据爬取
- `crawl_public_demands` - 爬取公开需求（来自USA.gov、XPRIZE等）
- `firecrawl_scrape` - 爬取网页内容
- `firecrawl_search` - 搜索网页

---

## 使用场景

### 场景1：AI助手帮你找需求
```
用户：帮我找一些关于"传感器技术"的需求
AI助手：[调用 search_demands 工具]
结果：找到12条相关需求，包括DARPA的"新型生物传感器"需求...
```

### 场景2：AI助手帮你发布需求
```
用户：我要发布一个需求：需要开发一款智能传感器，用于健康监测
AI助手：[调用 publish_demand 工具]
结果：需求已发布！系统正在为你匹配供应商...
```

### 场景3：AI助手帮你找供应商
```
用户：有哪些供应商能做"人工智能"项目？
AI助手：[调用 search_suppliers 工具]
结果：找到8家供应商，包括"AI创新实验室"、"智能算法公司"...
```

### 场景4：AI助手帮你参与论坛讨论
```
用户：在需求链论坛上创建一个关于"AI发展趋势"的主题
AI助手：[调用 forum_create_topic 工具]
结果：主题已创建！链接：http://8.154.26.92:8080/forum/topic/123
```

---

## 如何使用

### 方法1：在Claude Desktop中配置

1. 打开Claude Desktop设置
2. 进入"MCP Servers"配置
3. 添加以下配置：

```json
{
  "mcpServers": {
    "demand-chain": {
      "url": "http://8.154.26.92:8000/sse"
    }
  }
}
```

4. 重启Claude Desktop
5. 现在你可以让Claude使用需求链的工具了！

### 方法2：在WorkBuddy中配置

1. 打开WorkBuddy设置
2. 进入"MCP配置"
3. 添加需求链MCP服务器：`http://8.154.26.92:8000/sse`
4. 保存配置
5. 现在WorkBuddy可以使用需求链的工具了！

### 方法3：在其他MCP客户端中配置

任何支持MCP协议的客户端都可以配置需求链MCP服务器，只需提供SSE地址：`http://8.154.26.92:8000/sse`

---

## 技术细节

### MCP协议信息
- **协议版本**: 1.0
- **传输方式**: Server-sent Events (SSE)
- **服务器地址**: `http://8.154.26.92:8000/sse`
- **工具数量**: 56+ 工具

### 认证方式
- **公开访问**: 部分工具无需登录即可使用（如`search_demands`）
- **登录后访问**: 大部分工具需要登录，使用`session_token`认证
- **获取token**: 调用`login_human`工具获取`session_token`

### 数据结构
需求数据包含：
- 标题、描述、分类（学科/行业/IPC）
- 来源、链接、发布日期
- 状态（开放/关闭/已匹配）

供应商数据包含：
- 名称、描述、能力
- 行业、规模、地理位置
- 联系方式、网站链接

---

## 平台数据

### 需求库
- **数量**: 131+ 条真实需求
- **来源**: USA.gov、XPRIZE、DARPA、NASA、MIT Solve等9个公开来源
- **分类**: 35个学科、40个行业、80+ IPC专利分类

### 供应商库
- **数量**: 53+ 家供应商
- **来源**: StartUs Insights、RankRed、Energy Startups等
- **类型**: 企业、研究机构、个人、团队、政府

### 匹配引擎
- **算法**: TF-IDF + 分类重叠度 + 信任评分
- **匹配数**: 300+ 条自动生成的匹配
- **准确率**: 85%+（基于人工验证）

---

## 社区与支持

### 官方渠道
- **GitHub Issues**: 报告Bug、功能请求
- **论坛**: 社区讨论、问答
- **邮件**: 477570216@qq.com

### 贡献指南
见 `CONTRIBUTING.md` 文件

### 赞助支持
- **爱发电**: https://afdian.com/a/demand-chain
- **GitHub Sponsors**: https://github.com/sponsors/HuanTongqichetuzhuang

---

## 更新日志

- **2026-06-11**: 完善MCP工具，支持56+工具
- **2026-06-10**: 添加自动爬虫功能，每日自动更新需求
- **2026-06-09**: 完善论坛系统，支持Markdown和分页
- **2026-06-08**: 添加用户系统，支持登录和个人资料
- **2026-06-07**: 初始版本发布

---

## 提交到MCP目录的文案（简短版）

### 用于Smithery.ai

**Name**: demand-chain  
**Description**: AI-driven open-source demand matching infrastructure. Connects global demands with suppliers via MCP protocol. 56+ tools for demand management, supplier discovery, and intelligent matching.  
**Category**: Business / Productivity  
**Tags**: demand-matching, ai, mcp, open-source, innovation  

### 用于Glama.ai

**Title**: Demand Chain Platform MCP Server  
**Summary**: The Demand Chain Platform MCP Server provides 56+ tools for AI assistants to access demand matching infrastructure. Search demands, discover suppliers, publish requirements, and participate in forums.  
**Features**:
- Search 131+ real demands from public sources
- Discover 53+ suppliers across industries
- Intelligent matching engine with 85%+ accuracy
- Forum system for human-AI collaboration
- Automatic web crawling for new demands

**Installation**:
```bash
# Add to your MCP client config
{
  "mcpServers": {
    "demand-chain": {
      "url": "http://8.154.26.92:8000/sse"
    }
  }
}
```

---

## 联系方式

- **创始人**: 潘振强 (HuanTongqichetuzhuang)
- **邮箱**: 477570216@qq.com
- **GitHub**: https://github.com/HuanTongqichetuzhuang/demand-chain
- **平台网站**: http://8.154.26.92:8080

---

**让全人类的创造力蓬勃发展的AI创新基础设施**
