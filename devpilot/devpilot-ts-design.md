明白了，你用的是 **DeepSeek-V4** 模型。这个模型在 2026 年 4 月发布，API 完全兼容 OpenAI 格式，同时引入了新的参数。

设计文档的核心原则不变：**不改动 Agent 逻辑，只改配置**。以下是针对 DeepSeek-V4 更新后的设计文档（v2.1）：

---

```markdown
# DevPilot-TS — TypeScript + Node.js 版 AI 编程助手（修订版 v2.1）

> 技术栈：TypeScript + Node.js + Vercel AI SDK (`v3.4.33`) + LangGraph.js  
> 难度：⭐⭐⭐（比 Python 版降一档，砍掉 30% 功能，聚焦核心能力）  
> **核心增强**：LLM 供应商可插拔（原生支持 Agnes 与 **DeepSeek-V4** 平滑切换）

---

## 目录

- [1. 项目定位](#1-项目定位)
- [2. 为什么 TS + Node](#2-为什么-ts--node)
- [3. 技术栈选型](#3-技术栈选型)
  - [3.1 核心依赖与版本锁定](#31-核心依赖与版本锁定)
  - [3.2 LLM 供应商抽象层](#32-llm-供应商抽象层)
- [4. 三层架构（修订版）](#4-三层架构修订版)
- [5. 项目结构](#5-项目结构)
- [6. 用户视角](#6-用户视角)
- [7. 6 阶段落地路线](#7-6-阶段落地路线)
- [8. 供应商差异与适配策略](#8-供应商差异与适配策略)
- [9. 安全设计](#9-安全设计)
- [10. 学习收益](#10-学习收益)

---

## 1. 项目定位

**DevPilot-TS** 是一个常驻在你终端里的 AI 编程助手，能：

- 📝 记住你的代码风格和项目结构（**记忆层**）
- 🤖 多个专职 Agent 协作完成"写代码 → 测试 → review"（**多 Agent 层**）
- 🔧 通过 MCP 接入 git/文件系统等开发工具（**MCP 层**）
- 💬 在终端和你对话，也能被 VS Code / Cursor 调用（**MCP Server**）
- 🔄 **底层 LLM 可随时切换**（Agnes / DeepSeek-V4 / 其他 OpenAI 兼容 API），不改动 Agent 逻辑

### 降难度后的范围（对比 Python 版）

| 功能 | Python 版 | TS 版（本项目） |
|---|---|---|
| Agent 数量 | 3 个子 Agent（Coder/Reviewer/Tester）+ Orchestrator | **2 个**（Coder + Reviewer）+ Orchestrator |
| 工具数量 | 8+ | **5 个**（read_file/write_file/run_cmd/git_diff/notes） |
| MCP Server | 4 个工具暴露 | **2 个工具** |
| 记忆类型 | 4 种 | **2 种**（短期 + 用户画像），向量记忆作为可选扩展 |
| 工期 | 3-4 周 | **2-3 周**（含供应商适配器基建） |
| CLI 框架 | Typer + Rich | **Commander.js + Ora + Chalk** |
| **LLM 供应商** | 单一 OpenAI | **抽象化，可插拔**（内置 Agnes / DeepSeek-V4 适配器） |

---

## 2. 为什么 TS + Node

| 优势 | 说明 |
|---|---|
| **AI SDK 原生** | Vercel AI SDK 是 TS 原生，streaming/tool-calling 比 LangChain TS 更顺手 |
| **MCP SDK 友好** | Anthropic 官方 MCP TS SDK 是一等公民，文档最完整 |
| **前端无缝** | 后续想加 Web UI（Next.js），TS 全栈复用类型 |
| **Cursor/Claude Code 生态** | 这两个主流 AI 编程工具都是 TS 生态，你的 MCP Server 直接能被它们用 |
| **部署轻量** | Node 单进程 + npx 启动 MCP Server 比 Python venv + npx 混合简单 |

---

## 3. 技术栈选型

### 3.1 核心依赖与版本锁定（⚠️ 防坑铁律）

> **特别声明**：Vercel AI SDK 的 v3 → v4 存在破坏性 API 变更，且 `zod-to-json-schema` 存在严重的间接依赖冲突。**必须严格锁定以下版本**，否则阶段一无法启动。

| 类别 | 选型 | 锁定版本 | 为什么 / 备注 |
|---|---|---|---|
| **运行时** | Node.js | 20+ LTS | 原生支持 ESM 和 fetch |
| **语言** | TypeScript | 5.4+ | 严格模式 |
| **包管理** | pnpm | v11+ | 使用 `pnpm.overrides` 强制依赖版本 |
| **LLM SDK（核心）** | `ai` | **3.4.33** | **禁止升级到 v4.x**，v3 的 `tool()` 执行函数为 `execute({ args })` |
| **OpenAI 适配器** | `@ai-sdk/openai` | **0.0.72** | 配合 v3 使用，`createOpenAI({ baseURL, apiKey })` |
| **Schema 校验** | `zod` | **3.23.8** |  |
| **Schema → JSON** | `zod-to-json-schema` | **3.23.5** | 必须强制覆盖，防止被间接拉取 3.25+ 版本导致函数签名报错 |
| **Agent 编排** | `@langchain/langgraph` | 0.0.30+ | 状态机 + 条件边（注意：JS 版无原生 SQLite Saver，需自行序列化） |
| **MCP SDK** | `@modelcontextprotocol/sdk` | **1.0.4** | 暂不升级到 1.29+，避免与 zod 3.23 冲突 |
| **CLI** | `commander` + `ora` + `chalk` + `@inquirer/prompts` | 最新 | 业界标准组合 |
| **存储** | `better-sqlite3` + `lowdb` | 最新 | SQLite 做 checkpoint（存 JSON 序列化数据），lowdb 做用户画像 |
| **测试** | `vitest` | 最新 |  |
| **代码质量** | `biome` | 最新 | 一体化 lint + format |

**pnpm overrides 强制锁定配置（放入 package.json）**：

```json
{
  "pnpm": {
    "overrides": {
      "zod-to-json-schema": "3.23.5"
    }
  }
}
```

### 3.2 LLM 供应商抽象层（核心架构升级）

不将任何特定供应商（OpenAI / Agnes / DeepSeek-V4）硬编码在 Agent 代码中。所有 LLM 调用通过 **工厂模式 + 配置驱动**。

**环境变量规范**：

| 变量名 | 说明 | 示例值 |
|---|---|---|
| `LLM_PROVIDER` | 供应商标识 | `agnes` / `deepseek-v4` / `openai` |
| `LLM_BASE_URL` | API 基础路径（不含 `/chat/completions`） | `https://api.deepseek.com` |
| `LLM_API_KEY` | 密钥 | `sk-xxx` |
| `LLM_MODEL` | 模型名称 | `deepseek-v4-pro` 或 `deepseek-v4-flash` |
| `LLM_MAX_OUTPUT_TOKENS` | 最大输出 Token | `8192`（DeepSeek-V4 默认限制） |

