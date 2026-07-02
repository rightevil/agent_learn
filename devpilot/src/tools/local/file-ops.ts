import { tool } from "ai";
import { z } from "zod";
import { readFile } from "node:fs/promises";
import { writeFile } from "node:fs/promises";
import path from "node:path";
import { logger } from "../../logger.js";
import { assertSafePath } from "../../utils/path.js";

export const readFileTool = tool({
  description: "Read the contents of a file from the local filesystem. Returns the file content as text.",
  parameters: z.object({
    filePath: z.string().describe("Absolute path to the file to read"),
  }),
  execute: async ({ filePath }: { filePath: string }) => {
    logger.tool("read_file", `Reading ${filePath}`);
    try {
      assertSafePath(filePath);
      const content = await readFile(filePath, "utf-8");
      const truncated = content.length > 8000
        ? content.slice(0, 8000) + "\n... (truncated)"
        : content;
      return truncated;
    } catch (error) {
      const msg = error instanceof Error ? error.message : String(error);
      return `Error reading file: ${msg}`;
    }
  },
});

export const writeFileTool = tool({
  description: "Write content to a file on the local filesystem. Creates directories if needed.",
  parameters: z.object({
    filePath: z.string().describe("Absolute path to the file to write"),
    content: z.string().describe("Content to write to the file"),
  }),
  execute: async ({ filePath, content }: { filePath: string; content: string }) => {
    logger.tool("write_file", `Writing to ${filePath}`);
    try {
      assertSafePath(filePath);
      const dir = path.dirname(filePath);
      await import("node:fs/promises").then(fs => fs.mkdir(dir, { recursive: true }));
      await writeFile(filePath, content, "utf-8");
      return `Successfully wrote to ${filePath} (${content.length} bytes)`;
    } catch (error) {
      const msg = error instanceof Error ? error.message : String(error);
      return `Error writing file: ${msg}`;
    }
  },
});
