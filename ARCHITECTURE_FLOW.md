# 需求链平台 — 架构流程图

## 1. 整体架构

```mermaid
flowchart TB
    subgraph Users["👥 用户层"]
        Human["🙋 人类用户\n(浏览器)"]
        Agent["🤖 AI Agent\n(MCP客户端)"]
    end

    subgraph Frontend["🌐 前端层"]
        WB["科研工作台\nscientist_workbench.html"]
        DS["需求广场"]
        SP["供应商目录"]
        FM["论坛"]
        CH["聊天"]
        GS["全局搜索"]
        NF["通知"]
    end

    subgraph API["🔌 API层"]
        WEB["Web Server (Starlette)\n端口 80/8080\nREST API + WebSocket"]
        MCP["MCP Server (FastMCP)\n端口 8000\n72 工具"]
    end

    subgraph Adapters["🔗 适配器层 🆕"]
        AC["AcademicClient\n学术检索客户端"]
        FC["FirecrawlClient\n爬虫客户端"]
        LC["LLMClient\nDeepSeek AI"]
    end

    subgraph Services["🧠 业务服务层"]
        DM["需求管理"]
        DE["供应商发现"]
        DC["需求发现"]
        ME["匹配引擎"]
        FW["数据飞轮"]
        CL["分类引擎"]
        FS["论坛"]
        NS["通知"]
        AC2["即时通讯"]
    end

    subgraph External["🌍 外部数据源"]
        PubMed["PubMed"]
        CrossRef["CrossRef"]
        OpenAlex["OpenAlex"]
        Semantic["Semantic Scholar"]
        GrantsGov["Grants.gov"]
        Firecrawl["Firecrawl"]
        Crawlers["15+ 爬虫脚本"]
    end

    subgraph Database["💾 数据层"]
        PG[("PostgreSQL\n16张表")]
        Redis[("Redis")]
    end

    Human --> WEB
    Agent --> MCP
    WEB --> WB & DS & SP & FM & CH & GS & NF
    WB --> WEB
    WEB --> DM & DE & DC & ME & FW & CL & FS & NS & AC2
    MCP --> DM & DE & DC & ME & FW & CL & FS & NS & AC2
    WEB --> AC
    MCP --> AC
    AC --> PubMed & CrossRef & OpenAlex & Semantic & GrantsGov
    DE --> FC
    DC --> FC
    FC --> Firecrawl
    DC --> Crawlers
    DM & DE & ME & FW --> PG
    CL --> LC
    NS --> Redis
```

## 2. 科研工作台数据流 🆕

```mermaid
sequenceDiagram
    participant User as 研究者
    participant WB as 科研工作台
    participant WEB as Web API
    participant AC as AcademicClient
    participant DBs as 学术数据库
    participant LLM as DeepSeek

    User->>WB: 输入研究主题
    WB->>WEB: GET /api/academic/search_papers
    WB->>WEB: GET /api/academic/search_funding
    WB->>WEB: POST /api/academic/research_summary

    WEB->>AC: search_papers(query)
    par PubMed
        AC-->>PubMed: NCBI E-utilities
        PubMed-->>AC: 论文元数据
    and CrossRef
        AC-->>CrossRef: REST API
        CrossRef-->>AC: DOI, authors
    and OpenAlex
        AC-->>OpenAlex: REST API
        OpenAlex-->>AC: 论文+引用数
    and Semantic Scholar
        AC-->>Semantic: Graph API
        Semantic-->>AC: 论文+引用
    end
    AC-->>WEB: 合并去重后列表

    AC->>GrantsGov: search_funding(query)
    GrantsGov-->>AC: 资助机会
    AC-->>WEB: 资助列表

    alt 已登录
        WEB->>LLM: 生成研究总结
        LLM-->>WEB: AI总结文本
    end

    WEB-->>WB: 综合返回
    WB->>User: 📋总结/📄论文/💰资助
```

## 3. 跨库去重流程 🆕

```mermaid
flowchart LR
    Q["用户查询词"] --> P["并行4个API"]

    P --> P1["PubMed"]
    P --> P2["CrossRef"]
    P --> P3["OpenAlex"]
    P --> P4["Semantic Scholar"]

    P1 --> R1["论文A PMID"]
    P2 --> R2["论文A DOI"]
    P3 --> R3["论文A 标题"]
    P4 --> R4["论文A 标题"]

    R1 & R2 & R3 & R4 --> Merge["标题去重合并"]
    Merge --> Sort["按年份降序"]
    Sort --> Out["去重结果"]
    Out --> Tag["标注数据源"]
```

## 4. MCP 工具全景 (72个)

```mermaid
mindmap
  root((72 MCP 工具))
    需求发布
      发布需求
      搜索需求
      相似需求检测
      加入需求组
      需求拆分
      需求链路
      更新/关闭
    供应商
      搜索供应商
      发现供应商
      匹配反馈
      邀请供应商
      接受匹配
      报告进展
    学术检索 🆕
      search_papers
      跨4库论文
      search_funding
      资助机会
      research_summary
      AI研究总结
    协作
      A2A握手
      协作工作区
      即时通讯
      在线状态
    论坛
      创建/查看
      回复/投票
    系统
      注册/登录
      Agent引导
      Webhook
      偏好设置
```

## 5. 数据源全景

```mermaid
mindmap
  root((数据源全景))
    需求发现
      USA.gov挑战赛
      XPRIZE
      EU Horizon Europe
      NASA
      MIT Solve
      DARPA
      HeroX
      UKRI
      ERC
    供应商发现
      Google Patents
      政府采购
      学术论文爬虫
      Firecrawl全网
    科研设备
      大学共享平台
      NRII
      SelectScience
      NIM计量院
    学术检索 🆕
      PubMed 医学
      CrossRef 跨学科
      OpenAlex 开放学术
      Semantic Scholar AI
      Grants.gov 资助
```

