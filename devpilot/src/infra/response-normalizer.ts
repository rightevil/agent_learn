import type { Config } from "../config.js";
import type { NormalizedResponse, ToolCall } from "../types.js";

/**
 * Normalize different provider response structures into a standard format.
 *
 * - Agnes: content is returned directly, no special handling needed
 * - DeepSeek-V4: thinking mode returns `reasoning_content` as a separate field;
 *   we extract it and place it in `reasoning`, while `content` stays clean.
 * - OpenAI: passthrough (standard format)
 */
export function normalizeResponse(
  config: Config,
  raw: RawProviderResponse
): NormalizedResponse {
  const { LLM_PROVIDER } = config;

  switch (LLM_PROVIDER) {
    case "deepseek-v4": {
      const choice = raw.choices?.[0];
      const message = choice?.message;

      return {
        content: message?.content ?? "",
        reasoning: (message as DeepSeekMessage)?.reasoning_content || undefined,
        toolCalls: extractToolCalls(message?.tool_calls),
      };
    }
    case "agnes":
    case "openai":
    default: {
      const choice = raw.choices?.[0];
      const message = choice?.message;

      return {
        content: message?.content ?? "",
        toolCalls: extractToolCalls(message?.tool_calls),
      };
    }
  }
}

interface RawProviderResponse {
  choices?: Array<{
    message?: {
      content?: string | null;
      tool_calls?: RawToolCall[];
    };
  }>;
}

interface DeepSeekMessage {
  content?: string | null;
  reasoning_content?: string;
  tool_calls?: RawToolCall[];
}

interface RawToolCall {
  id?: string;
  type?: string;
  function?: {
    name?: string;
    arguments?: string;
  };
}

function extractToolCalls(rawToolCalls?: RawToolCall[]): ToolCall[] {
  if (!rawToolCalls) return [];

  return rawToolCalls
    .filter((tc) => tc.type === "function" && tc.function)
    .map((tc) => {
      let args: Record<string, unknown> = {};
      if (tc.function?.arguments) {
        try {
          args = JSON.parse(tc.function.arguments);
        } catch {
          args = {};
        }
      }
      return {
        name: tc.function!.name ?? "",
        arguments: args,
      };
    });
}
