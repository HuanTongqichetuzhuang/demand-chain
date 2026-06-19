"""
Redis 异步缓存包装器。

提供 get/set/delete/remember 操作，支持 JSON 序列化。
Redis 不可用时静默降级（不缓存），不抛异常。
"""
import json
import logging
from typing import Any, Callable, Coroutine, Optional

from src.shared.config import settings

logger = logging.getLogger(__name__)

_redis = None
_pool = None


async def get_redis():
    """获取 Redis 连接（懒加载，单例）。"""
    global _redis, _pool
    if _redis is not None:
        return _redis
    try:
        import redis.asyncio as aioredis
        _pool = aioredis.ConnectionPool.from_url(
            settings.redis_url,
            max_connections=10,
            decode_responses=True,
        )
        _redis = aioredis.Redis(connection_pool=_pool)
        await _redis.ping()
        logger.info(f"[Cache] Redis connected: {settings.redis_url}")
        return _redis
    except Exception as e:
        logger.warning(f"[Cache] Redis unavailable (caching disabled): {e}")
        _redis = None
        return None


async def close_redis():
    """关闭 Redis 连接池。"""
    global _redis, _pool
    if _pool:
        await _pool.disconnect()
        _pool = None
    _redis = None


async def get(key: str) -> Optional[Any]:
    """获取缓存值（JSON 自动反序列化）。"""
    r = await get_redis()
    if r is None:
        return None
    try:
        val = await r.get(key)
        if val is None:
            return None
        return json.loads(val)
    except Exception as e:
        logger.debug(f"[Cache] get({key}) error: {e}")
        return None


async def set(key: str, value: Any, ttl: int = 300) -> bool:
    """设置缓存值（JSON 自动序列化），ttl 单位秒。"""
    r = await get_redis()
    if r is None:
        return False
    try:
        await r.setex(key, ttl, json.dumps(value, default=str))
        return True
    except Exception as e:
        logger.debug(f"[Cache] set({key}) error: {e}")
        return False


async def delete(key: str) -> bool:
    """删除单个缓存键。"""
    r = await get_redis()
    if r is None:
        return False
    try:
        await r.delete(key)
        return True
    except Exception as e:
        logger.debug(f"[Cache] delete({key}) error: {e}")
        return False


async def delete_pattern(pattern: str) -> int:
    """删除匹配 pattern 的所有键（如 cache:home:*）。"""
    r = await get_redis()
    if r is None:
        return 0
    try:
        cursor, keys = await r.scan(match=pattern, count=100)
        if keys:
            return await r.delete(*keys)
        return 0
    except Exception as e:
        logger.debug(f"[Cache] delete_pattern({pattern}) error: {e}")
        return 0


async def remember(key: str, ttl: int, func: Callable[[], Coroutine[Any, Any, Any]]) -> Any:
    """先读缓存，缓存未命中则执行 func 并写入缓存。"""
    cached = await get(key)
    if cached is not None:
        return cached
    result = await func()
    await set(key, result, ttl)
    return result

