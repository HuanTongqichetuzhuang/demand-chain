FROM python:3.12-slim

WORKDIR /app

RUN pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/

RUN apt-get update && apt-get install -y --no-install-recommends build-essential curl && rm -rf /var/lib/apt/lists/*

# 只装核心依赖，不装 crawl4ai（太重）
RUN pip install --no-cache-dir fastapi "uvicorn[standard]<0.30" sqlalchemy[asyncio] asyncpg pgvector pydantic pydantic-settings python-dotenv httpx mcp alembic

COPY src/ ./src/
COPY prompts/ ./prompts/
COPY i18n/ ./i18n/
COPY AGENT_GUIDE.md ./
COPY *.html ./
COPY *.jpg ./
COPY *.png ./
COPY docs/ ./docs/

EXPOSE 8000

CMD ["python", "-m", "src.server"]
