# 需求链平台 — 完整开发交接文档
生成时间: 2026-06-11

---

## 1. 服务器信息

### 阿里云 ECS
| 项目 | 值 |
|------|---|
| **公网 IP** | 8.154.26.92 |
| **SSH 端口** | 2222 |
| **SSH 用户** | root |
| **服务器配置** | 1.6GB RAM, 阿里云 ECS |
| **系统** | Linux |

### SSH 登录命令
```bash
ssh -o StrictHostKeyChecking=no -p 2222 root@8.154.26.92
```

### 项目路径
- **服务器**: `/opt/demand-chain/`
- **Docker compose 文件**: `/opt/demand-chain/docker-compose.prod.yml`
- **本地开发路径**: `E:/项目/需求链平台`

---

## 2. 数据库

### PostgreSQL + pgvector
| 项目 | 值 |
|------|---|
| **容器名** | dc-db |
| **数据库名** | demand_chain |
| **用户名** | dc |
| **密码** | dc_dev_2026 |
| **端口** | 5432 |
| **镜像** | pgvector/pgvector:pg16 |

### 当前数据量（2026-06-11）
| 表 | 记录数 |
|---|---|
| demands | 26 |
| capability_profiles（供应商） | 63 |
| forum_topics | 0 |
| forum_replies | 0 |
| users | 0 |

### 直接操作数据库
```bash
ssh -p 2222 root@8.154.26.92 "docker exec dc-db psql -U dc -d demand_chain"
```

---

## 3. Docker 服务

### 三个容器

| 服务 | 容器名 | 端口 | 说明 |
|------|--------|------|------|
| **db** | dc-db | 5432 | PostgreSQL |
| **mcp** | dc-mcp | 8000 | MCP Server (给AI助手用) |
| **web** | dc-web | 8080 | Web 页面 + REST API |

### MCP 环境变量
```
DATABASE_URL=postgresql+asyncpg://dc:dc_dev_2026@db:5432/demand_chain
DEEPSEEK_API_KEY=sk-c32415bb5ae44cdc844f1b95f99e4544
FIRECRAWL_API_KEY=fc-e97094049296412bb87cc3946d515649
```

### 部署命令（本地构建+上传）
```bash
cd "E:/项目/需求链平台"
docker build -t demand-chain:slim .
docker save demand-chain:slim -o "E:/temp/dc-slim.tar"
scp -o StrictHostKeyChecking=no -P 2222 "E:/temp/dc-slim.tar" root@8.154.26.92:/opt/dc-slim.tar
ssh -o StrictHostKeyChecking=no -p 2222 root@8.154.26.92 \
  "docker load -i /opt/dc-slim.tar > /dev/null && rm /opt/dc-slim.tar && \
   cd /opt/demand-chain && docker compose -f docker-compose.prod.yml -p dc up -d --force-recreate web"
```

---

## 4. API 服务

### MCP Server (端口 8000)
- **地址**: `http://8.154.26.92:8000/sse`
- **本地 MCP 配置**: `~/.workbuddy/mcp.json` 中 `demand-chain` 条目
- 工具数量: 56+