**两个内置适配器模块**（位于 `src/infra/`，对 Agent 层完全透明）：

1. **请求构建器（Request Builder）**：根据 `LLM_PROVIDER` 自动注入供应商特有参数。
   - Agnes：自动添加 `body.chat_template_kwargs.enable_thinking = true`。
   - **DeepSeek-V4**：通过 `thinking.reasoning_effort` 控制思考强度。普通请求默认 `high`，复杂 Agent 请求自动设为 `max`。支持 `high` 和 `max` 两个级别。
   - 通用：透传 `temperature`、`maxTokens` 等标准字段。

2. **响应归一化器（Response Normalizer）**：将不同供应商的返回结构统一成标准的 `{ content, reasoning?, toolCalls[] }` 格式。
   - Agnes：`content` 直接包含最终答案。
   - **DeepSeek-V4**：思考模式（thinking mode）下返回 `reasoning_content` 字段，提取为单独的 `reasoning` 元数据；非思考模式直接透传 `content`。

---

## 4. 三层架构（修订版）

```
┌─────────────────────────────────────────────────────┐
│  Layer 1: 记忆层                                     │
│  ┌────────────────┐    ┌────────────────┐           │
│  │  Short-term    │    │  User Profile  │           │
│  │  (LangGraph    │    │  (lowdb JSON)  │           │
│  │   checkpoint)  │    │  代码风格/项目  │           │
│  │  SQLite 持久化 │    │  偏好          │           │
│  └────────────────┘    └────────────────┘           │
└─────────────────────────────────────────────────────┘
                        ▲
                        │
                        ▼
┌─────────────────────────────────────────────────────┐
│  Layer 2: 多 Agent 协作层（与供应商无关）             │
│            ┌─────────────────┐                      │
│            │  Orchestrator   │                      │
│            └────────┬────────┘                      │
│         ┌───────────┴───────────┐                   │
│         ▼                       ▼                   │
│   ┌──────────┐            ┌───────────┐             │
│   │  Coder   │ ─────────→ │  Reviewer │             │
│   │  Agent   │            │  Agent    │             │
│   └──────────┘            └───────────┘             │
└─────────────────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────┐
│  Layer 3: 工具生态层 + LLM 适配层                    │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │
│  │  本地工具    │  │  MCP Client │  │  MCP Server │  │
│  │ read_file   │  │ git-mcp     │  │ (暴露给     │  │
│  │ write_file  │  │ filesystem  │  │  Cursor)    │  │
│  │ run_cmd     │  │ -mcp        │  │             │  │
│  │ git_diff    │  │             │  │             │  │
│  │ notes       │  │             │  │             │  │
│  └─────────────┘  └─────────────┘  └─────────────┘  │
│                                                     │
│  ┌─────────────────────────────────────────────┐    │
│  │         LLM 供应商适配层（新增）             │    │
│  │  ┌───────────────┐  ┌──────────────────┐   │    │
│  │  │ 请求构建器     │  │ 响应归一化器     │   │    │
│  │  │ (Agnes/DeepS) │  │ (Agnes/DeepS)   │   │    │
│  │  └───────────────┘  └──────────────────┘   │    │
│  └─────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────┘
```

