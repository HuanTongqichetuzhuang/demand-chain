# 需求链平台部署指南

## 架构

```
数据库: PostgreSQL 16 + pgvector
    ↓
MCP 服务: demand-chain (端口 8000) → 56+ MCP 工具
    ↓
Web 站点: 静态 HTML + REST API (端口 8080)
    ↓
人类浏览器: 17 个 HTML 页面
```

## 快速启动（云服务器）

```bash
# 1. 安装 Docker + Docker Compose（如果没装）
curl -fsSL https://get.docker.com | bash

# 2. 克隆仓库
git clone https://github.com/HuanTongqichetuzhuang/demand-chain.git
cd demand-chain

# 3. 配置环境变量
vim docker-compose.prod.yml
# 修改: DEEPSEEK_API_KEY、FIRECRAWL_API_KEY

# 4. 启动全部服务
docker compose -f docker-compose.prod.yml -p dc up -d

# 5. 检查
docker ps              # dc-db, dc-mcp, dc-web 都在 Running
curl localhost:8000    # MCP 服务（返回 404 正常，SSE 在 /sse）
curl localhost:8080    # 网站首页（返回 200）
```

## 端口说明

| 端口 | 服务 | 用途 |
|------|------|------|
| 8000 | MCP Server | AI 助手接入 `https://demand-chain.duckdns.org/sse` |
| 8080 | Web 站点 | 人类浏览器访问 `http://IP:8080` |
| 5432 | PostgreSQL | 数据库（仅内部） |
| 9000 | ~~微信服务~~ | 已弃用 |

## 更新部署

```bash
cd demand-chain

# 从 GitHub 拉最新代码
git pull

# 重新构建并启动
docker compose -f docker-compose.prod.yml -p dc build mcp
docker compose -f docker-compose.prod.yml -p dc up -d --force-recreate mcp
docker compose -f docker-compose.prod.yml -p dc up -d --force-recreate web

# 或者一键（在本地 Docker 环境）
```

## 本地开发

```bash
# 后端
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# 启动 MCP 服务
python -m src.server

# 前端（纯 HTML，无需构建）
# 直接用浏览器打开 login.html 即可
# API 从 web_server.py 提供
```

## 生产环境配置

- 服务器最低配置：**1 核 1G**（数据库 + MCP + Web 挤在一起）
- 推荐配置：**2 核 4G**
- 开放端口：8000（MCP）、8080（Web）
- 数据库自动保存，重启不丢数据

