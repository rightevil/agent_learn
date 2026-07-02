import path from "node:path";
import { mkdirSync, readFileSync, existsSync } from "node:fs";
import { writeFile } from "node:fs/promises";
import { logger } from "../logger.js";

const DATA_DIR = path.resolve(process.cwd(), "data");
const MEMORY_PATH = path.join(DATA_DIR, "long-term-memory.json");

export interface TaskMemory {
  id: string;
  task: string;
  solution: string;
  timestamp: string;
  keywords: string[];
}

/**
 * Load all stored task memories.
 */
export function loadMemories(): TaskMemory[] {
  mkdirSync(DATA_DIR, { recursive: true });

  if (!existsSync(MEMORY_PATH)) {
    return [];
  }

  try {
    const raw = readFileSync(MEMORY_PATH, "utf-8");
    return JSON.parse(raw);
  } catch {
    logger.warn("Failed to read long-term memory, starting fresh");
    return [];
  }
}

/**
 * Save all task memories to disk.
 */
export async function saveMemories(memories: TaskMemory[]): Promise<void> {
  mkdirSync(DATA_DIR, { recursive: true });
  await writeFile(MEMORY_PATH, JSON.stringify(memories, null, 2), "utf-8");
}

/**
 * Add a new task memory entry.
 */
export async function addMemory(task: string, solution: string): Promise<void> {
  const memories = loadMemories();

  // Keep only the last 100 entries to prevent unbounded growth
  if (memories.length >= 100) {
    memories.shift();
  }

  memories.push({
    id: Date.now().toString(36),
    task,
    solution: solution.slice(0, 2000), // Truncate long solutions
    timestamp: new Date().toISOString(),
    keywords: extractKeywords(task),
  });

  await saveMemories(memories);
}

/**
 * Find the most similar past task memories to the given task.
 * Uses simple keyword overlap scoring (Jaccard-like similarity).
 * Returns top 3 matches.
 */
export function findSimilarTasks(task: string, limit = 3): TaskMemory[] {
  const memories = loadMemories();
  if (memories.length === 0) return [];

  const taskKeywords = extractKeywords(task);

  const scored = memories.map((mem) => {
    const overlap = mem.keywords.filter((kw) => taskKeywords.includes(kw));
    // Jaccard-like score: intersection / union
    const union = new Set([...mem.keywords, ...taskKeywords]);
    const score = union.size > 0 ? overlap.length / union.size : 0;

    // Boost recent memories
    const ageDays = (Date.now() - new Date(mem.timestamp).getTime()) / (1000 * 60 * 60 * 24);
    const recencyBoost = Math.max(0, 1 - ageDays / 30); // Linear decay over 30 days

    return { memory: mem, score: score + recencyBoost * 0.3 };
  });

  // Sort by score descending, take top N with score > 0
  return scored
    .filter((s) => s.score > 0.1)
    .sort((a, b) => b.score - a.score)
    .slice(0, limit)
    .map((s) => s.memory);
}

/**
 * Extract keywords from a task description.
 * Simple approach: split on non-word chars, filter short words, deduplicate.
 */
function extractKeywords(text: string): string[] {
  const words = text
    .toLowerCase()
    .split(/[\s,;:.!?()\[\]{}"'`/\\|@#$%^&*+=<>]+/)
    .filter((w) => w.length > 2)
    // Remove common stop words
    .filter((w) => !STOP_WORDS.has(w));

  return [...new Set(words)];
}

const STOP_WORDS = new Set([
  "the", "and", "for", "that", "this", "with", "from", "have", "are",
  "was", "not", "but", "you", "all", "can", "had", "her", "his",
  "has", "how", "its", "may", "our", "out", "see", "she", "some",
  "than", "them", "then", "these", "what", "when", "who", "will",
  "de", "en", "la", "las", "los", "por", "que", "una",
]);
