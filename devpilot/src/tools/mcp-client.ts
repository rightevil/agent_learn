import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";
import { logger } from "../logger.js";

export interface MCPServerConfig {
  name: string;
  command: string;
  args: string[];
  enabled: boolean;
}

interface MCPToolDef {
  name: string;
  description?: string;
  inputSchema: {
    type: string;
    properties?: Record<string, unknown>;
    required?: string[];
  };
}

/**
 * MCP Client Manager: connects to external MCP servers and discovers their tools.
 *
 * Servers are configured via MCP_SERVERS env var (JSON array) or use defaults.
 * Example:
 *   MCP_SERVERS='[{"name":"filesystem","command":"npx","args":["-y","@modelcontextprotocol/server-filesystem","/tmp"]}]'
 */
export class MCPClientManager {
  private clients: Map<string, Client> = new Map();
  private tools: Map<string, { serverName: string; tool: MCPToolDef }> = new Map();
  private connected = false;

  get isConnected(): boolean {
    return this.connected;
  }

  get toolNames(): string[] {
    return Array.from(this.tools.keys());
  }

  /**
   * Connect to all configured MCP servers and discover their tools.
   */
  async connect(servers: MCPServerConfig[] = []): Promise<void> {
    if (this.connected) return;

    const configs = servers.length > 0 ? servers : this.loadServerConfigs();

    for (const cfg of configs) {
      if (!cfg.enabled) continue;

      try {
        logger.info(`Connecting to MCP server: ${cfg.name}...`);

        const transport = new StdioClientTransport({
          command: cfg.command,
          args: cfg.args,
        });

        const client = new Client({
          name: "devpilot",
          version: "0.1.0",
        }, {
          capabilities: { tools: {} },
        });

        await client.connect(transport);
        this.clients.set(cfg.name, client);

        // Discover tools
        const { tools } = await client.listTools();
        for (const tool of tools) {
          const key = `mcp:${cfg.name}/${tool.name}`;
          this.tools.set(key, {
            serverName: cfg.name,
            tool: {
              name: tool.name,
              description: tool.description,
              inputSchema: tool.inputSchema as MCPToolDef["inputSchema"],
            },
          });
        }

        logger.success(`MCP/${cfg.name}: ${tools.length} tools discovered`);
      } catch (error) {
        logger.warn(`Failed to connect to MCP server "${cfg.name}": ${error instanceof Error ? error.message : String(error)}`);
      }
    }

    this.connected = true;
  }

  /**
   * Call a tool on the appropriate MCP server.
   */
  async callTool(fullName: string, args: Record<string, unknown>): Promise<string> {
    const entry = this.tools.get(fullName);
    if (!entry) {
      throw new Error(`MCP tool not found: ${fullName}`);
    }

    const client = this.clients.get(entry.serverName);
    if (!client) {
      throw new Error(`MCP server not connected: ${entry.serverName}`);
    }

    const result = await client.callTool({
      name: entry.tool.name,
      arguments: args,
    });

    // Extract text content from the result
    const contents = result.content as Array<{ type: string; text?: string }>;
    return contents
      .filter((c) => c.type === "text")
      .map((c) => c.text || "")
      .join("\n");
  }

  /**
   * Get all discovered MCP tool definitions.
   */
  getToolDefs(): Map<string, { serverName: string; tool: MCPToolDef }> {
    return new Map(this.tools);
  }

  /**
   * Disconnect from all MCP servers.
   */
  async disconnect(): Promise<void> {
    for (const [name, client] of this.clients) {
      try {
        await client.close();
        logger.info(`Disconnected from MCP/${name}`);
      } catch {
        // ignore close errors
      }
    }
    this.clients.clear();
    this.tools.clear();
    this.connected = false;
  }

  private loadServerConfigs(): MCPServerConfig[] {
    const envConfig = process.env.MCP_SERVERS;
    if (envConfig) {
      try {
        return JSON.parse(envConfig);
      } catch {
        logger.warn("Invalid MCP_SERVERS JSON, using defaults");
      }
    }

    // Default: try to connect to filesystem MCP server if installed
    return [
      {
        name: "filesystem",
        command: "npx",
        args: ["-y", "@modelcontextprotocol/server-filesystem", process.cwd()],
        enabled: false, // disabled by default for safety
      },
    ];
  }
}

/** Singleton instance */
export const mcpManager = new MCPClientManager();
