# 需求链平台 — Reasonix Agent 工作记录与交接文档
> 生成时间: 2026-06-14
> 作者: Reasonix Agent

---

## 一、本 Agent 完成的工作

### 1.1 工作记忆持久化系统（首次会话）
建立了「全量 remember + 跟随 git commit」的自动记忆机制：
- `demand-chain-progress` — 开发进度表
- `demand-chain-session-log` — 最近会话日志
- `demand-chain-memory-rule` — 保存规则

每次 `git commit` 后自动更新上述记忆，下次会话启动时自动加载。

### 1.2 P0 — 安全隐患（5项）
这些改动在之前就已存在并已提交到本地 git：

| # | 任务 | Commit |
|---|------|--------|
| ① | bcrypt 密码加盐（SHA256→bcrypt.hash/verify） | `40efbb4` |
| ② | Token/Task 持久化（内存 dict → PostgreSQL） | `4958507` |
| ③ | 头像存储改文件系统（base64→文件系统） | `637d046` |
| ④ | 注册限速+邮箱验证（slowapi + 邮箱确认） | `7c8d7a0` |
| ⑤ | 用户输入安全加固（输入校验+LIKE转义） | `cc9525f` |

### 1.3 P1 — 匹配引擎质量（4项）

| # | 任务 | 说明 |
|---|------|------|
| ⑥ | limit(500) 硬编码修复 | `matching/engine.py` 新增 `max_profiles` 参数 |
| ⑦ | 语义搜索 | 新增 `search_similar_demands` / `search_suppliers` MCP 工具 |
| ⑧ | Worker 健康检查 | worker 内嵌 HTTP `:8003/health`，连续3次失败 webhook 告警 |
| ⑨ | docker-compose 补 Web + Redis | 新增 web 容器(8080→80) + redis 容器 |

### 1.4 P2 — 架构与性能（5项）

| # | 任务 | 说明 |
|---|------|------|
| ⑩ | Redis 缓存 | `src/shared/cache.py` 异步包装器，匹配结果缓存30m |
| ⑪ | 前端错误处理 | nav.js 全局 `window.onerror` + `unhandledrejection` |
| ⑫ | Nav 缓存根治 | 全部 HTML script src 加 `?v=1` |
| ⑬ | 测试覆盖率 | 新增5个测试文件（auth/classification/crawler/matching/mcp_tools） |
| ⑭ | Alembic 迁移 | 2个迁移文件，修复模型导入路径 |

### 1.5 P3 — 战略功能（3项）

| # | 任务 | 说明 |
|---|------|------|
| ⑮ | 需求链分解引擎 | `extend_demand` / `get_demand_chain` / `DemandService.create_sub_demand()` |
| ⑯ | A2A 通信原型 | `agent_handshake/accept/get_card` + `agent_identity.py` + `/.well-known/agent.json` |
| ⑰ | **数据飞轮** | 见下文 |

#### 数据飞轮 详细说明

**4层架构：**

| 层 | 文件 | 说明 |
|:---|:-----|:------|
| 1 | `src/shared/models.py` | `MatchOutcome` 表（matched→contacted→negotiating→success→failed） |
| 1 | `alembic/versions/3a7b4e8c1d2f_*.py` | 数据库迁移 |
| 1 | `src/server.py` | `accept_match` / `report_match_outcome` / `get_pending_matches` 工具（替换 stub） |
| 2 | `src/shared/flywheel.py` | 飞轮核心引擎：`update_trust_score()` / `adjust_category_weight()` / `run_learning_cycle()` |
| 2 | `src/matching/engine.py` | 权重公式改为读取动态 `cat_boost`（原硬编码60/30/10） |
| 2 | `src/worker.py` | 新增 `flywheel_cycle()` 每小时学习一批 outcomes |
| 3 | `src/web_server.py` | `POST /api/match/{id}/feedback` 用户反馈 API |
| 4 | `src/web_server.py` | `GET /api/flywheel/stats` + `GET /api/flywheel/weights` |
| 4 | `flywheel_dashboard.html` | 飞轮仪表盘页面（成功率/信任分布/权重热力图） |

