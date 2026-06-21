FROM python:3.12-slim

WORKDIR /app

RUN pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/

# 只装核心依赖，不装 crawl4ai（太重）和 build-essential（不需要编译）
RUN pip install --no-cache-dir fastapi "uvicorn[standard]<0.30" sqlalchemy[asyncio] asyncpg pgvector pydantic pydantic-settings python-dotenv httpx mcp alembic "passlib[bcrypt]" "redis[hiredis]" && pip install "bcrypt<4.1" --no-cache-dir

COPY src/ ./src/
COPY prompts/ ./prompts/
COPY i18n/ ./i18n/
COPY AGENT_GUIDE.md ./
COPY *.html ./
COPY *.jpg ./
COPY *.png ./
COPY *.ico ./
COPY *.js ./
COPY scripts/ ./scripts/
COPY docs/ ./docs/
COPY alembic.ini ./
COPY alembic/ ./alembic/

EXPOSE 8000 80

CMD ["python", "-m", "src.server"]
