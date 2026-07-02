# DevPilot-TS

AI 编程助手 — 学习 Agent 开发设计模式的 TypeScript 练手项目。

## 学习目标

- **Orchestrator + Workers** 多 Agent 协作模式
- **结构化 ReAct** 循环（推理→行动→观察，四字段 state，支持暂停/恢复）
- Agent 记忆管理（短期 checkpoint + 用户画像）

## 快速开始

```bash
# 安装依赖
pnpm install

# 配置环境变量
cp .env.example .env
# 编辑 .env，填入 AGNES_API_KEY

# 运行
pnpm dev
```

## 项目结构

```
src/
├── index.ts              # CLI 入口
├── config.ts             # 配置加载（dotenv + zod）
├── agent/                # Agent 层
│   ├── state.ts          # ReAct state 定义
│   ├── orchestrator.ts   # 编排器（规则 + LLM 兜底）
│   ├── react.ts          # ReAct 循环引擎
│   └── prompts.ts        # 各 Agent 的 system prompt
├── memory/               # 记忆层
│   ├── short-term.ts     # 短期记忆（LangGraph checkpoint）
│   └── user-profile.ts   # 用户画像（lowdb）
├── tools/                # 工具层
│   ├── read_file.ts
│   └── write_file.ts
└── utils/
    └── logger.ts
```

## 学习资源

- [devpilot-ts-design.md](./devpilot-ts-design.md) — 完整设计文档
- [ts_nodejs_getting_started.md](./ts_nodejs_getting_started.md) — Python → TS 入门指南
