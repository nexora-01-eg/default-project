// Shared IO: JSON, dirs, resume state. Mirrors threeui-library conventions.
import { promises as fs } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

export const ULIB_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
export const THREEUI_ROOT = path.resolve(ULIB_ROOT, "..", "threeui-library");

export async function readJson(file, fallback) {
  try {
    return JSON.parse(await fs.readFile(file, "utf8"));
  } catch {
    return fallback;
  }
}

export async function writeJson(file, data) {
  await fs.mkdir(path.dirname(file), { recursive: true });
  await fs.writeFile(file, JSON.stringify(data, null, 2) + "\n", "utf8");
}

export function nowIso() {
  return new Date().toISOString();
}

export function parseArgs(argv = process.argv.slice(2)) {
  const args = {};
  for (let k = 0; k < argv.length; k += 1) {
    const m = argv[k].match(/^--([^=\s]+)(=(.*))?$/);
    if (m) {
      if (m[3] !== undefined) args[m[1]] = m[3];
      else if (k + 1 < argv.length && !argv[k + 1].startsWith("--")) args[m[1]] = argv[k + 1];
      else args[m[1]] = true;
    }
  }
  return args;
}
