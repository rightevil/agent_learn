import type { Config } from "../config.js";

export type ThinkingMode = "off" | "low" | "high" | "max";

export interface ProviderRequestParams {
  body?: Record<string, unknown>;
  headers?: Record<string, string>;
}

/**
 * Inject provider-specific parameters into the request body.
 * - Agnes: chat_template_kwargs.enable_thinking
 * - DeepSeek-V4: thinking.reasoning_effort
 * - OpenAI: no extra params (passthrough)
 */
export function buildProviderRequest(
  config: Config,
  options?: { enableReasoning?: boolean; reasoningEffort?: ThinkingMode }
): ProviderRequestParams {
  const { LLM_PROVIDER } = config;
  const enableReasoning = options?.enableReasoning ?? false;
  const reasoningEffort = options?.reasoningEffort ?? "high";

  switch (LLM_PROVIDER) {
    case "agnes": {
      if (enableReasoning) {
        return {
          body: {
            chat_template_kwargs: { enable_thinking: true },
          },
        };
      }
      return {};
    }
    case "deepseek-v4": {
      if (enableReasoning) {
        return {
          body: {
            thinking: { reasoning_effort: reasoningEffort },
          },
        };
      }
      return {};
    }
    case "openai":
    default:
      return {};
  }
}
