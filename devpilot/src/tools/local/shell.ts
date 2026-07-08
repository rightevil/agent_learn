import { z } from "zod";
import { spawn } from "node:child_process";
import { registry, type ToolDef } from "../types.js";

const ALLOWED_COMMANDS = ["ls", "cat", "grep", "git", "npm", "pnpm", "npx", "node", "python", "py", "dir", "type", "findstr", "pwd", "cd", "echo", "mkdir", "cp", "mv", "copy", "move"];
const BLOCKED_COMMANDS = ["rm", "sudo", "chmod", "curl", "wget", "del", "erase", "rd", "rmdir"];

function stripUnixFlags(args: string[]): string[] {
  return args.filter((a) => !a.startsWith("-"));
}

function normalizeWinPath(arg: string): string {
  if (process.platform === "win32" && /^[a-zA-Z]:[\\/]/.test(arg)) {
    return arg.replace(/\//g, "\\");
  }
  return arg;
}

function winArgs(args: string[]): string[] {
  return stripUnixFlags(args).map(normalizeWinPath);
}

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
    child.stdout?.on("data", (data: Buffer) => { stdout += data.toString(); });
    child.stderr?.on("data", (data: Buffer) => { stderr += data.toString(); });
    child.on("close", (code) => {
      if (code === 0) {
        resolve(stdout.slice(0, 4000));
      } else {
        resolve(`Command exited with code ${code}\n${stderr || stdout}`.slice(0, 2000));
      }
    });
    child.on("error", (err) => { reject(err); });
  });
}

export const runCmdTool: ToolDef = {
  name: "run_cmd",
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
  async execute(rawArgs) {
    let command = rawArgs.command as string;
    let args = rawArgs.args as string[];

    if (!command) return "Error: no command specified";

    if (args.length === 0 && /\s+/.test(command.trim())) {
      if (/["']/.test(command)) {
        const shell = process.platform === "win32" ? "cmd" : "sh";
        const flag = process.platform === "win32" ? "/c" : "-c";
        try {
          validateCommand(command, []);
          return await spawnCommand(shell, [flag, command]);
        } catch (error) {
          return `Error: ${error instanceof Error ? error.message : String(error)}`;
        }
      }
      const parts = command.trim().split(/\s+/);
      command = parts[0];
      args = parts.slice(1);
    }

    try {
      validateCommand(command, args);
      const base = command.split(/\s+/)[0].toLowerCase();

      if (process.platform === "win32" && base in WIN_CMD_MAP) {
        const mapping = WIN_CMD_MAP[base];
        return await spawnCommand(mapping.cmd, mapping.mapArgs(args));
      }

      return await spawnCommand(command, args);
    } catch (error) {
      return `Error: ${error instanceof Error ? error.message : String(error)}`;
    }
  },
};

registry.register(runCmdTool);
