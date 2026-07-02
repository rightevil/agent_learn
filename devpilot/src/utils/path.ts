import path from "node:path";

const ALLOWED_ROOTS: string[] = [];

function getAllowedRoots(): string[] {
  if (ALLOWED_ROOTS.length === 0) {
    const home = process.env.HOME || process.env.USERPROFILE || "";
    if (home) {
      ALLOWED_ROOTS.push(path.resolve(home, "projects"));
    }
    ALLOWED_ROOTS.push(process.cwd());
  }
  return ALLOWED_ROOTS;
}

/**
 * Ensure a file path stays within allowed roots to prevent path traversal attacks.
 */
export function assertSafePath(targetPath: string): void {
  const roots = getAllowedRoots();
  const resolved = path.resolve(targetPath);

  const allowed = roots.some((root) => {
    const resolvedRoot = path.resolve(root);
    return resolved.startsWith(resolvedRoot);
  });

  if (!allowed) {
    throw new Error(
      `Path out of bounds: ${targetPath}\n` +
      `Allowed roots: ${roots.join(", ")}`
    );
  }
}
