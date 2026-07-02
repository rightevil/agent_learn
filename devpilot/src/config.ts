import "dotenv/config";
import { z } from "zod";

const configSchema = z.object({
  LLM_PROVIDER: z.enum(["agnes", "deepseek-v4", "openai"]).default("deepseek-v4"),
  LLM_BASE_URL: z.string().default("https://api.deepseek.com"),
  LLM_API_KEY: z.string().min(1, "LLM_API_KEY is required"),
  LLM_MODEL: z.string().default("deepseek-v4-flash"),
  LLM_MAX_OUTPUT_TOKENS: z.coerce.number().default(8192),
});

export type Config = z.infer<typeof configSchema>;

export function loadConfig(): Config {
  const result = configSchema.safeParse(process.env);
  if (!result.success) {
    console.error("Configuration error:", result.error.format());
    process.exit(1);
  }
  return result.data;
}

export const config = loadConfig();