---

## 5. 项目结构

```
devpilot-ts/
├── package.json               # 含 pnpm.overrides 版本锁定
├── tsconfig.json
├── biome.json
├── .env.example               # 包含 LLM_PROVIDER 等变量模板
├── README.md
├── src/
│   ├── index.ts               # CLI 入口
│   ├── config.ts              # 配置加载（dotenv + zod 校验）
│   ├── logger.ts              # 简单 console logger
│   ├── types.ts               # 共享类型
│   │
│   ├── infra/                 # 🆕 基础设施层（供应商隔离）
│   │   ├── llm-factory.ts     # 根据 LLM_PROVIDER 创建统一的 llm 实例
│   │   ├── request-builder.ts # 注入供应商特有参数（Thinking / reasoning_effort 等）
│   │   └── response-normalizer.ts # 归一化不同供应商的返回结构
│   │
│   ├── agent/                 # Layer 2（纯业务，依赖 infra/llm-factory）
│   │   ├── state.ts           # AgentState 定义（Annotation）
│   │   ├── graph.ts           # Orchestrator 主图
│   │   ├── orchestrator.ts    # 编排节点：理解需求、分派
│   │   ├── coder-agent.ts     # 写代码 Agent
│   │   ├── reviewer-agent.ts  # Review Agent
│   │   └── prompts.ts         # 各 Agent 的 system prompt（供应商特定模板）
│   │
│   ├── memory/                # Layer 1
│   │   ├── short-term.ts      # 基于 MemorySaver + 手动序列化到 SQLite
│   │   ├── user-profile.ts    # 用户画像 (lowdb)
│   │   └── summarizer.ts      # 对话摘要压缩（根据 maxOutput 动态调整阈值）
│   │
│   ├── tools/                 # Layer 3
│   │   ├── local/
│   │   │   ├── file-ops.ts    # read_file / write_file（路径沙箱）
│   │   │   ├── shell.ts       # run_cmd（spawn + 参数数组，严格过滤）
│   │   │   ├── git-ops.ts     # git_diff / git_commit
│   │   │   └── notes.ts       # 笔记存储
│   │   ├── mcp-client.ts      # MCP Client 管理器
│   │   └── mcp-adapter.ts     # MCP → AI SDK Tool
│   │
│   ├── mcp-server/            # Layer 3 暴露端
│   │   └── server.ts          # 把 DevPilot 暴露为 MCP Server
│   │
│   └── utils/
│       ├── path.ts            # 路径安全（防越界）
│       └── confirm.ts         # 用户确认提示
├── tests/
│   ├── agent.test.ts
│   ├── tools.test.ts
│   └── memory.test.ts
└── data/                      # 运行时数据
    ├── checkpoints.sqlite     # LangGraph 持久化（JSON 序列化存 blob）
    ├── profile.json           # 用户画像
    └── notes/                 # 笔记存储
```

