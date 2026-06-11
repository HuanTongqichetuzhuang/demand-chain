# 需求链平台 · Demand Chain Platform

> AI 驱动的开放式创新基础设施 — 连接全球需求与供应商  
> 🌐 [https://8.154.26.92:8080](https://8.154.26.92:8080)

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Status](https://img.shields.io/badge/status-active-green.svg)](https://8.154.26.92:8080)
[![Stars](https://img.shields.io/github/stars/HuanTongqichetuzhuang/demand-chain?style=social)](https://github.com/HuanTongqichetuzhuang/demand-chain)

---

## 平台现状

| 模块 | 状态 | 说明 |
|------|:--:|------|
| **需求库** | ✅ | 131 条真实需求（来自 USA.gov、XPRIZE、DARPA、NASA、MIT Solve 等 9 个公开来源） |
| **供应商库** | ✅ | 53 家供应商（StartUs Insights、RankRed、Energy Startups 等） |
| **匹配引擎** | ✅ | TF-IDF + 分类重叠度 + 信任评分，自动生成 300+ 条匹配 |
| **语义搜索** | ✅ | 中英文混合分词，TF-IDF 余弦相似度排序 |
| **论坛系统** | ✅ | 发帖/回复/点赞/置顶/Markdown 渲染/分页 |
| **用户系统** | ✅ | 注册/登录/个人资料/头像/密码修改/通知设置 |
| **MCP Server** | ✅ | 56+ 工具，Agent 直接接入 |
| **Web 页面** | ✅ | 首页/需求广场/供应商/论坛/登录/个人主页/API 文档/教程 |
| **自动爬虫** | ✅ | 每日 06:00 自动执行，9 个需求源 + 3 个供应商源 |
| **国际化** | 🚧 | 中英文切换（部分页面） |

## 核心问题

消费者、企业、科研机构乃至政府部门每天产生大量未被满足的需求，但缺乏有效的传递渠道。需求方不知道谁能解决，供应商不知道市场真正需要什么。

## 解决方案

**AI 自动匹配供需：**
1. 用户用自然语言发布需求，AI 自动分类到 35 个学科、40 个行业、80+ IPC 专利分类
2. 匹配引擎自动搜索供应商库，计算匹配分数
3. 通过邮件通知用户匹配结果
4. 支持 A2A 协议（Google 开源的 Agent 间通信标准）让 AI Agent 代表用户沟通

## 技术栈

- **后端**: Python 3.12 / Starlette / Uvicorn / SQLAlchemy (async)
- **数据库**: PostgreSQL 16 + pgvector (向量搜索就绪)
- **AI**: DeepSeek API (分类 + 结构化)
- **搜索**: TF-IDF 语义搜索 (中文 bigram 分词)
- **协议**: MCP (Model Context Protocol) / A2A
- **部署**: Docker Compose / 阿里云 ECS

## 快速开始

```bash
git clone https://github.com/HuanTongqichetuzhuang/demand-chain.git
cd demand-chain

# 本地开发
python -m src.server        # MCP Server → port 8000
python -m src.web_server     # Web Server → port 80

# Docker 部署
docker compose -f docker-compose.prod.yml -p dc up -d
```

浏览器访问 `http://localhost:8080`。

## AI 助手接入

将 MCP 地址配置给你的 AI 助手（Claude Desktop / 龙虾助手 / 通义千问）：

```
http://8.154.26.92:8000/sse
```

你的 AI 助手即可使用 56+ 工具，代表你发布需求、搜索供应商、查看匹配结果。

## 项目结构

```
├── index.html              # 首页（实时数据流）
├── demand_square.html      # 需求广场（语义搜索 + 分类）
├── suppliers.html          # 供应商页面（搜索 + 筛选）
├── forum.html              # 论坛（Markdown + 分页）
├── login.html              # 注册/登录
├── profile.html            # 个人主页（资料/匹配/通知设置）
├── shared.css              # 共享样式（nav/footer/card/btn/skeleton）
├── nav.js / i18n.js        # 导航栏 / 国际化
├── forum.js                # 论坛逻辑
├── scripts/
│   ├── auto_crawler.py     # 自动爬虫（9需求源+3供应商源）
│   ├── structure_demands.py # 批量结构化
│   ├── batch_structure.py  # 快速结构化
│   └── seed_forum.py       # 论坛种子数据
└── src/
    ├── server.py           # MCP Server (56+ tools)
    ├── web_server.py       # Web + REST API
    ├── matching/engine.py  # 匹配引擎
    ├── forum/service.py    # 论坛服务
    ├── demand/service.py   # 需求服务
    ├── shared/
    │   ├── semantic_search.py  # TF-IDF 搜索引擎
    │   ├── classification.py   # 多维度分类
    │   └── models.py           # 数据库模型
    └── adapters/
        └── llm_client.py       # DeepSeek 客户端
```

## 赞助支持

- [爱发电](https://afdian.com/a/demand-chain)
- [GitHub Sponsors](https://github.com/sponsors/HuanTongqichetuzhuang)

## License

Apache 2.0 · 永久开源 · 中立 · 免费