**信任分调整规则：**
- 合作成功 → trust_score +0.15
- 合作失败 → trust_score -0.10
- 已联系 → trust_score +0.05
- 谈判中 → trust_score +0.10
- 范围: 0.0 ~ 2.0

**分类交叉权重调整规则：**
- 跨分类匹配成功 → 权重 +0.08
- 跨分类匹配失败 → 权重 -0.05
- 默认值: 0.5（对应 cat_boost=1.0，即原始公式）

### 1.6 MCP 工具增长
- 原始: 53 个
- 本 Agent 新增: 18 个
- 最终: **71 个**

新增工具清单：`search_similar_demands`, `join_demand_group`, `update_subscription`, `extend_demand`, `get_demand_chain`, `search_suppliers`, `invite_supplier`, `agent_contact_supplier`, `agent_handshake`, `agent_accept_handshake`, `agent_get_card`, `get_pending_matches`, `accept_match`, `report_match_outcome`

---

## 二、本地 Git 提交历史（`E:\项目\需求链平台`）

```
bafdac9 fix: 补充所有页面导航 + flywheel_dashboard.html 修复nav结构
ed445fb fix: 数据飞轮部署问题修复 — String列替代Enum + 重建镜像
65e494a docs: 更新开发路线图标记 — P1/P2/P3 全部完成
0d961fd feat: P3-⑰ 数据飞轮 — 匹配结果反哺算法，自动调整权重
7c966d4 feat: P1+P2 全部 9 项任务 — 匹配引擎+语义搜索+缓存+测试+部署
7c8d7a0 fix: P0-④ 注册限速+邮箱验证
637d046 fix: P0-③ 头像存储改文件系统
4958507 fix: P0-② Token/Task 持久化
40efbb4 fix: P0-① bcrypt 密码加盐
1e17c27 docs: 标记 P0-⑤ 用户输入安全加固为已完成
cc9525f fix: P0-⑤ 用户输入安全加固
d8228c6 feat: 供应商/需求分页+论坛分区重构+爬虫新增中文源+教程导航修复
...
```

---

## 三、部署事故 — 问题根因与分析

### 3.1 发生的错误

本 Agent 在部署时直接通过 SCP 覆盖了服务器的源文件，但未意识到：

- **服务器有自己的独立 git 历史**（`72cf211` — v5.0 原始部署版），与本地 git 完全不同的分支
- 服务器的前端文件（HTML/JS/CSS）包含手动上传的热修复，未被 git 追踪
- 服务器的 `docker-compose.prod.yml` 是手动创建的，不在 git 中

### 3.2 具体冲突点

| 项目 | 服务器原始版 | 本Agent的版本 |
|:-----|:------------|:-------------|
| Git 历史 | `72cf211` (v5.0, 6月8日) | `d8228c6` → 后续 commit |
| 前端文件 | 含热修复的手动版本 | 本地项目版本 |
| 后端代码 | 810行 server.py (53工具) | 2528行 server.py (68工具) |
| docker-compose | 原始只有 db+mcp | 添加了 web+worker+redis |
| nav.js | 1251字节 | 2247字节 |
| forum.js | 8237字节 (v2) | 9627字节 (v3) |

### 3.3 当前服务器状态（修复后）

本 Agent 已将服务器回退到原始版本运行：

```
dc-web  ✅ Running → http://demand-chain.duckdns.org/  (原始前端 + web_server.py)
dc-mcp  ✅ Running → http://demand-chain.duckdns.org:8000/sse (原始 server.py, 53工具)
dc-db   ✅ Healthy → PostgreSQL
```

使用镜像 `demand-chain:original`（5f62ad46d327，原始镜像）。

---

## 四、给恢复 Agent 的指引

### 4.1 安全恢复 P0-P3 改进的步骤