---

## 6. 用户视角

### 6.1 第一次使用

```bash
$ npx devpilot

👋 欢迎使用 DevPilot！我是你的 AI 编程助手。
看到你是第一次使用，先简单介绍下你的偏好：

? 你主要用什么语言？ › Python
? 测试框架？ › pytest
? 代码风格偏好？ › 带 type hints，函数有 docstring

好的，记下了。之后给你写代码默认按这个来。

接下来可以试试：
  - "在 ~/projects/demo 写个 hello world"
  - "看下 ~/projects/web 的 README"
  - "帮我 git diff 看看刚才的改动"
```

### 6.2 日常使用

```bash
你: 看下 ~/projects/web/src/login.py 哪里有问题
DevPilot: 
  [read_file] 读到 142 行
  [分析] 第 87 行 query_user 函数没有处理 SQL 注入
  
  建议改成：
  ```python
  def query_user(user_id: str) -> User:
      cursor.execute(
          "SELECT * FROM users WHERE id = %s",
          (user_id,)  # 参数化
      )
  ```
  
  要我直接改吗？(y/n)

你: y
DevPilot:
  [write_file] 已更新 login.py
  [git_diff] 显示改动
  
  要我 commit 吗？(y/n)

你: y
DevPilot:
  [git_commit] 提交：fix: 修复 query_user SQL 注入问题
  ✓ 完成
```

### 6.3 多 Agent 协作

```bash
你: 给 ~/projects/api 写个 health check 接口，带测试
DevPilot:
  [Orchestrator] 拆解任务：
    1. Coder Agent: 写 health check
    2. Coder Agent: 写测试
    3. Reviewer Agent: review 两者
  
  [Coder Agent] 正在写 health check...
  [Coder Agent] 正在写测试...（并行）
  [Reviewer Agent] review 中...
  
  ✅ 全部完成：
  - 新增 src/health.py
  - 新增 tests/test_health.py
  - Review 通过（2 个小建议见下）
  
  要 commit 吗？
```

### 6.4 在 Cursor 里用（MCP Server）

Cursor 配置 `~/.cursor/mcp.json`：
```json
{
  "mcpServers": {
    "devpilot": {
      "command": "npx",
      "args": ["-y", "devpilot-mcp"]
    }
  }
}
```

之后在 Cursor 对话框输入：
```
/devpilot 看下这个项目结构，告诉我哪些可以重构
```
Cursor 会调你的 MCP Server，DevPilot 用它记住的你的偏好来分析。

---

## 7. 6 阶段落地路线（修订版）

### 阶段 1：环境 + LLM 适配层 + 单 Agent MVP（2.5 天）

**目标**：跑通"读文件 + 调 Agnes/DeepSeek-V4 + 输出"最小闭环，且供应商切换仅需改 `.env`。

**做什么**：
1. `pnpm init` + 按 **3.1 节版本锁定** 装依赖（**切记不要装 `ai@latest**）。
2. 写 `src/infra/llm-factory.ts`：读取 `LLM_PROVIDER`，调用 `createOpenAI` 并传入对应的 `baseURL` 与 `apiKey`。
   - DeepSeek-V4 的 `base_url` 为 `https://api.deepseek.com`
   - `model` 参数为 `deepseek-v4-pro` 或 `deepseek-v4-flash`
3. 写 `src/infra/request-builder.ts`：
   - 若 `provider === 'agnes'`：合并 `chat_template_kwargs.enable_thinking`
   - 若 `provider === 'deepseek-v4'`：通过 `thinking.reasoning_effort` 控制思考强度，复杂 Agent 场景建议设为 `max`
4. 写 `src/tools/local/file-ops.ts`：`read_file` 工具。
5. 写最小 Agent：用户输入路径 → Agent 调 read_file → 调用 `llm-factory` 生成的实例 → 输出总结。
6. 验证：改 `.env` 中的 `LLM_PROVIDER` 为 `deepseek-v4`，重启后无需改代码即切换成功。

