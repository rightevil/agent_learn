# 领域文档

工程技能在探索代码库时应如何消费本仓库的领域文档。

## 探索前先阅读这些

- 仓库根目录下的 **`CONTEXT.md`**
- 如果存在 **`CONTEXT-MAP.md`**（多上下文仓库），则阅读它指向的每个 `CONTEXT.md`
- **`docs/adr/`** — 阅读与你即将工作的领域相关的架构决策记录。在多上下文仓库中，还需检查 `src/<上下文>/docs/adr/` 中特定上下文的决策。

如果这些文件不存在，**静默继续**。不要提示缺失，也不要急于建议创建。`/domain-modeling` 技能（通过 `/grill-with-docs` 和 `/improve-codeback-architecture` 到达）会在术语或决策实际被确定时懒加载创建它们。

## 文件结构

单上下文仓库（大多数仓库）：

```
/
├── CONTEXT.md
├── docs/adr/
│   ├── 0001-event-sourced-orders.md
│   └── 0002-postgres-for-write-model.md
└── src/
```

多上下文仓库（根目录存在 `CONTEXT-MAP.md`）：

```
/
├── CONTEXT-MAP.md
├── docs/adr/                          ← 系统级决策
└── src/
    ├── ordering/
    │   ├── CONTEXT.md
    │   └── docs/adr/                  ← 上下文特定决策
    └── billing/
        ├── CONTEXT.md
        └── docs/adr/
```

## 使用词表的术语

当你的输出命名了一个领域概念（在 issue 标题、重构提案、假设、测试名称中），请使用 `CONTEXT.md` 中定义的术语。不要偏离词表明确避免的同义词。

如果需要但你需要的概念不在词表中，这是一个信号——要么你在发明项目未使用的语言（请重新考虑），要么确实存在空白（在 `/domain-modeling` 中标注）。

## 标注 ADR 冲突

如果你的输出与现有 ADR 相矛盾，请明确标注，而不是悄悄覆盖：

> _与 ADR-0007（事件溯源订单）矛盾——但值得重新讨论因为……_
