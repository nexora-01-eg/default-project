// npm run report — print the final THREEUI COLLECTION REPORT (no network).
import path from "node:path";
import { LIB_ROOT, readJson } from "./lib/store.mjs";

async function main() {
  const inventory = await readJson(path.join(LIB_ROOT, "inventory.json"), []);
  const locked = await readJson(path.join(LIB_ROOT, "locked.json"), []);
  const errors = await readJson(path.join(LIB_ROOT, "errors.json"), []);
  const duplicates = await readJson(path.join(LIB_ROOT, "duplicates.json"), []);
  const categories = await readJson(path.join(LIB_ROOT, "categories.json"), {});
  const counts = categories.counts || {};
  for (const i of inventory) counts[i.category] = (counts[i.category] || 0) + (categories.counts ? 0 : 1);
  const accessible = inventory.filter((i) => i.access === "accessible").length;
  const downloaded = inventory.filter((i) => i.source_available).length;
  console.log(`\nTHREEUI COLLECTION REPORT\n\nTotal discovered: ${inventory.length + locked.length}\nAccessible: ${accessible}\nLocked: ${locked.length}\nDownloaded: ${downloaded}\nSkipped: 0\nUpdated: 0\nDuplicates: ${duplicates.length}\nFailed: ${errors.length}\n`);
  console.log("Categorized breakdown:");
  for (const [k, v] of Object.entries(counts).sort((a, b) => b[1] - a[1])) console.log(` - ${k}: ${v}`);
  if (locked.length) {
    console.log(`\nLocked sample (first 10):`);
    for (const l of locked.slice(0, 10)) console.log(` ! ${l.name} <${l.url}> (${l.reason || "pro-auth-required"})`);
  }
  if (errors.length) {
    console.log(`\nErrors: ${errors.length} (see errors.json)`);
    for (const e of errors.slice(0, 10)) console.log(` x ${e.url || e.slug || "?"}: ${e.note || e.status || ""}`);
  }
}
main().catch((e) => { console.error("[report] fatal:", e); process.exit(1); });