**学到**：
- TS + Node 项目搭建
- Vercel AI SDK 的 `generateText` + `tool` 用法（v3 版）
- Zod schema 定义工具参数
- 工厂模式与适配器模式隔离供应商差异

**验收**：
```
你: 看下 package.json
DevPilot: 这是你的项目配置文件，主要依赖...
（切换 provider 后功能完全一致）
```

---

### 阶段 2：记忆层（3 天）

**目标**：重启 DevPilot 后能恢复对话状态，记住你的偏好。

**做什么**：
1. 装 `better-sqlite3`，写 `src/memory/short-term.ts`
   - **关键修改**：LangGraph.js 无官方 SQLite Saver，改用 `MemorySaver` + 手动 `JSON.stringify(state)` 存 SQLite BLOB，启动时反序列化恢复。
2. 装 `lowdb`，写 `src/memory/user-profile.ts`
   - 启动时检测是否第一次用，是则引导用户配置
3. 写 `src/memory/summarizer.ts`
   - 超过 10 轮对话时，LLM 摘要前 8 轮，保留最近 2 轮；根据当前 `LLM_MAX_OUTPUT_TOKENS` 动态调整压缩阈值
4. 改 Agent：每轮调 LLM 前先从 profile 读偏好，注入 system prompt

**学到**：
- LangGraph.js 的 checkpoint 机制及自定义持久化
- JSON 文件存储（lowdb 比直接 fs 简单）
- 对话窗口压缩策略
- 环境变量驱动的动态策略调整

**验收**：
- 重启 CLI 后能继续上次的对话
- 第一次配置后，以后写代码默认带 type hints（你之前配置的）

---

### 阶段 3：多 Agent 协作（3 天）

**目标**：把单 Agent 拆成 Orchestrator + Coder + Reviewer。

**做什么**：
1. 写 `src/agent/state.ts`：定义 `AgentState`（含 `task`、`coderOutput`、`reviewResult` 等字段）
2. 写 `src/agent/coder-agent.ts`：
   - 接收任务描述
   - 调 LLM 生成代码（LLM 实例来自 `llm-factory`，不硬编码模型名）
   - 调 write_file 写入
3. 写 `src/agent/reviewer-agent.ts`：
   - 读 Coder 写的代码
   - 调 LLM review
   - 返回 review 结果（通过/有建议/不通过）
4. 写 `src/agent/orchestrator.ts`：
   - 接收用户请求
   - LLM 决策：简单任务直接 Coder，复杂任务 Coder+Reviewer
5. 写 `src/agent/graph.ts`：
   - LangGraph 主图：`orchestrator → coder → reviewer → end/rework`
   - 条件边：reviewer 不通过则回到 coder（带 feedback），最大重试次数 3 次防止死循环

**学到**：
- LangGraph.js 的多节点 + 条件边
- 子 Agent 之间通过 state 传递数据
- 串行 pipeline（Coder → Reviewer）

**验收**：
```
你: 在 ~/test 写个加法函数 a+b
DevPilot: 
  [Coder] 写好了 add.py
  [Reviewer] review 通过
  完成
```

---

### 阶段 4：MCP Client 集成（2 天）

**目标**：让 Agent 能调用外部 MCP Server。

**做什么**：
1. 装 `@modelcontextprotocol/sdk`（版本锁定 1.0.4）
2. 写 `src/tools/mcp-client.ts`：
   - 启动时连接配置的 MCP Server（git-mcp、filesystem-mcp）
   - 列出所有可用工具
3. 写 `src/tools/mcp-adapter.ts`：
   - 把 MCP tool 转成 AI SDK 的 `tool()` 格式（v3 的 `execute({ args })` 风格）
4. 在 Agent 里注册 MCP 工具
5. 装 `@modelcontextprotocol/server-filesystem`，配置连接本地文件系统 MCP

**学到**：
- MCP 协议的 stdio 传输
- MCP tool schema → AI SDK tool 的转换
- 动态工具发现

**验收**：
```
你: 用 git-mcp 看下当前分支
DevPilot: [mcp:git/status] 当前在 main 分支，有 2 个未提交改动
```

---

### 阶段 5：暴露为 MCP Server（2 天）

