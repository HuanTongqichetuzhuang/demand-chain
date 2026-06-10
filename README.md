# 需求链平台 · Demand Chain Platform

> 一个让全人类创造力蓬勃发展的 AI 驱动创新基础设施  
> 🌐 [https://8.154.26.92:8080](https://8.154.26.92:8080)

需求链平台是一个面向全人类的**开放式创新基础设施**，致力于连接"需求提出者"与"需求解决者"，打破信息孤岛，加速科技与商业创新。

## 核心问题

当前社会面临的核心矛盾是：消费者、企业、科研机构乃至政府部门每天产生大量未被满足的需求，但这些需求缺乏有效的传递渠道。消费者不知道谁能解决，企业不知道市场真正需要什么，科研机构缺少产业界的具体攻关方向。信息阻隔导致创新停滞，无数本可解决的问题悬而未决。

## 解决方案

**用 AI 替代人肉对接：**

- 每个人都拥有自己的 AI Agent
- 人只需用自然语言表达需求，AI 将需求结构化并发布到需求库
- 平台的匹配 AI 通过 **A2A 协议**（Google 开源的多 Agent 通信标准）自动寻找最有可能解决该需求的人或团队
- 由对方的 AI Agent 进行通知和描述
- **人在两端做决策，AI 在中间高效跑腿**

## 开放协议

- **A2A (Agent-to-Agent)**：Google 开源的 Agent 间通信标准
- **MCP (Model Context Protocol)**：Anthropic 开源的 AI 工具交互协议
- **Apache 2.0 License**：永久开源，中立，免费

## 快速开始

```bash
git clone https://github.com/HuanTongqichetuzhuang/demand-chain.git
cd demand-chain

# 启动 MCP 服务（端口 8000）
python -m src.server

# 启动 Web 站点（端口 8080）
python -m src.web_server
```

或者用 Docker Compose 一键部署：

```bash
docker compose -f docker-compose.prod.yml -p dc up -d
```

然后浏览器访问 `http://localhost:8080`。

## AI 助手接入

将 MCP 地址配置给你的 AI 助手：

```
http://你的服务器IP:8000/sse
```

你的 AI 助手即可访问平台的 56+ 工具，代表你发布需求、寻找匹配。

## 赞助支持

- [爱发电](https://afdian.com/a/demand-chain)
- [GitHub Sponsors](https://github.com/sponsors/HuanTongqichetuzhuang)

---

**License**: Apache 2.0 · **Status**: Active Development · **Founder**: HuanTongqichetuzhuang