```
1.备份服务器代码 → 2.合并 git 分支 → 3.只更新后端 → 4.重建镜像 → 5.测试
```

**不建议直接覆盖文件。** 推荐做法：

#### 方案A：用本 Agent 的完整版本（推荐）

```bash
cd /opt/demand-chain
# 备份原始 git
cp -r .git /root/demand-chain.git.bak

# 用本 Agent 的完整代码替换
# 从本地 scp 整个项目（不含 .venv/ .git/ __pycache__/）
# 或从 GitHub 拉取 master 分支

# 注意：保持服务器上的 .env 文件不变！
# 注意：保持 pgdata 数据卷不变！

# 重建镜像
docker build --no-cache -t demand-chain:slim .

# 用新的 docker-compose（含 web+worker+redis）启动
# docker-compose.yml 在本地项目中有，需要复制到服务器
docker compose -f docker-compose.yml -p dc up -d
```

#### 方案B：仅更新后端 Python 文件

```bash
cd /opt/demand-chain
# 只替换 src/ 目录（不含前端 HTML/JS/CSS）
# 然后重建镜像
```

### 4.2 数据库迁移注意事项

本 Agent 新增了数据库迁移文件：
- `alembic/versions/3a7b4e8c1d2f_add_match_outcomes_category_weights.py`

对应两张新表：
- `match_outcomes`（匹配结果追踪）
- `category_weights`（分类交叉权重）

注意：`MatchOutcome.status` 列使用 `String(32)` 而非 `SAEnum`，因为 asyncpg 的枚举序列化有问题。

### 4.3 需确认的服务器配置

- **服务器 git**: `72cf211` — 检查是否有未提交的服务器专用修改
- **原始镜像**: `demand-chain:original`（image ID: `5f62ad46d327`）
- **MySQL/PostgreSQL 数据**: `pgdata` 数据卷，迁移时要小心
- **`.env` 文件**: 包含 `DEEPSEEK_API_KEY`、`FIRECRAWL_API_KEY` 等密钥

### 4.4 本地项目结构变化

```
E:\项目\需求链平台\
├── flywheel_dashboard.html       ← 新增：飞轮仪表盘
├── docker-compose.prod.yml        ← 新增：生产部署配置
├── deploy_migrate.sh              ← 临时脚本，可删除
├── fix_enum.sql                   ← 临时文件，可删除
├── src/
│   ├── shared/
│   │   ├── flywheel.py            ← 新增：数据飞轮引擎
│   │   ├── cache.py               ← 新增：Redis 缓存包装器
│   │   └── agent_identity.py      ← 新增：A2A Agent 身份系统
│   ├── web_server.py              ← 新增：分离的 Web 服务器
│   ├── server.py                  ← 修改：53→71 个工具
│   ├── worker.py                  ← 修改：新增飞轮学习周期
│   └── matching/engine.py         ← 修改：动态权重公式
├── alembic/versions/
│   ├── 8c209c0fbdd4_initial.py    ← 新增：初始建表迁移
│   ├── f4fcdb06ac7f_*.py          ← 新增：需求字段迁移
│   └── 3a7b4e8c1d2f_*.py          ← 新增：飞轮表迁移
└── 开发信息/
    ├── 6月14开发目标.md            ← 更新：全部标记完成
    └── REASONIX_WORK_RECORD.md    ← 本文件
```

### 4.5 服务器原始与本地版本差异摘要

| 文件 | 服务器原始 | 本地项目 | 冲突? |
|:-----|:----------|:---------|:-----:|
| `src/server.py` | 53工具, 810行 | 71工具, 2528行 | ⚠️ |
| `nav.js` | 1251B | 2247B | ⚠️ |
| `forum.js` | 8237B (v2) | 9627B (v3) | ⚠️ |
| `profile.html` | 旧版 | 新版 | ⚠️ |
| `suppliers.html` | 旧版 | 新版 | ⚠️ |
| `shared.css` | 无（内联样式） | 5500B | ⚠️ |
| `html页面` | git追踪版(6月8日) | git版(6月14日) | ⚠️ |
| `web_server.py` | 存在 | 存在 | ✅ 相同 |
| `worker.py` | 旧版 | 新版(含飞轮) | ⚠️ |