**目标**：让 Cursor / Claude Desktop 能调 DevPilot。

**做什么**：
1. 写 `src/mcp-server/server.ts`：
   - 用 `@modelcontextprotocol/sdk` 的 `Server` 类
   - 暴露 2 个工具：`ask_devpilot`（对话）、`get_profile`（读用户画像）
2. 在 `package.json` 加 `"bin": { "devpilot": "dist/index.js", "devpilot-mcp": "dist/mcp-server/server.js" }`（CLI 与 MCP 服务分离，避免 stdio 死锁）
3. 配置 Cursor 的 `mcp.json` 指向 `devpilot-mcp`
4. 在 Cursor 里测试

**学到**：
- MCP Server 端实现
- 工具暴露与 schema 定义
- 多客户端共享一个 Agent

**验收**：
- Cursor 对话框输入 `/devpilot 你好`，能拿到 DevPilot 的回复
- 不同的 Cursor 项目共享同一个用户画像

---

### 阶段 6：长期记忆扩展（可选，2 天）

**目标**：让 DevPilot 能跨会话回忆"上次类似的任务"。

**做什么**：
1. 装 `@langchain/community` 的 Chroma vectorstore
2. 写 `src/memory/long-term.ts`：
   - 每次任务完成后，把"任务描述 + 解决方案"向量化存入 Chroma
   - 下次任务开始时，retrieve 最相似的 3 条历史
3. 在 Orchestrator 里把检索结果注入 prompt

**学到**：
- 向量数据库基础
- RAG（检索增强生成）模式
- 跨会话记忆

**验收**：
- 上周解决了一个 race condition bug
- 这周说"上次那个 race condition 怎么修的"，能找到

---

## 8. 供应商差异与适配策略（核心参考表）

| 特性维度 | **Agnes-2.0-Flash** | **DeepSeek-V4** | **架构处理方式** |
| :--- | :--- | :--- | :--- |
| **API 基础地址** | `https://apihub.agnes-ai.com/v1` | `https://api.deepseek.com` | 通过 `LLM_BASE_URL` 环境变量配置 |
| **模型名称** | `agnes-2.0-flash` | `deepseek-v4-pro` 或 `deepseek-v4-flash` | 通过 `LLM_MODEL` 环境变量配置 |
| **推理/思考模式** | 通过 `chat_template_kwargs.enable_thinking` 开启 | 通过 `thinking.reasoning_effort` 控制（`high` / `max`） | 抽象为 `enableReasoning` + `reasoningEffort` 配置项；Agnes 映射为 `chat_template_kwargs`，DeepSeek-V4 映射为 `thinking.reasoning_effort` |
| **推理内容返回位置** | 直接混入 `content` 字段 | 思考模式下返回 `reasoning_content` 字段 | `response-normalizer` 提取 `reasoning_content` 存入 `metadata`，Agent 只拿纯净 `content` |
| **最大输出 Token** | 65,536 | 受上下文长度限制，建议设为 8192 | `LLM_MAX_OUTPUT_TOKENS` 环境变量控制 |
| **上下文窗口** | 512K | **1M**（百万级） | 记忆层压缩策略可调整：DeepSeek-V4 上下文极大，可大幅减少压缩甚至不做压缩 |
| **工具调用** | 完全遵循 OpenAI 标准 | 完全遵循 OpenAI 标准，支持 `tools` 和 `tool_choice` | **无需适配**，工具定义（Zod Schema）在两端完全通用 |
| **Agent 能力** | 标准 | **显著增强**，在 Agentic Coding 评测中达开源最佳水平 | 适合复杂多步 Agent 任务，建议 Orchestrator 在 DeepSeek-V4 下启用更高 `reasoning_effort` |

**切换成本**：修改 `.env` 中的 5 个变量 → 重启 CLI → 完成。Agent 图、工具、MCP 零改动。

---

## 9. 安全设计

DevPilot 能读写文件、跑命令，安全是第一要务。

### 9.1 路径沙箱

```typescript
// src/utils/path.ts
import path from 'node:path';

const ALLOWED_ROOTS = [
  process.env.HOME + '/projects',
  process.cwd(),
];

export function assertSafePath(p: string): void {
  const resolved = path.resolve(p);
  const allowed = ALLOWED_ROOTS.some(root => resolved.startsWith(path.resolve(root)));
  if (!allowed) {
    throw new Error(`路径越界: ${p} (仅允许: ${ALLOWED_ROOTS.join(', ')})`);
  }
}
```

