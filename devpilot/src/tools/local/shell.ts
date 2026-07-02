import { tool } from "ai";
import { z } from "zod";
import { spawn } from "node:child_process";
import { logger } from "../../logger.js";

const ALLOWED_COMMANDS = ["ls", "cat", "grep", "git", "npm", "pnpm", "node", "dir", "type", "findstr"];
const BLOCKED_COMMANDS = ["rm", "sudo", "chmod", "curl", "wget", "del", "erase", "rd", "rmdir"];

// On Windows, map Unix commands to their Windows equivalents
const WIN_CMD_MAP: Record<string, { cmd: string; mapArgs: (args: string[]) => string[] }> = {
  ls: { cmd: "cmd", mapArgs: (args) => ["/c", "dir", ...args] },
  cat: { cmd: "cmd", mapArgs: (args) => ["/c", "type", ...args] },
  grep: { cmd: "findstr", mapArgs: (args) => args },
};

function validateCommand(command: string, args: string[]): void {
  const dangerousChars = /[;|$`&]/;
  if (dangerousChars.test(command)) {
    throw new Error(`Command contains illegal characters: ${command}`);
  }
  for (const arg of args) {
    if (dangerousChars.test(arg)) {
      throw new Error(`Argument contains illegal characters: ${arg}`);
    }
  }

  const base = command.split(/\s+/)[0].toLowerCase();
  if (BLOCKED_COMMANDS.includes(base)) {
    throw new Error(`Command is blocked: ${base}`);
  }
  if (!ALLOWED_COMMANDS.includes(base)) {
    throw new Error(`Command not in allowlist: ${base}`);
  }
}

function spawnCommand(command: string, args: string[]): Promise<string> {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, {
      cwd: process.cwd(),
      timeout: 30_000,
      shell: false,
    });

    let stdout = "";
    let stderr = "";

    child.stdout?.on("data", (data: Buffer) => {
      stdout += data.toString();
    });
    child.stderr?.on("data", (data: Buffer) => {
      stderr += data.toString();
    });

    child.on("close", (code) => {
      if (code === 0) {
        resolve(stdout.slice(0, 4000));
      } else {
        resolve(`Command exited with code ${code}\n${stderr || stdout}`.slice(0, 2000));
      }
    });

    child.on("error", (err) => {
      reject(err);
    });
  });
}

export const runCmdTool = tool({
  description: "Run a safe shell command and return the output. Only whitelisted commands are allowed.",
  parameters: z.object({
    command: z.string().describe("The command to run (e.g. 'git', 'npm', 'ls')"),
    args: z.array(z.string()).default([]).describe("Arguments to pass to the command"),
  }),
  execute: async ({ command, args }: { command: string; args: string[] }) => {
    logger.tool("run_cmd", `${command} ${args.join(" ")}`);
    try {
      validateCommand(command, args);
      const base = command.split(/\s+/)[0].toLowerCase();

      if (process.platform === "win32" && base in WIN_CMD_MAP) {
        const mapping = WIN_CMD_MAP[base];
        const mappedArgs = mapping.mapArgs(args);
        const result = await spawnCommand(mapping.cmd, mappedArgs);
        return result;
      }

      const result = await spawnCommand(command, args);
      return result;
    } catch (error) {
      const msg = error instanceof Error ? error.message : String(error);
      return `Error running command: ${msg}`;
    }
  },
});
