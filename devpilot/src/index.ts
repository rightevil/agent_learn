#!/usr/bin/env node
import { Command } from "commander";
import ora from "ora";
import chalk from "chalk";
import { input, select, confirm } from "@inquirer/prompts";
import { generateText, type CoreTool } from "ai";
import { randomUUID } from "node:crypto";
import { config } from "./config.js";
import { createLLM } from "./infra/llm-factory.js";
import { readFileTool, writeFileTool } from "./tools/local/file-ops.js";
import { runCmdTool } from "./tools/local/shell.js";
import { AGENT_PROMPTS } from "./agent/prompts.js";
import { logger } from "./logger.js";
import {
  saveConversation,
  loadConversation,
  listConversations,
  resolveConversationId,
} from "./memory/short-term.js";
import { loadProfile, saveProfile, isFirstRun } from "./memory/user-profile.js";
import { shouldSummarize, buildSummarizationPrompt, compactMessages } from "./memory/summarizer.js";
import type { Message, UserProfile } from "./types.js";
import { confirmWrite } from "./utils/confirm.js";
import { runAgentPipeline } from "./agent/graph.js";
import { mcpManager } from "./tools/mcp-client.js";
import { mcpToolsToAITools } from "./tools/mcp-adapter.js";
import { addMemory, findSimilarTasks } from "./memory/long-term.js";

const program = new Command();

program
  .name("devpilot")
  .description("DevPilot-TS — AI coding assistant")
  .version("0.1.0")
  .argument("[prompt]", "What do you want DevPilot to do?")
  .option("-f, --file <path>", "Read and analyze a specific file")
  .option("-m, --model <model>", "Override the LLM model")
  .option("-i, --interactive", "Start interactive session")
  .option("-c, --continue <id>", "Continue a previous conversation")
  .option("--list", "List previous conversations")
  .option("--multi", "Use multi-agent pipeline (orchestrator + coder + reviewer)")
  .option("--mcp", "Enable MCP server connections")
  .action(async (prompt, options) => {
    try {
      if (options.list) {
        showConversationList();
        return;
      }
      await main(prompt, options);
    } catch (error) {
      logger.error(error instanceof Error ? error.message : String(error));
      process.exit(1);
    }
  });

function showConversationList() {
  const conversations = listConversations();
  if (conversations.length === 0) {
    logger.info("No previous conversations found.");
    return;
  }
  console.log(chalk.bold("\nPrevious conversations:"));
  for (const conv of conversations) {
    const msgCount = conv.messages.length;
    const preview = conv.messages[0]?.content.slice(0, 60) ?? "(empty)";
    console.log(
      `  ${chalk.cyan(conv.id)}  ${conv.updatedAt}  ${msgCount} msgs  "${preview}..."`
    );
  }
  console.log();
}

async function buildTools(enableMcp: boolean): Promise<Record<string, CoreTool>> {
  const tools: Record<string, CoreTool> = {
    read_file: readFileTool,
    write_file: writeFileTool,
    run_cmd: runCmdTool,
  };

  if (enableMcp) {
    if (!mcpManager.isConnected) {
      await mcpManager.connect();
    }
    if (mcpManager.isConnected) {
      const mcpTools = mcpToolsToAITools();
      Object.assign(tools, mcpTools);
      logger.info(`MCP tools loaded: ${Object.keys(mcpTools).join(", ") || "none"}`);
    }
  }

  return tools;
}

async function main(prompt: string | undefined, options: { file?: string; model?: string; continue?: string; multi?: boolean; mcp?: boolean }) {
  // --- First-run onboarding ---
  const profile = await ensureProfile();

  // --- Multi-agent mode ---
  if (options.multi && prompt) {
    await runMultiAgent(prompt, profile);
    return;
  }

  // --- Load or create conversation ---
  let convId = options.continue;
  if (convId) {
    const resolved = resolveConversationId(convId);
    if (resolved) {
      convId = resolved;
    }
    // If no match found, treat the short id as a new conversation id
  }
  convId = convId || randomUUID();
  const existingConv = loadConversation(convId);

  const modelName = options.model || config.LLM_MODEL;
  logger.info(`Provider: ${config.LLM_PROVIDER} | Model: ${modelName}`);

  if (existingConv) {
    logger.info(`Continuing conversation ${convId} (${existingConv.messages.length} messages)`);
  }

  // --- Build the user message ---
  let userMessage: string;
  if (options.file) {
    userMessage = `Please read and analyze the file at "${options.file}". Summarize its contents and tell me what it does.`;
  } else if (prompt) {
    userMessage = prompt;
  } else {
    // No prompt and no file → interactive mode
    await interactiveSession(profile, convId, existingConv?.messages ?? [], options.mcp || false);
    return;
  }

  // --- Single-shot mode ---
  const historyMessages = existingConv?.messages ?? [];
  const allMessages: Message[] = [
    ...historyMessages,
    { role: "user" as const, content: userMessage },
  ];

  // Long-term memory: find similar past tasks
  const similarTasks = findSimilarTasks(userMessage, 3);
  if (similarTasks.length > 0) {
    const context = similarTasks
      .map((m) => `- Task: ${m.task.slice(0, 200)}\n  Solution: ${m.solution.slice(0, 300)}`)
      .join("\n");
    allMessages.unshift({
      role: "system",
      content: `[Relevant past tasks from long-term memory]\n${context}`,
    });
    logger.info(`Found ${similarTasks.length} similar past task(s)`);
  }

  // Summarize old messages if needed
  const messages = [...allMessages];
  if (shouldSummarize(messages.length)) {
    const { toSummarize, toKeep } = buildSummarizationPrompt(messages);
    if (toSummarize.length > 0) {
      logger.info(`Compressing ${toSummarize.length} old messages...`);
      const summary = compactMessages(toSummarize);
      const summaryMsg: Message = { role: "system", content: `[Previous conversation summary]\n${summary}` };
      messages.splice(0, toSummarize.length, summaryMsg);
    }
  }

  const llm = createLLM({ ...config, LLM_MODEL: modelName }, {
    enableReasoning: config.LLM_PROVIDER !== "openai",
    reasoningEffort: "high",
  });

  const spinner = ora("DevPilot is thinking...").start();

  try {
    const result = await generateText({
      model: llm,
      system: AGENT_PROMPTS.base(profile),
      messages,
      tools: await buildTools(options.mcp || false),
      maxTokens: config.LLM_MAX_OUTPUT_TOKENS,
      maxSteps: 10,
    });

    spinner.stop();

    // Display tool calls
    if (result.toolCalls && result.toolCalls.length > 0) {
      for (const tc of result.toolCalls) {
        logger.tool(tc.toolName, JSON.stringify(tc.args).slice(0, 120));
      }
    }

    // Display response
    console.log();
    console.log(chalk.bold("DevPilot:"));
    console.log(result.text);
    console.log();

    // Save conversation
    const updatedMessages: Message[] = [
      ...allMessages,
      { role: "assistant", content: result.text },
    ];
    saveConversation(convId, updatedMessages);
    logger.info(`Conversation saved (id: ${convId})`);

    // Save to long-term memory for future cross-session recall
    addMemory(userMessage, result.text).catch(() => {});

    if (result.usage) {
      logger.info(`Tokens: ${result.usage.totalTokens} (prompt: ${result.usage.promptTokens}, completion: ${result.usage.completionTokens})`);
    }
  } catch (error) {
    spinner.stop();
    throw error;
  }
}

