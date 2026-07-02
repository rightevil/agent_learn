import { generateText } from "ai";
import { config } from "../config.js";
import { createLLM } from "../infra/llm-factory.js";
import { readFileTool, writeFileTool } from "../tools/local/file-ops.js";
import { runCmdTool } from "../tools/local/shell.js";
import { AGENT_PROMPTS } from "./prompts.js";
import { logger } from "../logger.js";
import { loadProfile } from "../memory/user-profile.js";

/**
 * Coder agent: generates code based on the task specification.
 * Has access to file and shell tools.
 */
export async function coderNode(state: {
  task: string;
  coderOutput: string;
  reviewResult: string;
  retryCount: number;
  needsReview: boolean;
  finalOutput: string;
}) {
  logger.agent("Coder", "Generating code...");

  const profile = loadProfile();
  const llm = createLLM(config, {
    enableReasoning: config.LLM_PROVIDER !== "openai",
    reasoningEffort: "max",
  });

  // Build the prompt with any reviewer feedback from previous attempts
  let prompt = `Task:\n${state.task}`;

  if (state.reviewResult && state.retryCount > 0) {
    prompt += `\n\nPrevious review feedback (attempt ${state.retryCount}):\n${state.reviewResult}\n\nPlease fix the issues and regenerate the code.`;
  }

  const styleHint = profile.initialized
    ? `\n\nUser preferences: language=${profile.language}, style=${profile.codeStyle}`
    : "";

  const result = await generateText({
    model: llm,
    system: AGENT_PROMPTS.coder + styleHint,
    prompt,
    tools: {
      read_file: readFileTool,
      write_file: writeFileTool,
      run_cmd: runCmdTool,
    },
    maxTokens: config.LLM_MAX_OUTPUT_TOKENS,
    maxSteps: 10,
  });

  logger.agent("Coder", `Generated ${result.text.length} chars`);

  if (result.toolCalls?.length) {
    for (const tc of result.toolCalls) {
      logger.tool(tc.toolName, JSON.stringify(tc.args).slice(0, 120));
    }
  }

  return {
    task: state.task,
    coderOutput: result.text,
    reviewResult: state.reviewResult,
    retryCount: state.retryCount,
    needsReview: state.needsReview,
    finalOutput: state.finalOutput,
  };
}
