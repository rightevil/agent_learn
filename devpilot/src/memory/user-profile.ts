import path from "node:path";
import { mkdirSync, readFileSync, existsSync } from "node:fs";
import { writeFile } from "node:fs/promises";
import type { UserProfile } from "../types.js";
import { logger } from "../logger.js";

const DATA_DIR = path.resolve(process.cwd(), "data");
const PROFILE_PATH = path.join(DATA_DIR, "profile.json");

const DEFAULT_PROFILE: UserProfile = {
  language: "",
  testFramework: "",
  codeStyle: "",
  initialized: false,
};

/**
 * Load the user profile from disk. Returns the default (uninitialized)
 * profile if no profile file exists yet.
 */
export function loadProfile(): UserProfile {
  mkdirSync(DATA_DIR, { recursive: true });

  if (!existsSync(PROFILE_PATH)) {
    return { ...DEFAULT_PROFILE };
  }

  try {
    const raw = readFileSync(PROFILE_PATH, "utf-8");
    return { ...DEFAULT_PROFILE, ...JSON.parse(raw) };
  } catch {
    logger.warn("Failed to read profile, using defaults");
    return { ...DEFAULT_PROFILE };
  }
}

/**
 * Save the user profile to disk.
 */
export async function saveProfile(profile: UserProfile): Promise<void> {
  mkdirSync(DATA_DIR, { recursive: true });
  await writeFile(PROFILE_PATH, JSON.stringify(profile, null, 2), "utf-8");
}

/**
 * Check if this is the first run (no profile or not initialized).
 */
export function isFirstRun(): boolean {
  const profile = loadProfile();
  return !profile.initialized;
}
