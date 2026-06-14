# 需求链平台 · Demand Chain Platform

> AI 驱动的开放式创新基础设施 — 连接全球需求与供应商
> 纯 Python/HTML 项目，部署于阿里云 ECS Docker

## Project
- **技术栈**: Python 3.12 + Starlette/FastAPI + SQLAlchemy(async) + PostgreSQL 16 + pgvector
- **前端**: 纯 HTML + JS（无框架），多页面 SPA 风格，中英文 i18n
- **入口**: `src/server.py` (MCP Server :8000) / `src/web_server.py` (Web Server :8080)
- **仓库**: `github.com/HuanTongqichetuzhuang/demand-chain` (master)
- **服务器**: `ssh -p 2222 root@8.154.26.92` → Docker 容器部署

## Commands
| 命令 | 说明 |
|------|------|
| `.venv/Scripts/python -m src.server` | 启动 MCP Server (8000) |
| `.venv/Scripts/python -m src.web_server` | 启动 Web Server (8080) |
| `python scripts/auto_crawler.py` | 运行爬虫 |
| `docker build -t demand-chain:slim .` | 本地构建镜像 |
| `docker save demand-chain:slim -o E:/temp/dc-slim.tar` | 导出镜像 |
| `scp -P 2222 ... root@8.154.26.92:/opt/dc-slim.tar` | 上传到服务器 |
| `docker compose -f docker-compose.prod.yml -p dc up -d --force-recreate web` | 服务器部署 |
| `.venv/Scripts/pytest` | 运行测试 |
| `git config --local http.proxy http://127.0.0.1:7897` | Git 代理（用完即删） |

## Architecture
- **`src/server.py`** — MCP Server，56+ 工具，供 AI Agent 通过 SSE 接入
- **`src/web_server.py`** — Web Server + REST API（FastAPI路由）
- **`src/matching/engine.py`** — 匹配引擎（TF-IDF + 分类重叠度 + 信任评分）
- **`src/shared/`** — 核心共享模块：models(数据模型)、database(异步连接)、auth(认证)、semantic_search(TF-IDF搜索)、classification(分类)、task_manager(异步任务)、notifications(通知)、i18n(国际化)
- **`src/demand/service.py`** — 需求服务
- **`src/forum/service.py`** — 论坛服务
- **`src/adapters/llm_client.py`** — DeepSeek API 客户端
- **`src/discovery/`** — 供应商发现引擎 + 爬虫
- **`scripts/`** — 自动爬虫、数据导入、分类、种子数据脚本
- **前端页面**: index.html, demand_square.html, suppliers.html, forum.html, login.html, profile.html, api_docs.html + nav.js, forum.js, i18n.js, shared.css

## Conventions
- 后端 Python 使用 async/await，SQLAlchemy async session
- 所有 HTML 共享 `nav.js`（登录状态检测）+ `shared.css`
- 中英文切换用 `i18n.js` 的 `data-i18n` 属性
- API 返回 JSON，前端 `catch` 处理错误
- Git 推送需本地代理 (127.0.0.1:7897)，推送完立即 unset
- 部署流程：本地 Docker 构建 → SCP 上传 → 服务器 load + up -d
