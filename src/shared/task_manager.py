"""
异步任务系统 — 耗时操作拆分为 创建任务 → 轮询结果。
爬虫、供应商发现等操作不再阻塞 Agent。
"""
import asyncio
import logging
import time
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# task_id → {status, human_id, created_at, result, error}
_tasks: dict[str, dict] = {}
_seq = 0


def create_task(human_id: str, label: str) -> str:
    """创建新任务，返回 task_id"""
    global _seq
    _seq += 1
    task_id = f"task-{int(time.time())}-{_seq}"
    _tasks[task_id] = {
        "id": task_id,
        "human_id": human_id,
        "label": label,
        "status": "running",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "result": None,
        "error": None,
    }
    logger.info(f"[Task] created: {task_id} ({label})")
    return task_id


def complete_task(task_id: str, result: any):
    """标记任务完成"""
    if task_id in _tasks:
        _tasks[task_id]["status"] = "completed"
        _tasks[task_id]["result"] = result
        logger.info(f"[Task] completed: {task_id}")


def fail_task(task_id: str, error: str):
    """标记任务失败"""
    if task_id in _tasks:
        _tasks[task_id]["status"] = "failed"
        _tasks[task_id]["error"] = error
        logger.info(f"[Task] failed: {task_id}: {error}")


def get_task(task_id: str, human_id: str = "") -> dict:
    """获取任务状态"""
    t = _tasks.get(task_id)
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


def list_tasks(human_id: str, limit: int = 10) -> list:
    """列出人类的所有任务"""
    tasks = [t for t in _tasks.values() if t["human_id"] == human_id]
    tasks.sort(key=lambda t: t["created_at"], reverse=True)
    return [
        {"id": t["id"], "label": t["label"], "status": t["status"],
         "created_at": t["created_at"]}
        for t in tasks[:limit]
    ]
