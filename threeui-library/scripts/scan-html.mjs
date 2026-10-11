import { promises as fs } from "node:fs";
import path from "node:path";
const inv = JSON.parse(await fs.readFile("inventory.json", "utf8"));
async function walk(dir, out = []) {
  const ents = await fs.readdir(dir, { withFileTypes: true }).catch(() => []);
  for (const e of ents) {
    const p = path.join(dir, e.name);
    if (e.isDirectory()) await walk(p, out);
    else if (/\.html?$/i.test(e.name) && e.name !== "bundle.json") out.push(p);
  }
  return out;
}
for (const m of inv) {
  if (!m.local_path) continue;
  const files = await walk(path.join("..", "threeui-library", m.local_path, "source"));
  for (const f of files) {
    const code = await fs.readFile(f, "utf8").catch(() => "");
    if (!code) continue;
    const st = await fs.stat(f);
    const flags = [
      /type=["']module["']/i.test(code) ? "MODULE" : null,
      /\bimport\s+[^;]+?from\s+['"]/ .test(code) ? "IMPORT" : null,
      /src=["']\//.test(code) || /href=["']\//.test(code) ? "ABS-PATH" : null,
      /fetch\(|XMLHttpRequest/.test(code) ? "FETCH" : null,
      /new Worker/.test(code) ? "WORKER" : null,
    ].filter(Boolean).join(",") || "clean";
    console.log(`${Math.round(st.size / 1024)}KB [${flags}] ${m.slug} :: ${path.relative(path.join("..", "threeui-library", m.local_path, "source"), f)}`);
  }
}
