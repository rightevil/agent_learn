import { generateText } from "ai";
import { config } from "../config.js";
import { createLLM } from "../infra/llm-factory.js";
import { readFileTool } from "../tools/local/file-ops.js";
import { AGENT_PROMPTS } from "./prompts.js";
import { logger } from "../logger.js";

interface ReviewResult {
  verdict: "PASS" | "NEEDS_WORK";
  issues: string;
}

/**
 * Reviewer agent: reviews code produced by the Coder agent.
 * Returns PASS if code is acceptable, NEEDS_WORK if rework is required.
 */
export async function reviewerNode(state: {
  task: string;
  coderOutput: string;
  reviewResult: string;
  retryCount: number;
  needsReview: boolean;
  finalOutput: string;
}) {
  logger.agent("Reviewer", "Reviewing code...");

  const llm = createLLM(config);

  const result = await generateText({
    model: llm,
    system: AGENT_PROMPTS.reviewer,
    prompt: `Task specification:\n${state.task}\n\nCode to review:\n${state.coderOutput}`,
    tools: {
      read_file: readFileTool,
    },
    maxTokens: 2000,
    maxSteps: 3,
  });

  const parsed = parseReviewOutput(result.text);
  logger.agent("Reviewer", `Verdict: ${parsed.verdict}`);

  if (parsed.verdict === "PASS") {
    return {
      task: state.task,
      coderOutput: state.coderOutput,
      reviewResult: "PASS",
      retryCount: state.retryCount,
      needsReview: state.needsReview,
      finalOutput: `Code generated successfully.\n\n${state.coderOutput}\n\nReview: PASS\n${parsed.issues}`,
    };
  }

  return {
    task: state.task,
    coderOutput: state.coderOutput,
    reviewResult: `NEEDS_WORK\n${parsed.issues}`,
    retryCount: state.retryCount + 1,
    needsReview: state.needsReview,
    finalOutput: "",
  };
}

function parseReviewOutput(text: string): ReviewResult {
  const verdictMatch = text.match(/VERDICT:\s*(PASS|NEEDS_WORK)/i);
  const issuesMatch = text.match(/ISSUES:\s*([\s\S]*?)(?:SUGGESTIONS:|$)/i);

  const verdict = verdictMatch?.[1]?.toUpperCase() === "PASS" ? "PASS" : "NEEDS_WORK";
  const issues = issuesMatch?.[1]?.trim() || text;

  return { verdict, issues };
}

export const MAX_RETRIES = 3;
