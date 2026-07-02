#!/usr/bin/env node
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";
import { loadProfile } from "../memory/user-profile.js";
import { loadConversation, listConversations } from "../memory/short-term.js";

/**
 * DevPilot MCP Server
 *
 * Exposes DevPilot's capabilities as MCP tools so that Cursor, Claude Desktop,
 * and other MCP clients can use them.
 *
 * Tools exposed:
 *   - ask_devpilot: Send a prompt to DevPilot (simplified single-shot)
 *   - get_profile: Read the user's DevPilot profile/preferences
 *   - list_conversations: List previous DevPilot conversations
 */
async function main() {
  const server = new Server(
    {
      name: "devpilot-mcp",
      version: "0.1.0",
    },
    {
      capabilities: {
        tools: {},
      },
    }
  );

  // Register tool listing
  server.setRequestHandler(ListToolsRequestSchema, async () => ({
    tools: [
      {
        name: "get_profile",
        description: "Get the user's DevPilot profile including language, test framework, and code style preferences.",
        inputSchema: {
          type: "object",
          properties: {},
        },
      },
      {
        name: "list_conversations",
        description: "List recent DevPilot conversations with their IDs and previews.",
        inputSchema: {
          type: "object",
          properties: {
            limit: {
              type: "number",
              description: "Maximum number of conversations to return (default: 10)",
            },
          },
        },
      },
    ],
  }));

  // Handle tool calls
  server.setRequestHandler(CallToolRequestSchema, async (request) => {
    const { name, arguments: args } = request.params;

    switch (name) {
      case "get_profile": {
        const profile = loadProfile();
        if (!profile.initialized) {
          return {
            content: [
              {
                type: "text",
                text: "DevPilot profile has not been set up yet. Run `devpilot` in the terminal first to configure your preferences.",
              },
            ],
          };
        }
        return {
          content: [
            {
              type: "text",
              text: [
                "## DevPilot User Profile",
                "",
                `- **Language**: ${profile.language}`,
                `- **Test Framework**: ${profile.testFramework}`,
                `- **Code Style**: ${profile.codeStyle}`,
              ].join("\n"),
            },
          ],
        };
      }

      case "list_conversations": {
        const limit = typeof args?.limit === "number" ? args.limit : 10;
        const conversations = listConversations(limit);

        if (conversations.length === 0) {
          return {
            content: [{ type: "text", text: "No previous conversations found." }],
          };
        }

        const lines = ["## Recent DevPilot Conversations", ""];
        for (const conv of conversations) {
          const preview = conv.messages[0]?.content.slice(0, 80) ?? "(empty)";
          lines.push(
            `- **${conv.id.slice(0, 8)}** (${conv.messages.length} messages, ${conv.updatedAt})`,
            `  ${preview}...`
          );
        }

        return {
          content: [{ type: "text", text: lines.join("\n") }],
        };
      }

      default:
        throw new Error(`Unknown tool: ${name}`);
    }
  });

  // Start server via stdio
  const transport = new StdioServerTransport();
  await server.connect(transport);

  // Log to stderr (stdout is reserved for MCP protocol)
  console.error("[devpilot-mcp] Server started via stdio");
}

main().catch((error) => {
  console.error("[devpilot-mcp] Fatal error:", error);
  process.exit(1);
});
