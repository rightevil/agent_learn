import Database from "better-sqlite3";
import path from "node:path";
import { mkdirSync } from "node:fs";
import type { Message } from "../types.js";

const DATA_DIR = path.resolve(process.cwd(), "data");
const DB_PATH = path.join(DATA_DIR, "checkpoints.sqlite");

let db: Database.Database;

function getDb(): Database.Database {
  if (!db) {
    mkdirSync(DATA_DIR, { recursive: true });
    db = new Database(DB_PATH);
    db.pragma("journal_mode = WAL");
    db.exec(`
      CREATE TABLE IF NOT EXISTS conversations (
        id TEXT PRIMARY KEY,
        state TEXT NOT NULL,
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
      );
      CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        conversation_id TEXT NOT NULL,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        FOREIGN KEY (conversation_id) REFERENCES conversations(id)
      );
    `);
  }
  return db;
}

export interface ConversationState {
  id: string;
  messages: Message[];
  updatedAt: string;
}

/**
 * Save or update the current conversation state.
 * Serializes the messages array as JSON and stores it in SQLite.
 */
export function saveConversation(id: string, messages: Message[]): void {
  const database = getDb();
  const stateJson = JSON.stringify(messages);

  database.prepare(`
    INSERT INTO conversations (id, state, updated_at)
    VALUES (?, ?, datetime('now'))
    ON CONFLICT(id) DO UPDATE SET
      state = excluded.state,
      updated_at = datetime('now')
  `).run(id, stateJson);
}

/**
 * Load a conversation by ID. Returns null if not found.
 */
export function loadConversation(id: string): ConversationState | null {
  const database = getDb();
  const row = database.prepare(
    "SELECT id, state, updated_at FROM conversations WHERE id = ?"
  ).get(id) as { id: string; state: string; updated_at: string } | undefined;

  if (!row) return null;

  return {
    id: row.id,
    messages: JSON.parse(row.state),
    updatedAt: row.updated_at,
  };
}

/**
 * List recent conversation IDs.
 */
export function listConversations(limit = 10): ConversationState[] {
  const database = getDb();
  const rows = database.prepare(
    "SELECT id, state, updated_at FROM conversations ORDER BY updated_at DESC LIMIT ?"
  ).all(limit) as { id: string; state: string; updated_at: string }[];

  return rows.map((row) => ({
    id: row.id,
    messages: JSON.parse(row.state),
    updatedAt: row.updated_at,
  }));
}

/**
 * Delete a conversation by ID.
 */
export function deleteConversation(id: string): void {
  const database = getDb();
  database.prepare("DELETE FROM conversations WHERE id = ?").run(id);
}