### 9.2 命令白名单（⚠️ 加强版）

**修复原文档漏洞**：禁止使用 `child_process.exec`，必须使用 `spawn` + **参数数组模式**，并对输入字符串进行严格过滤（禁止 `;`、`$`、`` ` ``、`|` 等特殊字符），防止命令注入。

```typescript
// src/tools/local/shell.ts
const ALLOWED_COMMANDS = ['ls', 'cat', 'grep', 'git', 'npm', 'pnpm', 'node'];
const BLOCKED = ['rm', 'sudo', 'chmod', 'curl', 'wget'];

// 只允许预设的安全子命令集合（如 git status --porcelain），不开放自由拼接
export async function runCmd(command: string, args: string[]): Promise<string> {
  // 过滤特殊字符
  if (/[;|$`]/.test(command) || args.some(a => /[;|$`]/.test(a))) {
    throw new Error('命令包含非法字符');
  }
  const base = command.split(/\s+/)[0];
  if (BLOCKED.includes(base)) {
    throw new Error(`命令被禁止: ${base}`);
  }
  if (!ALLOWED_COMMANDS.includes(base)) {
    throw new Error(`命令不在白名单: ${base}`);
  }
  // 使用 spawn 执行
  ...
}
```

### 9.3 写操作必须确认

```typescript
// src/utils/confirm.ts
import { confirm } from '@inquirer/prompts';

export async function confirmWrite(path: string): Promise<boolean> {
  return confirm({
    message: `确认写入 ${path}?`,
    default: false,
  });
}
```

**非交互模式**：MCP Server 模式下需支持 `--yes` 全局标志，由路径沙箱兜底保证安全。

---

## 10. 学习收益

完成 DevPilot-TS 后，你将掌握：

### 10.1 TS/Node 生态

- TypeScript 严格模式 + Zod 运行时校验
- Node.js 异步编程（Promise、async/await、流）
- pnpm + ESM 模块系统 + 依赖版本锁定与覆盖
- 用 vitest 写测试

### 10.2 AI Agent 技术

- Vercel AI SDK（v3）的 streaming + tool calling
- LangGraph.js 状态机 + 条件边
- 多 Agent 协作（Orchestrator + Worker 模式）
- 记忆管理（短期 checkpoint + 长期画像）
- **LLM 供应商抽象与可插拔架构设计**

### 10.3 MCP 生态

- MCP Client 集成（接外部工具）
- MCP Server 暴露（被 Cursor/Claude 调用）
- MCP Resources 和 Prompts 高级用法

### 10.4 工程能力

- 安全沙箱设计（路径 + 命令防注入）
- CLI 工具开发（commander + 交互式确认）
- 持久化（SQLite + JSON）
- 跨平台路径处理

### 10.5 新增：LLM 供应商抽象与可插拔架构设计
- 理解如何通过工厂模式和适配器模式隔离外部依赖。
- 掌握处理不同供应商非标准特性（Thinking、reasoning_effort、reasoning_content）的策略。
- 学会利用环境驱动配置实现"零代码修改"的供应商切换。

---

## 下一步行动指南

1. **严格按 3.1 节版本锁定创建 `package.json`**，执行 `pnpm install`。
2. 配置 `.env`：
   ```env
   LLM_PROVIDER=deepseek-v4
   LLM_BASE_URL=https://api.deepseek.com
   LLM_API_KEY=sk-xxx
   LLM_MODEL=deepseek-v4-flash   # 或 deepseek-v4-pro
   LLM_MAX_OUTPUT_TOKENS=8192
   ```
3. 阶段一跑通后，花 10 分钟将 `.env` 切到 Agnes，验证整个 Agent 流水线是否正常（只改配置不改代码）。
4. 每天提交 git commit，方便回退。
5. 卡住时先对照 3.1 节检查依赖版本，再查 `src/infra/` 适配器是否配置正确。

**你现在手上的这份设计文档，已经包含了所有"依赖陷阱"的避坑指南和"DeepSeek-V4 完整适配"的架构方案。放心开工！** 🚀
```