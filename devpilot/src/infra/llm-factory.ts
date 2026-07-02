import { createOpenAI } from "@ai-sdk/openai";
import type { LanguageModelV1 } from "ai";
import type { Config } from "../config.js";
import { buildProviderRequest, type ThinkingMode } from "./request-builder.js";

/**
 * Create a unified LLM instance based on the LLM_PROVIDER config.
 * Uses @ai-sdk/openai's createOpenAI with custom baseURL for all providers
 * since Agnes and DeepSeek-V4 both have OpenAI-compatible APIs.
 */
export function createLLM(
  config: Config,
  options?: { enableReasoning?: boolean; reasoningEffort?: ThinkingMode }
): LanguageModelV1 {
  const provider = createOpenAI({
    baseURL: config.LLM_BASE_URL,
    apiKey: config.LLM_API_KEY,
  });

  const model = provider.chat(config.LLM_MODEL);

  // Inject provider-specific parameters into the model's request config
  const extraParams = buildProviderRequest(config, options);

  if (extraParams.body && Object.keys(extraParams.body).length > 0) {
    // Wrap the model to inject extra body params
    return wrapModel(model, extraParams);
  }

  return model as unknown as LanguageModelV1;
}

/**
 * Wraps a language model to inject custom request body parameters.
 * This is a lightweight proxy that merges our provider-specific params.
 */
function wrapModel(
  model: ReturnType<ReturnType<typeof createOpenAI>["chat"]>,
  extra: ReturnType<typeof buildProviderRequest>
): LanguageModelV1 {
  const originalDoGenerate = (model as unknown as LanguageModelV1).doGenerate;
  const wrapped = model as unknown as LanguageModelV1;

  if (!originalDoGenerate) {
    return wrapped;
  }

  return {
    ...wrapped,
    specificationVersion: "v1",
    provider: "devpilot-adapter",
    modelId: wrapped.modelId,
    doGenerate(options: Parameters<LanguageModelV1["doGenerate"]>[0]) {
      // Merge our extra body params into the request
      const mergedOptions = {
        ...options,
        ...(extra.body ? { extra_body: extra.body } : {}),
      };
      return originalDoGenerate.call(wrapped, mergedOptions);
    },
  } as LanguageModelV1;
}