### Web/REST API (端口 8080)
| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/demands` | GET | 获取所有需求 |
| `/api/suppliers` | GET | 获取所有供应商 |
| `/api/login` | POST | 用户登录 |
| `/api/register` | POST | 用户注册 |
| `/api/auto-demand` | POST | 爬虫自动添加需求 |
| `/api/auto-supplier` | POST | 爬虫自动添加供应商 |
| `/api/user/profile` | GET/PUT | 用户资料 |
| `/api/user/avatar` | POST | 上传头像 |
| `/api/user/password` | PUT | 修改密码 |
| `/api/user/stats` | GET | 用户统计 |
| `/api/forum/topics` | GET | 浏览帖子 |
| `/api/forum/topics/create` | POST | 发帖 |
| `/api/forum/topics/{id}/reply` | POST | 回复 |
| `/api/forum/topics/{id}/vote` | POST | 点赞 |
| `/api/forum/topics/{id}/replies` | GET | 获取回复 |
| `/api/forum/categories` | GET | 获取分类列表 |

---

## 5. 网站页面

| 页面 | URL | 状态 |
|------|-----|:--:|
| 首页 | `/` (index.html) | ✅ |
| 需求广场 | `/demand_square.html` | ✅ 41条需求，18分类 |
| 供应商 | `/suppliers.html` | ✅ 20家供应商，13分类 |
| 论坛 | `/forum.html` | ✅ 全部功能 |
| 登录/注册 | `/login.html` | ✅ |
| 个人主页 | `/profile.html` | ✅ |
| API 文档 | `/api_docs.html` | ✅ |
| 教程 | `/docs/tutorial.html` | ✅ |
| NLnet 提案 | `/docs/NLNET_PROPOSAL.md` | ✅ |

---

## 6. 账号和资金

### GitHub
| 项目 | 值 |
|------|---|
| **用户名** | HuanTongqichetuzhuang |
| **仓库** | https://github.com/HuanTongqichetuzhuang/demand-chain |
| **分支** | master |
| **赞助方式** | GitHub Sponsors + 爱发电 |

### 爱发电
| 项目 | 值 |
|------|---|
| **链接** | https://afdian.com/a/demand-chain |

### 微信赞赏码
- 文件: `WeChatPay.jpg` (在项目根目录)

### 测试账号
| 项目 | 值 |
|------|---|
| **邮箱** | test@dc.ai |
| **密码** | pass123 |

### 用户邮箱
| 项目 | 值 |
|------|---|
| **创始人邮箱** | 477570216@qq.com |

---

## 7. 文件结构

```
E:/项目/需求链平台/
├── index.html              # 首页
├── demand_square.html      # 需求广场
├── suppliers.html          # 供应商页面
├── forum.html              # 论坛
├── login.html              # 登录/注册
├── profile.html            # 个人主页
├── api_docs.html           # API 文档
├── nav.js                  # 导航栏登录状态（所有页面共享）
├── forum.js                # 论坛 JS（外部文件，无内联脚本）
├── i18n.js                 # 中英文切换
├── WeChatPay.jpg           # 微信赞赏码
├── logo.jpg                # Logo
├── Dockerfile              # Docker 构建
├── docker-compose.yml      # 本地开发 compose
├── README.md               # GitHub README
├── .github/FUNDING.yml     # GitHub 赞助按钮
├── scripts/
│   └── auto_crawler.py     # 自动爬虫（需求+供应商）
├── src/
│   ├── server.py           # MCP Server
│   ├── web_server.py       # Web Server + REST API
│   ├── shared/
│   │   ├── models.py       # 数据库模型
│   │   └── database.py     # 异步数据库连接
│   └── forum/service.py    # 论坛服务
├── docs/
│   ├── tutorial.html       # 教程
│   └── NLNET_PROPOSAL.md   # NLnet 提案
└── prompts/                # AI 提示词模板
```

---

## 8. 自动爬虫

### 脚本位置
`scripts/auto_crawler.py`

### 运行方式
```bash
cd "E:/项目/需求链平台"
python scripts/auto_crawler.py
```

### 需求来源 (9个)
- USA.gov 联邦挑战
- NASA 挑战
- DARPA 研究项目
- Grants.gov 联邦资助
- XPRIZE 竞赛
- MIT Solve
- Climate-KIC
- 国家自然科学基金委 (NSFC)
- 新加坡航空航天挑战

### 供应商来源 (3个)
- StartUs Insights (碳捕集初创)
- RankRed 气候科技
- Energy Startups 氢能

### 调度
每日 06:00 自动执行（automation-1781121806143）

### 入库接口
- `/api/auto-demand` - 自动添加需求
- `/api/auto-supplier` - 自动添加供应商

### 分类方式
关键词匹配（19个行业，中英双语关键词）

---

## 9. Git 代理配置

在 Windows Git Bash 中使用代理：
```bash
git config --local http.proxy http://127.0.0.1:7897
# 操作完成后取消
git config --local --unset http.proxy
```

---

## 10. 当前已知问题

| 问题 | 状态 |
|------|:--:|
| 浏览器缓存旧页面（已加 no-cache 头） | ✅ 已修复 |
| 论坛内联 JS 导致的语法错误 | ✅ 已改为外部 forum.js |
| 导航栏 CRLF 导致的 JS 错误 | ✅ 已用 nav.js + i18n.js 解决 |
| users 表缺少 avatar/bio 列 | ⚠️ 需执行 ALTER TABLE |
| 部分 HTML 页面未适配移动端 | ⚠️ 待优化 |

---

## 11. NLnet 提案

- 文件: `docs/NLNET_PROPOSAL.md`
- 金额: €45,000
- 阶段: 4个 Phase（匹配引擎 → A2A 通信 → 国际化 → 运维）
- 提交地址: https://nlnet.nl/propose/

---

## 12. 本地开发

### Python 环境
```bash
cd "E:/项目/需求链平台"
.venv/Scripts/python -m src.server           # MCP Server
.venv/Scripts/python -m src.web_server       # Web Server
```

### 验证编译
```bash
.venv/Scripts/python -c "from src.web_server import app; print('OK')"
```

### 本地代理
- 代理地址: 127.0.0.1:7897
- 用于 GitHub push/pull

---

## 13. 用户偏好和习惯

| 项目 | 说明 |
|------|------|
| **语言** | 中文交互，指令简洁 |
| **确认方式** | 执行前先预览，满意后再做 |
| **反馈风格** | 表格对比优先 |
| **Git 推送** | 需要通过代理 (127.0.0.1:7897)，用完即删 |
| **部署** | 本地 Docker 构建 → SCP 上传 → 服务器加载 |

---

## 14. 已完成的功能清单

| 模块 | 完成度 |
|------|:---:|
| MCP Server (56+ 工具) | ✅ |
| Web 服务器 (静态 + REST API) | ✅ |
| 注册/登录系统 | ✅ |
| 需求数据库 + 自动爬虫 | ✅ |
| 供应商数据库 + 自动爬虫 | ✅ |
| 需求广场（搜索、分类、详情弹窗） | ✅ |
| 供应商页面（筛选、分类） | ✅ |
| 论坛（发帖/回复/点赞） | ✅ |
| 个人主页（头像、资料、密码） | ✅ |
| 中英文切换 | ✅ |
| 导航栏登录状态 | ✅ |
| 教程页 | ✅ |
| API 文档页 | ✅ |
| 赞助渠道（微信+爱发电） | ✅ |
| Search and Networking Engine | ✅ |
| NLnet 提案 | ✅ |
| 自动爬虫调度 | ✅ |
