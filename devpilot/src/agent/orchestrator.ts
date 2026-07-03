import { generateText } from "ai";
import { config } from "../config.js";
import { createLLM } from "../infra/llm-factory.js";
import { readFileTool } from "../tools/local/file-ops.js";
import { runCmdTool } from "../tools/local/shell.js";
import { AGENT_PROMPTS } from "./prompts.js";
import { logger } from "../logger.js";
import type { Message } from "../types.js";

interface OrchestratorResult {
  type: "SIMPLE" | "CODE";
  plan: string;
}

/**
 * Orchestrator agent: analyzes the user's task and decides whether
 * it's a SIMPLE request (direct answer) or a CODE task (needs coder + reviewer).
 *
 * Has read_file and run_cmd access so it can handle simple queries
 * (read a file, check a directory) without invoking the full coder pipeline.
 */
export async function orchestratorNode(state: {
  task: string;
  messages: Message[];
  coderOutput: string;
  reviewResult: string;
  retryCount: number;
  needsReview: boolean;
  finalOutput: string;
}) {
  logger.agent("Orchestrator", "Analyzing task...");

  const llm = createLLM(config);

  // Build context from conversation history for better decisions
  const recentHistory = state.messages?.slice(-6) ?? [];
  const historyContext = recentHistory.length > 0
    ? recentHistory.map(m => `[${m.role}] ${m.content.slice(0, 300)}`).join("\n")
    : "";

  const systemPrompt = AGENT_PROMPTS.orchestrator
    + (historyContext ? `\n\nRecent conversation history:\n${historyContext}` : "");

  const result = await generateText({
    model: llm,
    system: systemPrompt,
    prompt: `User request: ${state.task}`,
    tools: {
      read_file: readFileTool,
      run_cmd: runCmdTool,
    },
    maxTokens: 2000,
    maxSteps: 5,
  });

  const text = result.text;
  const parsed = parseOrchestratorOutput(text);

  logger.agent("Orchestrator", `Decision: ${parsed.type}`);

  if (parsed.type === "SIMPLE") {
    return {
      task: state.task,
      messages: state.messages,
      needsReview: false,
      finalOutput: parsed.plan,
      coderOutput: "",
      reviewResult: "",
      retryCount: 0,
    };
  }

  return {
    task: `${state.task}\n\nSpecification:\n${parsed.plan}`,
    messages: state.messages,
    needsReview: true,
    finalOutput: "",
    coderOutput: "",
    reviewResult: "",
    retryCount: 0,
  };
}

function parseOrchestratorOutput(text: string): OrchestratorResult {
  const typeMatch = text.match(/TYPE:\s*(SIMPLE|CODE)/i);
  const planMatch = text.match(/PLAN:\s*([\s\S]*)/i);

  return {
    type: (typeMatch?.[1]?.toUpperCase() === "CODE" ? "CODE" : "SIMPLE"),
    plan: planMatch?.[1]?.trim() || text,
  };
}
