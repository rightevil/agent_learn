import { tool } from "ai";
import { z } from "zod";
import { spawn } from "node:child_process";
import { logger } from "../../logger.js";

const ALLOWED_COMMANDS = ["ls", "cat", "grep", "git", "npm", "pnpm", "npx", "node", "python", "py", "dir", "type", "findstr", "pwd", "cd", "echo", "mkdir", "cp", "mv", "copy", "move"];
const BLOCKED_COMMANDS = ["rm", "sudo", "chmod", "curl", "wget", "del", "erase", "rd", "rmdir"];

function stripUnixFlags(args: string[]): string[] {
  // Windows cmd uses /flags, not -flags. Strip anything starting with -
  return args.filter((a) => !a.startsWith("-"));
}

function normalizeWinPath(arg: string): string {
  if (process.platform === "win32" && /^[a-zA-Z]:[\\/]/.test(arg)) {
    return arg.replace(/\//g, "\\");
  }
  return arg;
}

/** Strip Unix flags + normalize paths — used by most cmd-mapped commands */
function winArgs(args: string[]): string[] {
  return stripUnixFlags(args).map(normalizeWinPath);
}

// On Windows, map Unix commands and cmd built-ins to spawn-able equivalents
const WIN_CMD_MAP: Record<string, { cmd: string; mapArgs: (args: string[]) => string[] }> = {
  ls:    { cmd: "cmd", mapArgs: (a) => ["/c", "dir", ...winArgs(a)] },
  dir:   { cmd: "cmd", mapArgs: (a) => ["/c", "dir", ...winArgs(a)] },
  cat:   { cmd: "cmd", mapArgs: (a) => ["/c", "type", ...winArgs(a)] },
  cd:    { cmd: "cmd", mapArgs: (a) => ["/c", "cd", ...winArgs(a)] },
  mkdir: { cmd: "cmd", mapArgs: (a) => ["/c", "mkdir", ...winArgs(a)] },
  cp:    { cmd: "cmd", mapArgs: (a) => ["/c", "copy", ...winArgs(a)] },
  mv:    { cmd: "cmd", mapArgs: (a) => ["/c", "move", ...winArgs(a)] },
  copy:  { cmd: "cmd", mapArgs: (a) => ["/c", "copy", ...winArgs(a)] },
  move:  { cmd: "cmd", mapArgs: (a) => ["/c", "move", ...winArgs(a)] },
  pwd:   { cmd: "cmd", mapArgs: () => ["/c", "cd"] },
  echo:  { cmd: "cmd", mapArgs: (a) => ["/c", "echo", ...a] },
  grep:  { cmd: "findstr", mapArgs: (a) => a },
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
    command: z.string().default("").describe("The command to run (e.g. 'git', 'npm', 'ls')"),
    args: z.union([
      z.array(z.string()),
      z.string().transform((s) => {
        try { return JSON.parse(s) as string[]; } catch { return [s]; }
      }),
    ]).default([]).describe("Arguments to pass to the command"),
  }),
  execute: async ({ command, args }: { command: string; args: string[] }) => {
    // Guard against LLM producing a call with no command
    if (!command) {
      return "Error: tool called without a command. Please specify a command to run (e.g. ls, dir, git, npm).";
    }

    // If the agent packed everything into command (e.g. "mkdir -p first"),
    // split it so args aren't lost
    if (args.length === 0 && /\s+/.test(command.trim())) {
      // If the command contains quotes, don't split — pass raw to shell
      if (/["']/.test(command)) {
        logger.tool("run_cmd", `(raw) ${command}`);
        const shell = process.platform === "win32" ? "cmd" : "sh";
        const flag = process.platform === "win32" ? "/c" : "-c";
        try {
          validateCommand(command, []);
          const result = await spawnCommand(shell, [flag, command]);
          return result;
        } catch (error) {
          const msg = error instanceof Error ? error.message : String(error);
          return `Error running command: ${msg}`;
        }
      }
      const parts = command.trim().split(/\s+/);
      command = parts[0];
      args = parts.slice(1);
    }

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