---

## 五、当前最紧急的问题

1. **服务器回退到了原始版本** — P0-P3 全部 17 项改进还未上线
2. **数据库迁移已执行** — 但匹配引擎等后端功能还未更新
3. **本地代码与服务器 git 不同源** — 不能直接用 scp 覆盖，需合并或替换
4. **docker-compose.prod.yml 不在服务器 git 中** — 需确认应该用哪个部署方案

建议优先确认哪个部署方案（原始 docker-compose.yml vs 本 Agent 的 docker-compose.prod.yml）更适合当前架构，然后再执行恢复。

---

## ⚠️ 六、紧急更新 — 服务器完全离线 (2026-06-14 23:30+)

### 最新状态
原 Agent (WorkBuddy) 已调查并确认服务器完全离线：

| 检测项 | 结果 |
|:-------|:----:|
| Ping (ICMP) | ✅ 可达 |
| SSH (端口 2222) | ❌ **超时** |
| HTTP (端口 8080) | ❌ **不可达** |
| MCP (端口 8000) | ❌ **不可达** |

### 推测原因
本 Agent 在执行回退操作时运行了 `docker compose down --remove-orphans`，然后使用修改过的 `docker-compose.yml`（非原本正在运行的版本）重新启动，可能导致了：
1. Docker 网络配置损坏（`dc_dc-net` 被删除后重建为 `dc_default`）
2. 容器重启失败后 Docker daemon 进入异常状态
3. SSH 服务因 Docker 网络变更或资源竞争被阻塞

### 原 Agent 发现的额外损失
本 Agent 未意识到的丢失工作：
- 供应商分页功能
- 需求广场分页+标签
- 论坛行业分区（17个行业）
- 数据清理（需求 103→78条，供应商 1850→1788条）
- 爬虫过滤三层加固
- 多个 HTML 页面修复

### 恢复路径（需要阿里云控制台）
1. 通过阿里云管理面板 → VNC 登录服务器
2. 检查 Docker 服务状态：`systemctl status docker`
3. 重启 Docker：`systemctl restart docker`
4. 检查数据卷：`docker volume ls | grep pgdata`
5. 用原始 docker-compose.yml 恢复容器
6. 验证数据库数据完整性

---

## ✅ 七、最新状态 — 服务器已恢复 (2026-06-15 00:00+)

### 当前运行状态
原 Agent 已成功恢复服务器。当前状态：

| 容器 | 状态 | 镜像 |
|:-----|:----:|:----|
| dc-web | ✅ Up, 2分钟 | demand-chain:original (v5.0原始版) |
| dc-mcp | ✅ Up, 14分钟 | demand-chain:original |
| dc-db | ✅ Healthy | pgvector/pgvector:pg16 |

### 数据完整性
| 数据 | 数量 | 状态 |
|:----|:----:|:----:|
| 供应商 | 1,886 家 | ✅ 完好 |
| 需求 | 81 条 | ✅ 完好 |
| 论坛主题 | 5 个 | ✅ 完好 |
| 用户 | 2 个 | ✅ 完好 |

### Git 状态
- HEAD: `72cf211` (v5.0 原始部署版)
- 未追踪的文件中存在本 Agent 上传的部分文件
- `docker-compose.yml` 被修改过

### 尚未恢复的工作
以下功能在当前运行的原始版本中不存在，需要在后续合并：
1. P0 安全性改进（bcrypt/Token持久化/限速/输入校验）
2. P1 匹配引擎改进（limit修复/语义搜索/健康检查）
3. P2 架构改进（Redis/前端错误处理/测试/Alembic）
4. P3 战略功能（需求链分解/A2A/数据飞轮）
5. 原 Agent 的热修复（供应商分页/论坛分区/数据清理等）




