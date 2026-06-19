"""
异步任务系统 — 耗时操作拆分为 创建任务 → 轮询结果。
爬虫、供应商发现等操作不再阻塞 Agent。

持久化方案：任务写入数据库，同时维护内存缓存。
"""
import asyncio
import logging
import time
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# 内存缓存: task_id → {id, human_id, label, status, created_at, result, error}
_task_cache: dict[str, dict] = {}
_seq = 0
_loaded_from_db: set[str] = set()


async def _persist_task(task_id: str, human_id: str, label: str):
    """写入任务到数据库"""
    from src.shared.database import async_session
    from src.shared.models import AsyncTask
    try:
        async with async_session() as session:
            session.add(AsyncTask(
                id=task_id,
                human_id=human_id,
                label=label,
                status="running",
            ))
            await session.commit()
    except Exception as e:
        logger.error(f"Failed to persist task: {e}")


async def _update_task_db(task_id: str, **kwargs):
    """更新数据库中的任务字段"""
    from src.shared.database import async_session
    from src.shared.models import AsyncTask
    from sqlalchemy import select
    try:
        async with async_session() as session:
            r = await session.execute(
                select(AsyncTask).where(AsyncTask.id == task_id)
            )
            t = r.scalar_one_or_none()
            if t:
                for k, v in kwargs.items():
                    setattr(t, k, v)
                await session.commit()
    except Exception as e:
        logger.error(f"Failed to update task {task_id}: {e}")


async def _load_task_from_db(task_id: str) -> dict | None:
    """从数据库加载一个任务"""
    from src.shared.database import async_session
    from src.shared.models import AsyncTask
    from sqlalchemy import select
    try:
        async with async_session() as session:
            r = await session.execute(
                select(AsyncTask).where(AsyncTask.id == task_id)
            )
            t = r.scalar_one_or_none()
            if t:
                return {
                    "id": t.id,
                    "human_id": t.human_id,
                    "label": t.label,
                    "status": t.status,
                    "created_at": t.created_at.isoformat() if t.created_at else "",
                    "result": t.result,
                    "error": t.error,
                }
    except Exception as e:
        logger.error(f"Failed to load task from DB: {e}")
    return None


async def create_task(human_id: str, label: str) -> str:
    """创建新任务，返回 task_id"""
    global _seq
    _seq += 1
    task_id = f"task-{int(time.time())}-{_seq}"
    entry = {
        "id": task_id,
        "human_id": human_id,
        "label": label,
        "status": "running",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "result": None,
        "error": None,
    }
    _task_cache[task_id] = entry
    _loaded_from_db.add(task_id)
    await _persist_task(task_id, human_id, label)
    logger.info(f"[Task] created: {task_id} ({label})")
    return task_id


async def complete_task(task_id: str, result_data: any):
    """标记任务完成"""
    if task_id in _task_cache:
        _task_cache[task_id]["status"] = "completed"
        _task_cache[task_id]["result"] = result_data
        await _update_task_db(task_id, status="completed", result=result_data)
        logger.info(f"[Task] completed: {task_id}")


async def fail_task(task_id: str, error: str):
    """标记任务失败"""
    if task_id in _task_cache:
        _task_cache[task_id]["status"] = "failed"
        _task_cache[task_id]["error"] = error
        await _update_task_db(task_id, status="failed", error=error)
        logger.info(f"[Task] failed: {task_id}: {error}")


async def get_task(task_id: str, human_id: str = "") -> dict:
    """获取任务状态（缓存→DB）"""
    t = _task_cache.get(task_id)
    if not t:
        # 查 DB
        if task_id not in _loaded_from_db:
            _loaded_from_db.add(task_id)
            t = await _load_task_from_db(task_id)
            if t:
                _task_cache[task_id] = t
    if not t:
        return {"error": "任务不存在"}
    if human_id and t["human_id"] != human_id:
        return {"error": "无权访问此任务"}
    return {
        "id": t["id"],
        "label": t["label"],
        "status": t["status"],
        "created_at": t["created_at"],
        "result": t["result"],
        "error": t["error"],
    }


async def list_tasks(human_id: str, limit: int = 10) -> list:
    """列出人类的所有任务（先查 DB 补充缓存，再取缓存）"""
    # 从 DB 加载该用户的任务（补充缓存）
    from src.shared.database import async_session
    from src.shared.models import AsyncTask
    from sqlalchemy import select, desc
    try:
        async with async_session() as session:
            r = await session.execute(
                select(AsyncTask)
                .where(AsyncTask.human_id == human_id)
                .order_by(desc(AsyncTask.created_at))
                .limit(limit)
            )
            for t in r.scalars().all():
                if t.id not in _task_cache:
                    _task_cache[t.id] = {
                        "id": t.id,
                        "human_id": t.human_id,
                        "label": t.label,
                        "status": t.status,
                        "created_at": t.created_at.isoformat() if t.created_at else "",
                        "result": t.result,
                        "error": t.error,
                    }
                    _loaded_from_db.add(t.id)
    except Exception as e:
        logger.error(f"Failed to list tasks from DB: {e}")

    # 从缓存取
    tasks = [t for t in _task_cache.values() if t["human_id"] == human_id]
    tasks.sort(key=lambda t: t["created_at"], reverse=True)
    return [
        {"id": t["id"], "label": t["label"], "status": t["status"],
         "created_at": t["created_at"]}
        for t in tasks[:limit]
    ]


async def cleanup_old_tasks(max_age_days: int = 30):
    """清理超过指定天数的已完成/失败任务"""
    from src.shared.database import async_session
    from src.shared.models import AsyncTask
    from sqlalchemy import delete
    from datetime import datetime, timezone, timedelta
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
        async with async_session() as session:
            result = await session.execute(
                delete(AsyncTask)
                .where(AsyncTask.created_at < cutoff)
                .where(AsyncTask.status.in_(["completed", "failed"]))
            )
            await session.commit()
            if result.rowcount:
                logger.info(f"Cleaned up {result.rowcount} old tasks")
                # 也从缓存清理
                keys_to_del = [
                    k for k, v in _task_cache.items()
                    if v["status"] in ("completed", "failed")
                    and v.get("created_at", "") < cutoff.isoformat()
                ]
                for k in keys_to_del:
                    _task_cache.pop(k, None)
                    _loaded_from_db.discard(k)
    except Exception as e:
        logger.error(f"Failed to cleanup old tasks: {e}")

