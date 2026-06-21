from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from .config import settings

# 连接池配置：MCP Server 需处理并发工具调用
# pool_size=20 支持 20 个同时查询，max_overflow=10 突发峰值再借 10 个
# pool_pre_ping=True 每次从池取连接前先 SELECT 1 验证连接有效
engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
    pool_recycle=3600,
)

_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

_db_initialized = False


class Base(DeclarativeBase):
    pass


async def init_db():
    global _db_initialized
    if _db_initialized:
        return
    async with engine.begin() as conn:
        from src.shared.models import Base
        await conn.run_sync(Base.metadata.create_all)
    _db_initialized = True
    import logging
    logging.getLogger(__name__).info("Database tables initialized")


class _SessionWrapper:
    """包装 async_sessionmaker，确保首次使用前初始化 DB 表结构。
    用法: async with async_session() as session:"""
    def __call__(self):
        return self

    async def __aenter__(self):
        global _db_initialized
        if not _db_initialized:
            await init_db()
        self._session = _session_factory()
        return await self._session.__aenter__()

    async def __aexit__(self, *args):
        await self._session.__aexit__(*args)


async_session = _SessionWrapper()
