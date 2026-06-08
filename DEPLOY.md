# 需求链平台部署清单

## 部署前检查

- [x] 全部模块导入通过 (16/16)
- [x] 完整测试通过 (35 pass, 0 fail, 2 skip = LLM API Key)
- [x] 数据库 10 张表全部创建
- [x] 16 个 HTML 页面就绪
- [x] 31 个 Python 源文件
- [x] Docker Compose 配置就绪

## 部署步骤

### 1. 配置环境变量
```bash
cp .env.example .env
# 编辑 .env，填入:
#   DEEPSEEK_API_KEY=sk-your-real-key
#   DATABASE_URL=postgresql+asyncpg://dc:dc_dev_2026@db:5432/demand_chain
```

### 2. 服务器上启动（阿里云 ECS 8.154.26.92）
```bash
# 安装 Docker
curl -fsSL https://get.docker.com | sh

# 拉代码
git clone https://github.com/your/demand-chain.git
cd demand-chain

# 配置环境
cp .env.example .env
nano .env  # 填入 DeepSeek API Key

# 启动全部服务
docker compose -p dc up -d

# 检查状态
docker compose -p dc ps
# 预期: dc-db (healthy), dc-mcp (running), dc-worker (running)

# 初始化数据库
docker compose -p dc exec mcp python -c "
import asyncio
from src.shared.database import engine, Base
import src.shared.models
async def main():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print('Tables created')
asyncio.run(main())
"

# 验证 MCP Server
curl http://localhost:8000/sse
# 返回 SSE 连接流
```

### 3. 本地启动（开发）
```bash
# 启动数据库
docker compose -p dc up -d db

# 安装依赖
python -m venv .venv
.venv/Scripts/pip install -e ".[dev]"

# 运行测试
PYTHONPATH="$PWD" .venv/Scripts/python tests/run_all.py

# 启动 MCP Server
PYTHONPATH="$PWD" .venv/Scripts/python -m src.server
```

### 4. Agent 接入
```json
{
  "mcpServers": {
    "demand-chain": {
      "url": "http://8.154.26.92:8000/sse",
      "transport": "sse"
    }
  }
}
```

## 当前状态

| 项目 | 状态 |
|------|------|
| 数据库 | PostgreSQL 16 + pgvector, 10张表 |
| MCP Server | FastMCP SSE, 37个工具 |
| HTML 页面 | 16个（全部可用mock数据） |
| 测试 | 35 pass / 0 fail |
| 国际化 | zh/en JSON + Agent原生架构 |
| 部署 | Docker Compose 3服务 |

## 下一步

1. 填入 DeepSeek API Key → 测试 LLM 结构化
2. 服务器上 docker compose up -d 部署
3. Agent 配置 MCP 接入测试
4. git push 到 GitHub 开源仓库
