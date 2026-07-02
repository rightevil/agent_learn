export interface AgentState {
  messages: Message[];
  task: string;
  coderOutput: string;
  reviewResult: string;
  retryCount: number;
  userProfile: UserProfile;
}

export interface Message {
  role: "user" | "assistant" | "system";
  content: string;
}

export interface UserProfile {
  language: string;
  testFramework: string;
  codeStyle: string;
  initialized: boolean;
}

export interface ToolResult {
  success: boolean;
  content: string;
  error?: string;
}

export interface NormalizedResponse {
  content: string;
  reasoning?: string;
  toolCalls: ToolCall[];
}

export interface ToolCall {
  name: string;
  arguments: Record<string, unknown>;
}
