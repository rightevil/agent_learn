import { generateText } from "ai";
import { config } from "../config.js";
import { createLLM } from "../infra/llm-factory.js";
import { readFileTool, writeFileTool } from "../tools/local/file-ops.js";
import { runCmdTool } from "../tools/local/shell.js";
import { AGENT_PROMPTS } from "./prompts.js";
import { logger } from "../logger.js";

interface OrchestratorResult {
  type: "SIMPLE" | "CODE";
  plan: string;
}

/**
 * Orchestrator agent: analyzes the user's task and decides whether
 * it's a SIMPLE request (direct answer) or a CODE task (needs coder + reviewer).
 */
export async function orchestratorNode(state: {
  task: string;
  coderOutput: string;
  reviewResult: string;
  retryCount: number;
  needsReview: boolean;
  finalOutput: string;
}) {
  logger.agent("Orchestrator", "Analyzing task...");

  const llm = createLLM(config);

  const result = await generateText({
    model: llm,
    system: AGENT_PROMPTS.orchestrator,
    prompt: `User request: ${state.task}`,
    maxTokens: 1000,
  });

  const text = result.text;
  const parsed = parseOrchestratorOutput(text);

  logger.agent("Orchestrator", `Decision: ${parsed.type}`);

  if (parsed.type === "SIMPLE") {
    return {
      task: state.task,
      needsReview: false,
      finalOutput: parsed.plan,
      coderOutput: "",
      reviewResult: "",
      retryCount: 0,
    };
  }

  return {
    task: `${state.task}\n\nSpecification:\n${parsed.plan}`,
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
