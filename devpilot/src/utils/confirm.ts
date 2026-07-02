import { confirm } from "@inquirer/prompts";

export async function confirmWrite(targetPath: string): Promise<boolean> {
  return confirm({
    message: `Confirm write to ${targetPath}?`,
    default: false,
  });
}
