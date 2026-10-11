// npm run update — re-snapshot (fresh fetch), diff vs previous registry,
// re-run dedupe+compare, rebuild unified outputs, report new/changed.
import { spawnSync } from "node:child_process";
import path from "node:path";
import { ULIB_ROOT, readJson } from "./lib/store.mjs";

function run(script, extra = []) {
  const r = spawnSync("node", [`./scripts/${script}`, ...extra], { cwd: ULIB_ROOT, encoding: "utf8" });
  process.stdout.write(r.stdout || "");
  if (r.status !== 0) { process.stderr.write(r.stderr || ""); throw new Error(`${script} failed`); }
}

async function main() {
  const before = await readJson(path.join(ULIB_ROOT, "metadata", "originkit-registry.json"), []);
  const beforeMap = new Map(before.map((e) => [e.name, JSON.stringify([e.displayName, e.description, e.galleryMedia, e.paid])]));
  console.log(`[update] baseline: ${before.length} items. Re-scanning OriginKit…`);
  run("snapshot.mjs", ["--refresh"]);
  run("collect-origin.mjs");
  const after = await readJson(path.join(ULIB_ROOT, "metadata", "originkit-registry.json"), []);
  const afterMap = new Map(after.map((e) => [e.name, JSON.stringify([e.displayName, e.description, e.galleryMedia, e.paid])]));
  const added = after.filter((e) => !beforeMap.has(e.name));
  const changed = after.filter((e) => beforeMap.has(e.name) && beforeMap.get(e.name) !== afterMap.get(e.name));
  const removed = before.filter((e) => !afterMap.has(e.name));
  console.log(`\nUPDATE DIFF\nnew: ${added.length}\nchanged: ${changed.length}\nremoved: ${removed.length}`);
  for (const e of added.slice(0, 30)) console.log(` + ${e.name} (${e.category})`);
  for (const e of changed.slice(0, 30)) console.log(` ~ ${e.name}`);
  for (const e of removed.slice(0, 30)) console.log(` - ${e.name}`);
}

main().catch((e) => { console.error("[update] fatal:", e); process.exit(1); });
