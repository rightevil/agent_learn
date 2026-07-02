import type { Message } from "../types.js";
import { config } from "../config.js";

const DEFAULT_MAX_TURNS = 10;
const KEEP_RECENT = 2;

/**
 * Determine if the conversation should be summarized based on the
 * number of message turns and the configured max output tokens.
 *
 * DeepSeek-V4 has a 1M context window, so compression is rarely needed.
 * Agnes has 512K, which is still generous. We adjust the threshold based
 * on LLM_MAX_OUTPUT_TOKENS — smaller models benefit from earlier compression.
 */
export function shouldSummarize(messageCount: number): boolean {
  const maxTurns = config.LLM_MAX_OUTPUT_TOKENS > 32000
    ? 30   // Large context models: summarize very late
    : DEFAULT_MAX_TURNS;

  return messageCount > maxTurns;
}

/**
 * Build a summarization prompt for the conversation history.
 * Keeps the last KEEP_RECENT turns intact and asks the LLM to
 * summarize everything before that.
 */
export function buildSummarizationPrompt(messages: Message[]): {
  toSummarize: Message[];
  toKeep: Message[];
} {
  if (messages.length <= KEEP_RECENT) {
    return { toSummarize: [], toKeep: messages };
  }

  const splitPoint = Math.max(0, messages.length - KEEP_RECENT);
  return {
    toSummarize: messages.slice(0, splitPoint),
    toKeep: messages.slice(splitPoint),
  };
}

/**
 * Create a compact summary string from a list of messages.
 * This is a lightweight client-side summary; for better results,
 * the LLM should be invoked with the summarization prompt.
 */
export function compactMessages(messages: Message[]): string {
  if (messages.length === 0) return "";

  const lines = messages.map((m) => {
    const preview = m.content.slice(0, 200).replace(/\n/g, " ");
    return `[${m.role}] ${preview}${m.content.length > 200 ? "..." : ""}`;
  });

  return lines.join("\n");
}
