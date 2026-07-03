import { Annotation } from "@langchain/langgraph";
import type { Message } from "../types.js";

/**
 * AgentState defines the shared state that flows through the
 * orchestrator → coder → reviewer pipeline.
 */
export const AgentStateAnnotation = Annotation.Root({
  /** The user's original request */
  task: Annotation<string>,

  /** Full conversation history (optional, for context-aware decisions) */
  messages: Annotation<Message[]>,

  /** The code produced by the Coder agent */
  coderOutput: Annotation<string>,

  /** The review result from the Reviewer agent */
  reviewResult: Annotation<string>,

  /** Number of rework attempts (coder → reviewer loop) */
  retryCount: Annotation<number>,

  /** Whether the orchestrator decided to use a reviewer */
  needsReview: Annotation<boolean>,

  /** Final output to show the user */
  finalOutput: Annotation<string>,
});
