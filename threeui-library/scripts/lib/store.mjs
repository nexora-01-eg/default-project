// Shared filesystem helpers: JSON IO, hashing, slugify, resume state.
import { createHash } from "node:crypto";
import { createReadStream } from "node:fs";
import { promises as fs } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

export const LIB_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");

export const DATA_DIRS = [
  "components", "templates", "landing-pages", "heroes", "sections",
  "backgrounds", "shaders", "3d-assets", "buttons", "text-animation",
  "ui-elements", "motion-design", "variants", "assets", "metadata",
];

export async function ensureDirs() {
  for (const d of DATA_DIRS) await fs.mkdir(path.join(LIB_ROOT, d), { recursive: true });
  await fs.mkdir(path.join(LIB_ROOT, "reports"), { recursive: true });
}

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

export function slugify(s) {
  return String(s || "untitled")
    .toLowerCase()
    .normalize("NFKD")
    .replace(/[̀-ͯ]/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 120) || "untitled";
}

export function sha256Hex(buf) {
  return createHash("sha256").update(buf).digest("hex");
}

export async function sha256File(file) {
  return new Promise((resolve, reject) => {
    const h = createHash("sha256");
    const s = createReadStream(file);
    s.on("data", (c) => h.update(c));
    s.on("end", () => resolve(h.digest("hex")));
    s.on("error", reject);
  });
}

export function nowIso() {
  return new Date().toISOString();
}

// ---- resume state ----
export async function loadState() {
  const p = path.join(LIB_ROOT, "metadata", "state.json");
  return readJson(p, { completed: {}, version: 1 });
}

export async function saveState(state) {
  await writeJson(path.join(LIB_ROOT, "metadata", "state.json"), state);
}

// ---- error / duplicate collectors ----
export function newLog() {
  return [];
}
export async function appendErrors(entries) {
  const p = path.join(LIB_ROOT, "errors.json");
  const cur = await readJson(p, []);
  cur.push(...entries.map((e) => ({ ...e, logged_at: nowIso() })));
  await writeJson(p, cur);
}
