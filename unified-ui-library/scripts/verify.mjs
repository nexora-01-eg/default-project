// npm run verify — integrity of the unified library (offline).
// Checks: threeui library untouched (43 items, source files present),
// unified metadata schema, locked entries have URLs, no empty outputs.
import { promises as fs } from "node:fs";
import path from "node:path";
import { ULIB_ROOT, THREEUI_ROOT, readJson, writeJson, nowIso } from "./lib/store.mjs";

const REQUIRED = ["name", "slug", "source", "original_url", "category", "type", "status"];

async function main() {
  const issues = [];
  // 1. ThreeUI untouched.
  const tInv = await readJson(path.join(THREEUI_ROOT, "inventory.json"), []);
  if (tInv.length !== 43) issues.push(`threeui inventory changed: ${tInv.length} items (expected 43)`);
  let missingSource = 0;
  for (const m of tInv.slice(0, 43)) {
    if (!m.local_path) continue;
    const st = await fs.stat(path.join(THREEUI_ROOT, m.local_path, "metadata.json")).catch(() => null);
    if (!st) missingSource += 1;
  }
  if (missingSource) issues.push(`threeui item folders missing: ${missingSource}`);

  // 2. Unified files.
  const inventory = await readJson(path.join(ULIB_ROOT, "inventory.json"), []);
  const locked = await readJson(path.join(ULIB_ROOT, "locked.json"), []);
  const dupes = await readJson(path.join(ULIB_ROOT, "duplicates.json"), []);
  const nears = await readJson(path.join(ULIB_ROOT, "near-duplicates.json"), []);
  const searchIdx = await readJson(path.join(ULIB_ROOT, "metadata", "search-index.json"), []);
  if (!inventory.length) issues.push("inventory.json empty");
  let badMeta = 0;
  for (const i of inventory) {
    for (const k of REQUIRED) if (i[k] === undefined || i[k] === null || i[k] === "") { badMeta += 1; break; }
  }
  if (badMeta) issues.push(`${badMeta} inventory entries fail schema`);
  const badLocked = locked.filter((l) => !l.original_url && !l.url).length;
  if (badLocked) issues.push(`${badLocked} locked entries without URL`);
  // 3. Cross-file consistency.
  const invSlugs = new Set(inventory.filter((i) => i.source === "OriginKit").map((i) => i.slug));
  const orphans = [...dupes, ...nears].filter((d) => !invSlugs.has(d.slug)).length;
  if (orphans) issues.push(`${orphans} dupe records without inventory entry`);

  const report = { checked_at: nowIso(), items: inventory.length, locked: locked.length, search_indexed: searchIdx.length, issues };
  await writeJson(path.join(ULIB_ROOT, "metadata", "verify.json"), report);
  console.log(`[verify] items=${inventory.length} locked=${locked.length} indexed=${searchIdx.length} issues=${issues.length}`);
  for (const i of issues.slice(0, 20)) console.log(` ! ${i}`);
}

main().catch((e) => { console.error("[verify] fatal:", e); process.exit(1); });
