import { StateGraph, START, END } from "@langchain/langgraph";
import { AgentStateAnnotation } from "./state.js";
import { orchestratorNode } from "./orchestrator.js";
import { coderNode } from "./coder-agent.js";
import { reviewerNode, MAX_RETRIES } from "./reviewer-agent.js";
import { logger } from "../logger.js";
import type { Message } from "../types.js";

/**
 * Decide what to do after the orchestrator analyzes the task.
 * - SIMPLE tasks go directly to END
 * - CODE tasks go to the coder
 */
function afterOrchestrator(state: {
  task: string;
  needsReview: boolean;
  finalOutput: string;
}) {
  if (state.finalOutput) {
    logger.agent("Graph", "Simple task → END");
    return END;
  }
  logger.agent("Graph", "Code task → Coder");
  return "coder";
}

/**
 * Decide what to do after the reviewer.
 * - PASS → END
 * - NEEDS_WORK & retries < MAX → back to coder
 * - NEEDS_WORK & retries >= MAX → END with issues
 */
function afterReviewer(state: {
  reviewResult: string;
  retryCount: number;
  finalOutput: string;
}) {
  if (state.finalOutput) {
    logger.agent("Graph", "Review passed → END");
    return END;
  }
  if (state.retryCount < MAX_RETRIES) {
    logger.agent("Graph", `Review needs work (attempt ${state.retryCount + 1}/${MAX_RETRIES}) → Coder`);
    return "coder";
  }
  logger.agent("Graph", `Max retries (${MAX_RETRIES}) reached → END`);
  return END;
}

/**
 * Build the multi-agent graph:
 *
 *   orchestrator ──(simple)──→ END
 *        │
 *        (code)
 *        ▼
 *      coder ──→ reviewer
 *        ▲          │
 *        │   (needs_work, retry<max)
 *        └──────────┘
 *        │
 *        (pass or max retries)
 *        ▼
 *       END
 */
export function buildAgentGraph() {
  const graph = new StateGraph(AgentStateAnnotation)
    .addNode("orchestrator", orchestratorNode)
    .addNode("coder", coderNode)
    .addNode("reviewer", reviewerNode)
    .addEdge(START, "orchestrator")
    .addConditionalEdges("orchestrator", afterOrchestrator)
    .addEdge("coder", "reviewer")
    .addConditionalEdges("reviewer", afterReviewer)
    .compile();

  return graph;
}

/**
 * Run the multi-agent pipeline for a given task.
 * Pass conversation messages for context-aware decisions.
 */
export async function runAgentPipeline(task: string, messages: Message[] = []): Promise<string> {
  const graph = buildAgentGraph();

  const result = await graph.invoke({
    task,
    messages,
    coderOutput: "",
    reviewResult: "",
    retryCount: 0,
    needsReview: false,
    finalOutput: "",
  });

  return result.finalOutput || result.coderOutput || "No output produced.";
}
