# TypeScript + Node.js 入门手册（写给 Python 开发者）

> 这份手册专门给"会 Python、想转 TS + Node"的开发者用。
> 每个概念都对照 Python 解释，让你 1 小时读懂，1 天上手。
> 读完能直接开始做 [DevPilot-TS 项目](./devpilot-ts-design.md)。

---

## 目录

- [第 1 章 心智模型转换](#第-1-章-心智模型转换)
- [第 2 章 环境搭建](#第-2-章-环境搭建)
- [第 3 章 TypeScript 语法对照 Python](#第-3-章-typescript-语法对照-python)
- [第 4 章 Node.js 异步与标准库](#第-4-章-nodejs-异步与标准库)
- [第 5 章 包管理与 npm 生态](#第-5-章-包管理与-npm-生态)
- [第 6 章 AI Agent 相关库速览](#第-6-章-ai-agent-相关库速览)
- [第 7 章 常见报错与排查](#第-7-章-常见报错与排查)
- [第 8 章 学习路径建议](#第-8-章-学习路径建议)

---

## 第 1 章 心智模型转换

### 1.1 三个最大的思维差异

| Python 思维 | TS 思维 | 影响 |
|---|---|---|
| 运行时才报错 | **编译时**就报错（TS 的核心价值） | 大量错误写代码时就发现 |
| 类型是"装饰" | 类型是"合同" | 类型定义驱动设计 |
| 一个文件一个模块（默认） | 显式 `import/export` | 模块边界更清晰 |
| `pip install` 全局可用 | `pnpm install` 项目隔离 | 不会版本冲突 |
| `if __name__ == "__main__"` | `"type": "module"` + `tsx` | 入口方式不同 |

### 1.2 不要带过来的 Python 习惯

❌ **不要**用 `class` 表达一切——TS 用 interface/type 更多
❌ **不要**用 `dict` 当万能容器——TS 用具体类型
❌ **不要**用 `try/except` 处理所有错误——TS 区分 `Error` 和 `reject`
❌ **不要**用列表推导式——TS 用 `.map()/.filter()/.reduce()`
❌ **不要**等运行时调试——TS 重视编译时类型推断

### 1.3 必须带过来的好习惯

✅ 类型注解（TS 比 Python 更严格，更好用）
✅ 异步 `async/await`（语法几乎一样）
✅ 模块化设计（TS 强制你显式 export）
✅ 测试驱动（vitest 和 pytest 体验差不多）

---

## 第 2 章 环境搭建

### 2.1 装 Node.js 和 pnpm

```bash
# 装 Node.js 20+（推荐用 nvm 管理版本）
# macOS
brew install nvm
nvm install 20
nvm use 20

# Linux
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
nvm install 20

# Windows: 下载 https://nodejs.org/en/download/

# 验证
node --version   # v20.x.x
npm --version    # 10.x.x

# 装 pnpm（比 npm 快 3 倍）
npm install -g pnpm
pnpm --version
```

### 2.2 创建第一个 TS 项目

```bash
mkdir my-first-ts && cd my-first-ts
pnpm init

# 装 TypeScript 和运行时
pnpm add typescript tsx @types/node
pnpm tsc --init   # 生成 tsconfig.json
```

### 2.3 tsconfig.json（关键配置）

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ES2022",
    "moduleResolution": "bundler",
    "strict": true,                    // ← 严格模式，必开
    "esModuleInterop": true,
    "skipLibCheck": true,
    "outDir": "./dist",
    "rootDir": "./src",
    "resolveJsonModule": true,
    "allowImportingTsExtensions": true,
    "noEmit": true                     // 用 tsx 跑，不编译
  },
  "include": ["src/**/*"]
}
```

### 2.4 package.json 脚本

```json
{
  "name": "my-first-ts",
  "type": "module",                    // ← 用 ESM
  "scripts": {
    "dev": "tsx src/index.ts",         // 开发：直接跑 TS
    "build": "tsc",                    // 编译
    "start": "node dist/index.js",     // 生产：跑编译后
    "test": "vitest"
  }
}
```

### 2.5 第一个 Hello World

创建 `src/index.ts`：

```typescript
function greet(name: string): string {
  return `Hello, ${name}!`;
}

console.log(greet('World'));
```

跑：

```bash
pnpm dev
# 输出: Hello, World!
```

### 2.6 装 VS Code 插件（强烈推荐）

- **TypeScript REPL**: 内置类型检查
- **Biome**: 一体化 lint + format（替代 ESLint + Prettier）
- **Error Lens**: 错误直接显示在行末

---

## 第 3 章 TypeScript 语法对照 Python

### 3.1 变量声明

```python
# Python
x = 10              # 可变
PI = 3.14           # 约定不可变
name: str = "Tom"   # 带类型注解
```

```typescript
// TypeScript
let x = 10;              // 可变
const PI = 3.14;         // 真不可变
const name: string = 'Tom';  // 带类型注解
```

**关键差异**：
- TS 优先用 `const`，需要修改才用 `let`
- TS **没有** `var`（已经废弃）
- 类型注解可以省略，TS 会自动推断

### 3.2 基本类型

| Python | TypeScript | 备注 |
|---|---|---|
| `int` | `number` | TS 不区分 int/float |
| `float` | `number` | |
| `str` | `string` | |
| `bool` | `boolean` | |
| `list[T]` | `T[]` 或 `Array<T>` | |
| `dict[K, V]` | `Record<K, V>` | |
| `tuple[T1, T2]` | `[T1, T2]` | |
| `Optional[T]` | `T \| null` 或 `T \| undefined` | |
| `Any` | `any`（少用）或 `unknown`（推荐） | |
| `None` | `null` 或 `undefined` | TS 有两个！ |

**None vs null vs undefined**：

```typescript
let a: string | null = null;       // 显式说"没有值"
let b: string | undefined;          // 未赋值
let c: string | null | undefined;   // 两种都可能

// 检查
if (a == null) { ... }              // 同时检查 null 和 undefined
if (a === null) { ... }             // 只检查 null
```

### 3.3 函数

```python
# Python
def add(a: int, b: int = 0) -> int:
    return a + b

# lambda
square = lambda x: x * x
```

```typescript
// TypeScript
function add(a: number, b: number = 0): number {
  return a + b;
}

// 箭头函数（最常用）
const square = (x: number): number => x * x;

// 类型别名
type AddFn = (a: number, b: number) => number;
const add2: AddFn = (a, b) => a + b;   // 类型可以省略，会被推断
```

### 3.4 interface vs type

TS 有两种定义对象类型的方式，初学者常困惑。

```typescript
// interface: 描述对象形状
interface User {
  name: string;
  age: number;
  email?: string;          // 可选字段
}

// type: 更通用，可以表示任何类型
type User2 = {
  name: string;
  age: number;
  email?: string;
};

// 用法一样
const u: User = { name: 'Tom', age: 20 };
```

**用哪个**：MVP 阶段都用 `interface` 描述对象，用 `type` 描述联合类型/函数类型。

### 3.5 联合类型（Python 没有）

```typescript
type Status = 'pending' | 'success' | 'error';   // 字符串字面量联合
const s: Status = 'pending';                      // 只能是这三个值

type ID = string | number;                        // 多种类型
function findById(id: ID) {
  if (typeof id === 'string') {
    // 这里 id 被推断为 string
  } else {
    // 这里 id 被推断为 number
  }
}
```

**Python 没有这个**，这是 TS 的强项。

### 3.6 解构（Python 也有，但 TS 用得更多）

```python
# Python
user = {"name": "Tom", "age": 20}
name, age = user["name"], user["age"]

def get_user():
    return "Tom", 20
name, age = get_user()
```

```typescript
// TypeScript
const user = { name: 'Tom', age: 20 };
const { name, age } = user;              // 对象解构
const { name: userName, age: userAge } = user;  // 重命名

function getUser(): [string, number] {
  return ['Tom', 20];
}
const [name, age] = getUser();           // 数组解构

// 函数参数解构（极常用）
function greet({ name, age }: { name: string; age: number }) {
  console.log(`${name}, ${age}`);
}
greet({ name: 'Tom', age: 20 });
```

### 3.7 异步

```python
# Python
async def fetch_data():
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            return await resp.json()

# 并发
results = await asyncio.gather(fetch_data(), fetch_data())
```

```typescript
// TypeScript
async function fetchData() {
  const resp = await fetch(url);
  return resp.json();
}

// 并发
const [a, b] = await Promise.all([fetchData(), fetchData()]);
```

**几乎一样**！主要差异：
- Python 用 `asyncio.gather`，TS 用 `Promise.all`
- Python 需要 `asyncio.run()` 启动，Node 顶层可以直接 `await`

### 3.8 错误处理

```python
# Python
try:
    result = do_something()
except ValueError as e:
    print(f"值错误: {e}")
except Exception as e:
    print(f"其他错误: {e}")
finally:
    cleanup()
```

```typescript
// TypeScript
try {
  const result = doSomething();
} catch (e) {
  // TS 的 catch 默认是 unknown，需要类型收窄
  if (e instanceof Error) {
    console.log(`错误: ${e.message}`);
  } else {
    console.log(`其他: ${e}`);
  }
} finally {
  cleanup();
}
```

### 3.9 类

```python
# Python
class Dog:
    def __init__(self, name: str):
        self.name = name

    def bark(self) -> str:
        return f"{self.name} says woof"

d = Dog("Rex")
print(d.bark())
```

```typescript
// TypeScript
class Dog {
  constructor(public name: string) {}    // 参数属性：自动赋值

  bark(): string {
    return `${this.name} says woof`;
  }
}

const d = new Dog('Rex');
console.log(d.bark());
```

**TS 优势**：`constructor(public name: string)` 一行等于 Python 的 `self.name = name`。

### 3.10 Enum

```python
# Python
from enum import Enum

class Color(Enum):
    RED = "red"
    GREEN = "green"
```

```typescript
// TypeScript
enum Color {
  Red = 'red',
  Green = 'green',
}

// 或者用联合字面量（更推荐）
type Color = 'red' | 'green';
const c: Color = 'red';
```

### 3.11 泛型

```python
# Python
from typing import Generic, TypeVar

T = TypeVar('T')

def first(items: list[T]) -> T:
    return items[0]
```

```typescript
// TypeScript
function first<T>(items: T[]): T {
  return items[0];
}

// 使用
const n: number = first([1, 2, 3]);
const s: string = first(['a', 'b']);
```

---

## 第 4 章 Node.js 异步与标准库

### 4.1 文件系统

```python
# Python 同步
with open('file.txt', 'r') as f:
    content = f.read()

# Python 异步
import aiofiles
async with aiofiles.open('file.txt') as f:
    content = await f.read()
```

```typescript
// TypeScript（Node 内置，无需额外库）
import { readFile, writeFile } from 'node:fs/promises';

// 异步（推荐）
const content = await readFile('file.txt', 'utf-8');
await writeFile('output.txt', 'hello');

// 同步（极少用）
import { readFileSync } from 'node:fs';
const c = readFileSync('file.txt', 'utf-8');
```

### 4.2 路径处理

```python
# Python
import os
from pathlib import Path

p = Path('/home') / 'user' / 'file.txt'
print(p.name)        # file.txt
print(p.suffix)      # .txt
print(p.parent)      # /home/user
print(p.resolve())   # 绝对路径
```

```typescript
// TypeScript
import path from 'node:path';

const p = path.join('/home', 'user', 'file.txt');
console.log(path.basename(p));     // file.txt
console.log(path.extname(p));      // .txt
console.log(path.dirname(p));      // /home/user
console.log(path.resolve(p));      // 绝对路径
```

### 4.3 子进程

```python
# Python
import subprocess
result = subprocess.run(['ls', '-l'], capture_output=True, text=True)
print(result.stdout)
```

```typescript
// TypeScript
import { execSync, exec } from 'node:child_process';
import { promisify } from 'node:util';

const execAsync = promisify(exec);

// 同步
const output = execSync('ls -l', { encoding: 'utf-8' });
console.log(output);

// 异步（推荐）
const { stdout } = await execAsync('ls -l');
console.log(stdout);
```

### 4.4 环境变量

```python
# Python
import os
api_key = os.environ.get('API_KEY', '')
```

```typescript
// TypeScript
// 直接用 process.env，但建议用 dotenv 加载 .env
import 'dotenv/config';   // 一行搞定

const apiKey = process.env.API_KEY || '';
```

### 4.5 HTTP 请求

```python
# Python
import httpx
async with httpx.AsyncClient() as client:
    r = await client.get('https://api.example.com')
    data = r.json()
```

```typescript
// TypeScript（Node 18+ 内置 fetch）
const resp = await fetch('https://api.example.com');
const data = await resp.json();

// 或者用 axios（更强大）
import axios from 'axios';
const { data } = await axios.get('https://api.example.com');
```

---

## 第 5 章 包管理与 npm 生态

### 5.1 pnpm 常用命令对照

| 操作 | pip | pnpm |
|---|---|---|
| 装包 | `pip install requests` | `pnpm add axios` |
| 装开发依赖 | `pip install pytest` | `pnpm add -D vitest` |
| 全局装 | `pip install black` | `pnpm add -g prettier` |
| 卸载 | `pip uninstall requests` | `pnpm remove axios` |
| 看已装 | `pip list` | `pnpm list` |
| 跑脚本 | `python script.py` | `pnpm tsx script.ts` |
| 锁定依赖 | `pip freeze > requirements.txt` | `pnpm install`（自动生成 pnpm-lock.yaml） |

### 5.2 虚拟环境

```python
# Python
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

```typescript
// TypeScript/Node 不需要虚拟环境！
// pnpm 默认在 node_modules/ 目录里隔离
// 不同项目互不影响

pnpm install
```

### 5.3 package.json 的 scripts 字段

```json
{
  "scripts": {
    "dev": "tsx watch src/index.ts",
    "build": "tsc",
    "test": "vitest",
    "lint": "biome check src/",
    "format": "biome format src/ --write"
  }
}
```

跑：
```bash
pnpm dev      # 等于 pnpm run dev
pnpm test
pnpm build
```

### 5.4 常用包对照表

| Python | TypeScript | 用途 |
|---|---|---|
| `requests` / `httpx` | `axios` / 内置 `fetch` | HTTP 客户端 |
| `pydantic` | `zod` | 数据校验 |
| `pydantic-settings` | `dotenv` + `zod` | 配置管理 |
| `typer` / `click` | `commander` | CLI |
| `rich` | `chalk` + `ora` + `cli-table3` | 终端美化 |
| `pytest` | `vitest` | 测试 |
| `structlog` | `pino` / `winston` | 日志 |
| `python-dotenv` | `dotenv` | .env 加载 |
| `pathlib` | `node:path` | 路径处理 |
| `aiofiles` | `node:fs/promises` | 异步文件 |

---

## 第 6 章 AI Agent 相关库速览

### 6.1 Vercel AI SDK（`ai` 包）

**作用**：调 LLM、流式输出、工具调用。比 LangChain 简洁。

```bash
pnpm add ai @ai-sdk/openai zod
```

**核心 API**：

```typescript
import { generateText, streamText, tool } from 'ai';
import { openai } from '@ai-sdk/openai';
import { z } from 'zod';

// 1. 简单生成
const { text } = await generateText({
  model: openai('gpt-4o-mini'),
  prompt: '你好',
});

// 2. 带系统提示
const { text: t2 } = await generateText({
  model: openai('gpt-4o-mini'),
  system: '你是助手',
  messages: [{ role: 'user', content: '你好' }],
});

// 3. 流式
const { textStream } = await streamText({
  model: openai('gpt-4o-mini'),
  prompt: '写诗',
});
for await (const chunk of textStream) {
  process.stdout.write(chunk);
}

// 4. 工具调用
const { toolCalls, text: t3 } = await generateText({
  model: openai('gpt-4o-mini'),
  prompt: '看下 /tmp/test.txt',
  tools: {
    read_file: tool({
      description: '读取文件',
      parameters: z.object({
        path: z.string().describe('文件路径'),
      }),
      execute: async ({ path }) => {
        const { readFile } = await import('node:fs/promises');
        return readFile(path, 'utf-8');
      },
    }),
  },
});
```

### 6.2 LangGraph.js（`@langchain/langgraph`）

**作用**：状态机编排，和 Python 版 LangGraph 类似。

```bash
pnpm add @langchain/langgraph
```

```typescript
import { StateGraph, END, Annotation } from '@langchain/langgraph';

// 1. 定义状态
const State = Annotation.Root({
  messages: Annotation<string[]>({ default: () => [] }),
  intent: Annotation<{ complete: boolean }>(),
});

// 2. 节点函数
async function intakeNode(state: typeof State.State) {
  // 处理 state
  return { messages: [...state.messages, 'intake done'] };
}

// 3. 构建图
const graph = new StateGraph(State)
  .addNode('intake', intakeNode)
  .addNode('plan', planNode)
  .addEdge('__start__', 'intake')
  .addEdge('intake', 'plan')
  .addConditionalEdges('plan', (state) => {
    return state.intent.complete ? 'end' : 'intake';
  }, { end: END, intake: 'intake' })
  .compile();

// 4. 调用
const result = await graph.invoke({
  messages: ['你好'],
  intent: { complete: false },
});
```

### 6.3 MCP SDK（`@modelcontextprotocol/sdk`）

**作用**：作为 MCP Client 调用外部 MCP Server，或自己作为 MCP Server。

```bash
pnpm add @modelcontextprotocol/sdk
```

**作为 Client**：

```typescript
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js';

const transport = new StdioClientTransport({
  command: 'npx',
  args: ['-y', '@modelcontextprotocol/server-filesystem', '/tmp'],
});

const client = new Client(
  { name: 'devpilot', version: '1.0' },
  { capabilities: {} }
);

await client.connect(transport);

// 列出工具
const { tools } = await client.listTools();
console.log(tools);

// 调用工具
const result = await client.callTool({
  name: 'read_file',
  arguments: { path: '/tmp/test.txt' },
});
```

**作为 Server**：

```typescript
import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';

const server = new Server(
  { name: 'devpilot-mcp', version: '1.0' },
  { capabilities: { tools: {} } }
);

// 注册工具
server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [{
    name: 'ask_devpilot',
    description: '问 DevPilot',
    inputSchema: {
      type: 'object',
      properties: { question: { type: 'string' } },
      required: ['question'],
    },
  }],
}));

server.setRequestHandler(CallToolRequestSchema, async (req) => {
  const { name, arguments: args } = req.params;
  if (name === 'ask_devpilot') {
    // 调用你的 Agent
    const answer = await askAgent(args.question);
    return { content: [{ type: 'text', text: answer }] };
  }
});

// 启动
const transport = new StdioServerTransport();
await server.connect(transport);
```

### 6.4 Zod（数据校验）

**作用**：替代 Pydantic，运行时校验 + 类型推导。

```bash
pnpm add zod
```

```typescript
import { z } from 'zod';

// 1. 定义 schema
const UserSchema = z.object({
  name: z.string().min(1),
  age: z.number().int().positive(),
  email: z.string().email().optional(),
});

// 2. 类型自动推导
type User = z.infer<typeof UserSchema>;
// 等于 { name: string; age: number; email?: string }

// 3. 校验
const result = UserSchema.safeParse({ name: 'Tom', age: 20 });
if (result.success) {
  console.log(result.data);  // 类型安全
} else {
  console.log(result.error);  // 详细错误
}
```

### 6.5 Commander（CLI）

```bash
pnpm add commander @inquirer/prompts ora chalk
```

```typescript
import { Command } from 'commander';
import { input, confirm } from '@inquirer/prompts';
import ora from 'ora';
import chalk from 'chalk';

const program = new Command();

program
  .command('chat')
  .description('开始对话')
  .action(async () => {
    const name = await input({ message: '你叫什么？' });
    const spinner = ora('思考中...').start();
    await new Promise(r => setTimeout(r, 1000));
    spinner.succeed(chalk.green(`你好 ${name}!`));
  });

program.parse();
```

---

## 第 7 章 常见报错与排查

### 7.1 `Cannot find module 'xxx' or its corresponding type declarations`

**原因**：模块没装，或类型声明没装。

**修复**：
```bash
# 装包
pnpm add xxx

# 如果是 @types/xxx 形式
pnpm add -D @types/xxx
```

### 7.2 `Type 'string | undefined' is not assignable to type 'string'`

**原因**：可选字段可能为 undefined，直接用会报错。

**修复**：
```typescript
// 错
const name: string = user.name;   // user.name 是 string | undefined

// 对：1. 加默认值
const name: string = user.name ?? 'unknown';

// 对：2. 类型守卫
if (user.name) {
  const name: string = user.name;
}

// 对：3. 显式抛错
const name: string = user.name ?? throwError('name 必填');
```

### 7.3 `Object is possibly 'null'`

**原因**：可能为 null 的对象直接访问属性。

**修复**：
```typescript
// 错
console.log(user.name);   // user 可能是 null

// 对：1. 可选链
console.log(user?.name);

// 对：2. 类型守卫
if (user) {
  console.log(user.name);
}
```

### 7.4 `await is only valid in async functions`

**原因**：用了 await 但函数不是 async。

**修复**：
```typescript
// 错
function fetchUser() {
  const data = await fetch('/api/user');   // 报错
}

// 对
async function fetchUser() {
  const data = await fetch('/api/User');
}
```

### 7.5 `TypeError: Cannot read property 'xxx' of undefined`

**原因**：访问 undefined 的属性。常见于解构后没检查。

**修复**：用可选链 + 默认值：
```typescript
// 错
const name = response.data.user.name;

// 对
const name = response?.data?.user?.name ?? 'unknown';
```

### 7.6 ESM vs CommonJS 冲突

**症状**：`Cannot use import statement outside a module` 或 `require is not defined`

**原因**：混用了 `import` 和 `require`。

**修复**：统一用 ESM：
```json
// package.json
{
  "type": "module"
}
```

```typescript
// 全部用 import
import { readFile } from 'node:fs/promises';

// 不要用 require
// const fs = require('fs');   // ❌
```

### 7.7 `tsc` 编译慢

**原因**：每次都编译到 JS 再跑。

**修复**：用 `tsx` 直接跑 TS：
```bash
pnpm add -D tsx

# 直接跑，不编译
pnpm tsx src/index.ts

# 或者监听文件变化
pnpm tsx watch src/index.ts
```

### 7.8 路径 import 报错

**症状**：`import { xxx } from './utils'` 报错（找不到模块）

**原因**：TS 默认要带扩展名（ESM 规范）。

**修复**：
```typescript
// 错（CommonJS 习惯）
import { xxx } from './utils';

// 对（ESM）
import { xxx } from './utils/index.js';   // 注意 .js 后缀
// 或
import { xxx } from './utils.ts';         // tsx 支持

// 或者配置 bundler 模式（推荐）
// tsconfig.json:
// "moduleResolution": "bundler"
// 之后就能省后缀
```

---

## 第 8 章 学习路径建议

### 8.1 1 小时入门

1. 装好 Node + pnpm（10 分钟）
2. 创建第一个 TS 项目跑通 Hello World（15 分钟）
3. 读第 3 章 TypeScript 语法对照（20 分钟）
4. 读第 4 章 Node 标准库（15 分钟）

### 8.2 1 天上手

1. 上午：写一个 CLI 小工具（读文件 + 调 API + 输出）
2. 下午：装 Vercel AI SDK，调通一次 LLM + 工具调用

**最小练习**：

```typescript
// src/index.ts
import { generateText, tool } from 'ai';
import { openai } from '@ai-sdk/openai';
import { z } from 'zod';
import { readFile } from 'node:fs/promises';
import { Command } from 'commander';

const program = new Command();

program.command('ask <question>').action(async (question: string) => {
  const { text } = await generateText({
    model: openai('gpt-4o-mini'),
    prompt: question,
    tools: {
      read_file: tool({
        description: '读取文件',
        parameters: z.object({ path: z.string() }),
        execute: async ({ path }) => readFile(path, 'utf-8'),
      }),
    },
  });
  console.log(text);
});

program.parse();
```

跑：
```bash
pnpm tsx src/index.ts ask "看下 package.json"
```

### 8.3 1 周熟练

按 [DevPilot-TS 设计文档](./devpilot-ts-design.md) 的阶段 1-2 做：
- 阶段 1：单 Agent MVP
- 阶段 2：记忆层

做完这两阶段，你就基本熟练了 TS + Node + AI SDK + LangGraph 的组合。

### 8.4 学习资源

| 资源 | 用途 |
|---|---|
| [TypeScript Handbook](https://www.typescriptlang.org/docs/handbook/) | 官方文档，1 天读完 |
| [Node.js 官方文档](https://nodejs.org/docs/latest/api/) | 标准库参考 |
| [Vercel AI SDK 文档](https://sdk.vercel.ai/docs) | AI SDK 权威 |
| [LangGraph.js 文档](https://langchain-ai.github.io/langgraphjs/) | 状态机 |
| [MCP 文档](https://modelcontextprotocol.io/) | MCP 协议 |
| [Total TypeScript](https://www.totaltypescript.com/) | 进阶 TS |

### 8.5 心态调整

1. **不要怕编译错误**：TS 编译错误是好事，帮你提前发现问题
2. **不要追求完美类型**：先用 `any` 跑通，再逐步加类型
3. **不要照搬 Python 习惯**：列表推导、字典推导在 TS 没有等价物
4. **善用 `pnpm tsx`**：开发时不需要编译，直接跑 TS
5. **学会读类型定义**：VS Code 鼠标悬停看类型，按 F12 跳转到定义

---

## 附录：Python → TS 速查表

```python
# === Python ===
from typing import Optional
import asyncio
import os

class User:
    def __init__(self, name: str, age: Optional[int] = None):
        self.name = name
        self.age = age

async def fetch_user(user_id: str) -> User:
    async with httpx.AsyncClient() as client:
        r = await client.get(f"/api/users/{user_id}")
        data = r.json()
        return User(name=data["name"], age=data.get("age"))

async def main():
    user = await fetch_user("123")
    print(f"{user.name}, {user.age}")

if __name__ == "__main__":
    asyncio.run(main())
```

```typescript
// === TypeScript ===
import httpx from 'node:fetch'  // 没这玩意，用内置 fetch

interface User {
  name: string;
  age?: number;  // 可选
}

async function fetchUser(userId: string): Promise<User> {
  const r = await fetch(`/api/users/${userId}`);
  const data = await r.json() as { name: string; age?: number };
  return { name: data.name, age: data.age };
}

async function main(): Promise<void> {
  const user = await fetchUser('123');
  console.log(`${user.name}, ${user.age ?? 'unknown'}`);
}

main();
```

**关键差异**：
1. 类型用 `interface`，构造逻辑用工厂函数（不一定非要 class）
2. `Optional[X]` → `X?` 或 `X | undefined`
3. `asyncio.run(main())` → 直接 `main()`（Node 顶层可以 await）
4. `httpx` → 内置 `fetch`
5. 字符串格式化 `f"{x}"` → 模板字符串 `` `${x}` ``

---

## 最后的话

从 Python 转 TS + Node 最大的不适应是：
1. **类型系统严格**——会经常被编译器骂，但习惯了就离不开
2. **生态分散**——一个功能可能要装 3-5 个包（Python 通常一两个）
3. **异步无处不在**——但语法和 Python 几乎一样

熬过前 3 天的不适，你会发现 TS + Node 在 AI Agent 开发上比 Python 更顺手——尤其涉及 streaming、CLI 工具、MCP 时。

加油！🚀

---
*AI生成*
