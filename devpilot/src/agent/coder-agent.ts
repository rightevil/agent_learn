import { config } from "../config.js";
import { createLLM } from "../infra/llm-factory.js";
import { AGENT_PROMPTS } from "./prompts.js";
import { registry } from "../tools/types.js";
import { logger } from "../logger.js";
import { loadProfile } from "../memory/user-profile.js";
import { generateFull } from "../utils/stream.js";
import type { Message } from "../types.js";

export async function coderNode(state: {
  task: string;
  messages: Message[];
  coderOutput: string;
  reviewResult: string;
  retryCount: number;
  needsReview: boolean;
  finalOutput: string;
}) {
  logger.agent("Coder", "Generating...");

  const profile = loadProfile();
  const llm = createLLM(config, {
    enableReasoning: config.LLM_PROVIDER !== "openai",
    reasoningEffort: "max",
  });

  const tools = registry.toAITools();

  let prompt = `Task:\n${state.task}`;
  if (state.reviewResult && state.retryCount > 0) {
    prompt += `\n\nPrevious review feedback (attempt ${state.retryCount}):\n${state.reviewResult}\n\nPlease fix the issues.`;
  }

  const styleHint = profile.initialized
    ? `\n\nUser preferences: language=${profile.language}, style=${profile.codeStyle}`
    : "";

  const recentMsgs = (state.messages ?? []).slice(-4);
  const contextMessages = recentMsgs.map(m => ({
    role: m.role as "user" | "assistant" | "system",
    content: m.content.slice(0, 500),
  }));

  const text = await generateFull(llm, {
    system: AGENT_PROMPTS.coder + styleHint,
    messages: [
      ...contextMessages,
      { role: "user", content: prompt },
    ],
    tools,
    maxTokens: config.LLM_MAX_OUTPUT_TOKENS,
    maxSteps: 10,
  });

  logger.agent("Coder", `Generated ${text.length} chars`);

  return {
    task: state.task,
    messages: state.messages,
    coderOutput: text,
    reviewResult: state.reviewResult,
    retryCount: state.retryCount,
    needsReview: state.needsReview,
    finalOutput: state.finalOutput,
  };
}
