import { tool, type CoreTool } from "ai";
import { z } from "zod";
import { mcpManager } from "./mcp-client.js";
import { logger } from "../logger.js";

/**
 * Convert an MCP tool definition to an AI SDK v3 tool.
 *
 * MCP tools use JSON Schema for their input, while AI SDK v3 uses Zod schemas.
 * We generate a dynamic Zod schema from the JSON Schema and wrap the MCP call.
 */
export function mcpToolToAITool(fullName: string): {
  name: string;
  aiTool: CoreTool;
} {
  const entry = mcpManager.getToolDefs().get(fullName);
  if (!entry) {
    throw new Error(`MCP tool not found: ${fullName}`);
  }

  const { tool: mcpTool } = entry;

  // Build a dynamic Zod schema from the MCP tool's JSON Schema
  const zodSchema = jsonSchemaToZod(mcpTool.inputSchema);

  const aiTool = tool({
    description: mcpTool.description || `MCP tool: ${mcpTool.name}`,
    parameters: zodSchema,
    execute: async (args: Record<string, unknown>) => {
      logger.tool(fullName, JSON.stringify(args).slice(0, 120));
      try {
        const result = await mcpManager.callTool(fullName, args);
        return result;
      } catch (error) {
        const msg = error instanceof Error ? error.message : String(error);
        return `MCP tool error (${fullName}): ${msg}`;
      }
    },
  }) as CoreTool;

  return { name: fullName, aiTool };
}

/**
 * Convert all discovered MCP tools to AI SDK tools.
 */
export function mcpToolsToAITools(): Record<string, CoreTool> {
  const tools: Record<string, CoreTool> = {};

  for (const fullName of mcpManager.toolNames) {
    try {
      const { name, aiTool } = mcpToolToAITool(fullName);
      tools[name] = aiTool;
    } catch (error) {
      logger.warn(`Skipping MCP tool ${fullName}: ${error instanceof Error ? error.message : String(error)}`);
    }
  }

  return tools;
}

/**
 * Convert a JSON Schema to a Zod schema.
 * Supports a limited subset of JSON Schema features.
 */
function jsonSchemaToZod(schema: {
  type: string;
  properties?: Record<string, unknown>;
  required?: string[];
}): z.ZodTypeAny {
  if (schema.type === "object" && schema.properties) {
    const shape: Record<string, z.ZodTypeAny> = {};

    for (const [key, prop] of Object.entries(schema.properties)) {
      const isRequired = schema.required?.includes(key);
      let fieldSchema = jsonSchemaPropToZod(prop as Record<string, unknown>);

      if (!isRequired) {
        fieldSchema = fieldSchema.optional();
      }

      shape[key] = fieldSchema;
    }

    return z.object(shape);
  }

  // Fallback: accept any object
  return z.object({}).passthrough();
}

function jsonSchemaPropToZod(prop: Record<string, unknown>): z.ZodTypeAny {
  const type = prop.type as string;

  switch (type) {
    case "string":
      return z.string();
    case "number":
    case "integer":
      return z.number();
    case "boolean":
      return z.boolean();
    case "array":
      return z.array(z.any());
    case "object":
      if (prop.properties) {
        return jsonSchemaToZod({
          type: "object",
          properties: prop.properties as Record<string, unknown>,
          required: prop.required as string[] | undefined,
        });
      }
      return z.object({}).passthrough();
    default:
      return z.any();
  }
}
