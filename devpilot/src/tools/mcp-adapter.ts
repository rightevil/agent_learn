import { z } from "zod";
import { mcpManager } from "./mcp-client.js";
import { logger } from "../logger.js";
import { registry, type ToolDef } from "./types.js";

/**
 * Register all tools from all connected MCP servers into the tool registry.
 * Each MCP tool becomes a ToolDef entry with conversion from JSON Schema → Zod.
 */
export async function registerMcpTools(): Promise<void> {
  if (!mcpManager.isConnected) return;

  for (const fullName of mcpManager.toolNames) {
    try {
      const entry = mcpManager.getToolDefs().get(fullName);
      if (!entry) continue;

      const zodSchema = jsonSchemaToZod(entry.tool.inputSchema);

      const toolDef: ToolDef = {
        name: fullName,
        description: entry.tool.description || `MCP tool: ${entry.tool.name}`,
        parameters: zodSchema,
        execute: async (args) => {
          logger.tool(fullName, JSON.stringify(args).slice(0, 120));
          try {
            return await mcpManager.callTool(fullName, args);
          } catch (error) {
            return `MCP tool error (${fullName}): ${error instanceof Error ? error.message : String(error)}`;
          }
        },
      };

      registry.register(toolDef);
    } catch (error) {
      logger.warn(`Skipping MCP tool ${fullName}: ${error instanceof Error ? error.message : String(error)}`);
    }
  }
}

// --- JSON Schema → Zod conversion (unchanged) ---

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
      if (!isRequired) fieldSchema = fieldSchema.optional();
      shape[key] = fieldSchema;
    }
    return z.object(shape);
  }
  return z.object({}).passthrough();
}

function jsonSchemaPropToZod(prop: Record<string, unknown>): z.ZodTypeAny {
  switch (prop.type) {
    case "string":  return z.string();
    case "number":
    case "integer": return z.number();
    case "boolean": return z.boolean();
    case "array":   return z.array(z.any());
    case "object":
      if (prop.properties) {
        return jsonSchemaToZod({
          type: "object",
          properties: prop.properties as Record<string, unknown>,
          required: prop.required as string[] | undefined,
        });
      }
      return z.object({}).passthrough();
    default: return z.any();
  }
}
