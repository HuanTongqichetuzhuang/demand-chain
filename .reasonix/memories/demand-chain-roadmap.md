---
name: demand-chain-roadmap
title: 开发路线图（2026-06-14）
description: 需求链平台开发路线图 P0-P3
metadata:
  type: project
---

## 当前开发路线（2026-06-14）
**P0-安全（本周完成）:** 
① bcrypt密码加盐(1h) ② Token/Task持久化(4h) ③ 头像存储改文件系统(3h) ④ 注册限速+邮箱验证(3h) ⑤ 用户输入安全加固(1h)

**P1-匹配引擎质量（1-2周）:**
⑥ limit(500)硬编码修复(0.5h) ⑦ pgvector语义搜索(8h) ⑧ Worker健康检查(2h) ⑨ docker-compose补Web(1h)

**P2-架构与性能（1-2周）:**
⑩ Redis缓存(6h) ⑪ 前端错误处理(2h) ⑫ Nav缓存根治(1h) ⑬ 测试覆盖率(8h) ⑭ Alembic迁移(1h)

**P3-战略功能（规划）:**
⑮ 需求链分解引擎(16h) ⑯ A2A通信原型(20h) ⑰ 数据飞轮(12h)

**建议顺序:** P0→P1→P2→P3，P0总计约12h，P1约11.5h

**Why:** 记录了最新的开发优先级和任务分配，避免重复规划。
**How to apply:** 当用户说"继续开发"或"干活"时，按此优先级询问用户想推进哪一项。