async function interactiveSession(
  profile: UserProfile,
  convId: string,
  existingMessages: Message[],
  enableMcp: boolean
) {
  logger.success("Welcome to DevPilot! (type /exit to quit, /help for commands)");

  const messages = [...existingMessages];

  while (true) {
    const userInput = await input({ message: "you:" });

    if (!userInput.trim()) continue;
    if (userInput === "/exit") {
      saveConversation(convId, messages);
      logger.info(`Conversation saved (id: ${convId}). Goodbye!`);
      break;
    }
    if (userInput === "/help") {
      console.log("  /exit  - quit session");
      console.log("  /help  - show this help");
      console.log("  /clear - clear current conversation");
      continue;
    }
    if (userInput === "/clear") {
      messages.length = 0;
      logger.info("Conversation cleared.");
      continue;
    }

    messages.push({ role: "user", content: userInput });

    // Summarize if needed
    if (shouldSummarize(messages.length)) {
      const { toSummarize, toKeep } = buildSummarizationPrompt(messages);
      if (toSummarize.length > 0) {
        const summary = compactMessages(toSummarize);
        const summaryMsg: Message = { role: "system", content: `[Summary]\n${summary}` };
        messages.splice(0, toSummarize.length, summaryMsg);
      }
    }

    const llm = createLLM(config, {
      enableReasoning: config.LLM_PROVIDER !== "openai",
      reasoningEffort: "high",
    });

    const spinner = ora("DevPilot is thinking...").start();

    try {
      const result = await generateText({
        model: llm,
        system: AGENT_PROMPTS.base(profile),
        messages,
        tools: await buildTools(enableMcp),
        maxTokens: config.LLM_MAX_OUTPUT_TOKENS,
        maxSteps: 10,
      });

      spinner.stop();

      if (result.toolCalls?.length) {
        for (const tc of result.toolCalls) {
          logger.tool(tc.toolName, JSON.stringify(tc.args).slice(0, 120));
        }
      }

      console.log();
      console.log(chalk.bold("DevPilot:"));
      console.log(result.text);
      console.log();

      messages.push({ role: "assistant", content: result.text });

      // Save to long-term memory
      addMemory(userInput, result.text).catch(() => {});
    } catch (error) {
      spinner.stop();
      logger.error(error instanceof Error ? error.message : String(error));
    }
  }
}

async function runMultiAgent(task: string, profile: UserProfile) {
  const spinner = ora("DevPilot multi-agent pipeline running...").start();

  try {
    logger.agent("Orchestrator", "Starting multi-agent pipeline...");
    const result = await runAgentPipeline(task);

    spinner.stop();
    console.log();
    console.log(chalk.bold("DevPilot (Multi-Agent):"));
    console.log(result);
    console.log();
  } catch (error) {
    spinner.stop();
    throw error;
  }
}

async function ensureProfile(): Promise<UserProfile> {
  let profile = loadProfile();

  if (!profile.initialized) {
    console.log(chalk.bold("\n👋 Welcome to DevPilot! Let's set up your preferences.\n"));

    profile.language = await select({
      message: "Your primary language?",
      choices: [
        { name: "TypeScript", value: "typescript" },
        { name: "JavaScript", value: "javascript" },
        { name: "Python", value: "python" },
        { name: "Go", value: "go" },
        { name: "Rust", value: "rust" },
      ],
    });

    profile.testFramework = await select({
      message: "Your preferred test framework?",
      choices: [
        { name: "vitest", value: "vitest" },
        { name: "jest", value: "jest" },
        { name: "pytest", value: "pytest" },
        { name: "go test", value: "go-test" },
        { name: "none", value: "none" },
      ],
    });

    profile.codeStyle = await input({
      message: "Code style preferences?",
      default: "standard conventions",
    });

    profile.initialized = true;
    await saveProfile(profile);
    logger.success("Preferences saved! You can change them anytime in data/profile.json\n");
  }

  return profile;
}

program.parse();
