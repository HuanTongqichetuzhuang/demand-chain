#!/bin/bash
# 需求链平台一键启动脚本
# 用法: bash start.sh

set -e
PROJECT_DIR="E:/项目/需求链平台"

echo "=== 需求链平台启动 ==="

# 1. 检查 Docker
echo "[1/5] 检查 Docker..."
docker ps >/dev/null 2>&1 || { echo "Docker 未运行，请先启动 Docker Desktop"; exit 1; }

# 2. 启动数据库
echo "[2/5] 启动 PostgreSQL..."
cd "$PROJECT_DIR"
docker compose -p dc up -d db 2>/dev/null || docker start dc-db 2>/dev/null
sleep 3

# 3. 初始化数据库表
echo "[3/5] 创建数据库表..."
PYTHONPATH="$PROJECT_DIR" .venv/Scripts/python -c "
import asyncio, sys
sys.path.insert(0,'.')
from src.shared.database import engine, Base
import src.shared.models
async def main():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print('  所有表已就绪')
asyncio.run(main())
"

# 4. 运行测试
echo "[4/5] 运行测试..."
PYTHONPATH="$PROJECT_DIR" .venv/Scripts/python tests/run_all.py
echo ""

# 5. 启动 MCP Server
echo "[5/5] 启动 MCP Server..."
echo "  地址: http://localhost:8000/sse"
echo "  按 Ctrl+C 停止"
PYTHONPATH="$PROJECT_DIR" .venv/Scripts/python -m src.server
