# 贡献指南 · Contributing

感谢你想贡献代码或测试！这个项目还很早期，任何形式的参与都有帮助。

## 我能做什么

| 你擅长 | 可以做的 |
|--------|---------|
| 🤖 **测试 MCP** | 用 Claude / 龙虾助手连上平台，发需求、搜匹配、报告 bug |
| 🐍 **写 Python** | 改 bug、加新工具、优化分类引擎、完善测试 |
| 🎨 **写前端** | 优化 17 个 HTML 页面、加视觉效果 |
| 📝 **写文档** | 改进 README、写教程、翻译 |
| 💡 **提建议** | 去 Issues 区提功能建议 |

## 快速开始

```bash
git clone https://github.com/HuanTongqichetuzhuang/demand-chain.git
cd demand-chain

# Python 虚拟环境
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e .

# 配置 DeepSeek API Key
cp .env.example .env
# 编辑 .env 填入 DEEPSEEK_API_KEY

# 跑测试
python tests/run_all.py
```

## MCP 测试指南

1. 在 AI 助手（Claude、通义千问、龙虾助手）里配置 MCP：
   ```
   URL: https://demand-chain.duckdns.org/sse
   ```

2. 第一次连上会说没有账号，注册一个测试账号

3. 试试这些流程：
   - 发布一条需求 → 看看分类对不对
   - 搜索需求 → 看看搜索结果
   - 注册能力画像 → 看看匹配引擎
   - 调 `list_available_tools` → 看看工具列表

4. 发现 bug 去 Issues 提，标 `bug` 标签

## 代码规范

- 用 Python 3.12
- 函数加 docstring
- 异步用 async/await
- MCP 工具返回 JSON 字符串
- 新功能写测试
- 提交信息用中文或英文都行

## 架构

```
src/
├── server.py          # MCP 服务（56 个工具）
├── wechat_bot.py      # 微信公众号接入（端口 9000）
├── worker.py          # 后台调度器
├── shared/            # 共享模块
│   ├── models.py      # 11 张数据库表
│   ├── database.py    # SQLAlchemy 异步引擎
│   ├── classification.py  # 分类引擎（24 学科）
│   ├── auth.py        # 身份认证（session_token）
│   └── task_manager.py    # 异步任务系统
├── adapters/          # LLM 客户端（DeepSeek）
├── demand/            # 需求服务
├── matching/          # 匹配引擎
├── forum/             # 论坛
└── discovery/         # 供应商发现
```

## 当前阶段的重点

| 优先级 | 任务 |
|--------|------|
| 🔴 **高** | MCP 工具 bug 修复、测试覆盖 |
| 🟡 **中** | 分类引擎扩展（加新学科/新工艺） |
| 🟢 **低** | 前端页面优化、文档翻译 |
| ⚪ **未来** | A2A 协议、联邦架构、无状态部署 |

## 项目原则

1. **Agent 原生** — 人通过 AI 助手交互
2. **永久开源** — Apache 2.0
3. **匹配中立** — 不偏向任何一方
4. **数据最少化** — 不收集隐私

---

有问题在 Issues 里问，或者发论坛帖。欢迎 PR。


