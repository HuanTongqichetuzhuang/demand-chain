---
name: demand-chain-overview
title: 需求链平台概况
description: 需求链平台项目概况与功能范围
metadata:
  type: project
---

## 项目概况
需求链平台是一个 AI 驱动的开放式创新基础设施，连接全球需求与供应商。

**核心功能:**
- 需求发布与管理（自然语言→结构化）
- 供应商能力画像注册
- 自动匹配引擎（TF-IDF + 分类重叠度 + 信任评分）
- 语义搜索（中文bigram分词）
- 论坛系统（发帖/回复/点赞/分行业）
- 自动爬虫（每日6点，15个数据源）
- MCP Server（56+工具供AI Agent接入）

**技术栈:** Python 3.12 / Starlette / SQLAlchemy(async) / PostgreSQL 16 + pgvector / Docker

**当前数据:** 供应商1877家（24分类），需求103条（含爬虫），论坛5主题

**用户偏好:** 中文交互，指令简洁，执行前预览，表格对比优先

**Why:** 每次会话需要了解项目本质、功能范围和当前状态。
**How to apply:** 用户提出需求时，先判断属于哪个功能模块，再定位到对应的代码文件。
