// npm run update — re-scan the official catalog, download only new/changed
// accessible items, leave unchanged items untouched, refresh metadata, report diff.
import { spawn } from "node:child_process";
import path from "node:path";
import { LIB_ROOT, readJson } from "./lib/store.mjs";

const args = process.argv.slice(2).join(" ");

async function runCollect() {
  await new Promise((resolve, reject) => {
    const cmd = process.platform === "win32" ? "node" : "node";
    const child = spawn(cmd, [path.join(LIB_ROOT, "scripts", "collect.mjs"), ...process.argv.slice(2)], { stdio: "inherit" });
    child.on("close", (code) => (code === 0 ? resolve() : reject(new Error(`collect exited ${code}`))));
    child.on("error", reject);
  });
}

async function main() {
  const before = await readJson(path.join(LIB_ROOT, "inventory.json"), []);
  const beforeLocked = await readJson(path.join(LIB_ROOT, "locked.json"), []);
  const beforeMap = new Map(before.map((i) => [i.slug, i.fingerprint || i.version]));
  const beforeLockedSet = new Set(beforeLocked.map((l) => l.url));
  console.log(`[update] baseline: ${before.length} inventoried, ${beforeLocked.length} locked. Re-scanning… (${args || "no extra args"})`);
  await runCollect();
  const after = await readJson(path.join(LIB_ROOT, "inventory.json"), []);
  const afterLocked = await readJson(path.join(LIB_ROOT, "locked.json"), []);
  const afterMap = new Map(after.map((i) => [i.slug, i.fingerprint || i.version]));
  const afterLockedSet = new Set(afterLocked.map((l) => l.url));
  const added = after.filter((i) => !beforeMap.has(i.slug));
  const changed = after.filter((i) => beforeMap.has(i.slug) && beforeMap.get(i.slug) !== (i.fingerprint || i.version));
  const removed = before.filter((i) => !afterMap.has(i.slug));
  const newlyUnlocked = [...beforeLockedSet].filter((u) => !afterLockedSet.has(u));
  console.log(`\nUPDATE DIFF\nnew items: ${added.length}\nupdated items: ${changed.length}\nremoved items: ${removed.length}\nnewly unlocked: ${newlyUnlocked.length}\nlocked now: ${afterLocked.length}`);
  for (const i of added.slice(0, 50)) console.log(` + ${i.slug} (${i.category})`);
  for (const i of changed.slice(0, 50)) console.log(` ~ ${i.slug} (${i.category})`);
  for (const i of removed.slice(0, 50)) console.log(` - ${i.slug}`);
}
main().catch((e) => { console.error("[update] fatal:", e); process.exit(1); });
