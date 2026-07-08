import { z } from "zod";
import { readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { assertSafePath } from "../../utils/path.js";
import { registry, type ToolDef } from "../types.js";

export const readFileTool: ToolDef = {
  name: "read_file",
  description: "Read the contents of a file from the local filesystem. Returns the file content as text.",
  parameters: z.object({
    filePath: z.string().default("").describe("Absolute path to the file to read"),
  }),
  async execute(args) {
    const filePath = args.filePath as string;
    if (!filePath) return "Error: no filePath provided";

    try {
      assertSafePath(filePath);
      const content = await readFile(filePath, "utf-8");
      return content.length > 8000
        ? content.slice(0, 8000) + "\n... (truncated)"
        : content;
    } catch (error) {
      return `Error reading file: ${error instanceof Error ? error.message : String(error)}`;
    }
  },
};

export const writeFileTool: ToolDef = {
  name: "write_file",
  description: "Write content to a file on the local filesystem. Creates directories if needed.",
  parameters: z.object({
    filePath: z.string().default("").describe("Absolute path to the file to write"),
    content: z.string().default("").describe("Content to write to the file"),
  }),
  async execute(args) {
    const filePath = args.filePath as string;
    const content = args.content as string;
    if (!filePath) return "Error: no filePath provided";
    if (!content) return "Error: no content provided";

    try {
      assertSafePath(filePath);
      const dir = path.dirname(filePath);
      await import("node:fs/promises").then(fs => fs.mkdir(dir, { recursive: true }));
      await writeFile(filePath, content, "utf-8");
      return `Successfully wrote to ${filePath} (${content.length} bytes)`;
    } catch (error) {
      return `Error writing file: ${error instanceof Error ? error.message : String(error)}`;
    }
  },
};

// Register on import
registry.register(readFileTool);
registry.register(writeFileTool);
