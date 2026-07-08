#!/usr/bin/env node
import { Command } from "commander";
import ora from "ora";
import chalk from "chalk";
import { input, select } from "@inquirer/prompts";
import { generateText } from "ai";
import { randomUUID } from "node:crypto";
import { config } from "./config.js";
import { logger } from "./logger.js";
import {
  saveConversation,
  loadConversation,
  listConversations,
  resolveConversationId,
} from "./memory/short-term.js";
import { loadProfile, saveProfile } from "./memory/user-profile.js";
import type { Message, UserProfile } from "./types.js";
import { runAgentPipeline } from "./agent/graph.js";
import { addMemory, findSimilarTasks } from "./memory/long-term.js";
import { streamFull, typewriter } from "./utils/stream.js";
import { createLLM } from "./infra/llm-factory.js";
import { AGENT_PROMPTS } from "./agent/prompts.js";
import { registry } from "./tools/types.js";

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

/**
 * Run with streaming: SIMPLE → real streamText, CODE → graph + typewriter.
 */
async function runWithStreaming(
  task: string,
  messages: Message[],
  profile: UserProfile,
  spinner: ReturnType<typeof ora>,
): Promise<string> {
  // Quick orchestrator call to decide SIMPLE vs CODE
  const llm = createLLM(config);
  const orchResult = await generateText({
    model: llm,
    system: AGENT_PROMPTS.orchestrator,
    prompt: `User request: ${task}`,
    maxTokens: 300,
  });

  const isCode = /TYPE:\s*CODE/i.test(orchResult.text);

  if (!isCode) {
    // SIMPLE → real streaming: tokens appear as LLM generates them
    let headerPrinted = false;
    const fullText = await streamFull(llm, {
      system: AGENT_PROMPTS.base(profile),
      messages,
      tools: registry.toAITools(),
      maxTokens: config.LLM_MAX_OUTPUT_TOKENS,
      maxSteps: 10,
      onFirstChunk: () => spinner.stop(),
      onChunk: async (chunk) => {
        if (!headerPrinted) {
          process.stdout.write(`\n${chalk.bold("DevPilot:")}\n`);
          headerPrinted = true;
        }
        process.stdout.write(chunk);
        await new Promise(r => setTimeout(r, 5));
      },
    });
    process.stdout.write("\n\n");
    return fullText;
  }

  // CODE → LangGraph pipeline + typewriter output
  const result = await runAgentPipeline(task, messages);
  spinner.stop();
  process.stdout.write(`\n${chalk.bold("DevPilot:")}\n`);
  await typewriter(result);
  process.stdout.write("\n\n");
  return result;
}

async function main(
  prompt: string | undefined,
  options: { file?: string; model?: string; continue?: string }
) {
  const profile = await ensureProfile();

  // --- Load or create conversation ---
  let convId = options.continue;
  if (convId) {
    const resolved = resolveConversationId(convId);
    if (resolved) convId = resolved;
  }
  convId = convId || randomUUID();
  const existingConv = loadConversation(convId);

  if (options.model) {
    // model override is noted but pipeline uses config directly
    logger.info(`Provider: ${config.LLM_PROVIDER} | Model override: ${options.model}`);
  }

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
    await interactiveSession(profile, convId, existingConv?.messages ?? []);
    return;
  }

  // --- Assemble messages with memory ---
  const historyMessages = existingConv?.messages ?? [];
  const allMessages: Message[] = [
    ...historyMessages,
    { role: "user", content: userMessage },
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

  const spinner = ora("DevPilot is thinking...").start();

  try {
    const output = await runWithStreaming(userMessage, allMessages, profile, spinner);
    spinner.stop();

    // Save conversation
    const updatedMessages: Message[] = [
      ...allMessages,
      { role: "assistant", content: output },
    ];
    saveConversation(convId, updatedMessages);
    logger.info(`Conversation saved (id: ${convId})`);

    // Save to long-term memory
    addMemory(userMessage, output).catch(() => {});
  } catch (error) {
    spinner.stop();
    throw error;
  }
}

async function interactiveSession(
  profile: UserProfile,
  convId: string,
  existingMessages: Message[]
) {
  logger.success("Welcome to DevPilot! (type /exit to quit, /help for commands)");

  const messages: Message[] = [...existingMessages];

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

    const spinner = ora("DevPilot is thinking...").start();

    try {
      const output = await runWithStreaming(userInput, messages, profile, spinner);
      spinner.stop();

      messages.push({ role: "assistant", content: output });
      addMemory(userInput, output).catch(() => {});
    } catch (error) {
      spinner.stop();
      logger.error(error instanceof Error ? error.message : String(error));
    }
  }
}

async function ensureProfile(): Promise<UserProfile> {
  let profile = loadProfile();

  if (!profile.initialized) {
    console.log(chalk.bold("\nWelcome to DevPilot! Let's set up your preferences.\n"));

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
