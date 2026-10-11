// npm run report — ORIGINKIT COLLECTION REPORT + best components +
// THREEUI vs ORIGINKIT verdicts (offline).
import path from "node:path";
import { ULIB_ROOT, readJson } from "./lib/store.mjs";

async function main() {
  const inventory = await readJson(path.join(ULIB_ROOT, "inventory.json"), []);
  const locked = await readJson(path.join(ULIB_ROOT, "locked.json"), []);
  const dupes = await readJson(path.join(ULIB_ROOT, "duplicates.json"), []);
  const nears = await readJson(path.join(ULIB_ROOT, "near-duplicates.json"), []);
  const quality = await readJson(path.join(ULIB_ROOT, "metadata", "quality.json"), []);
  const snap = await readJson(path.join(ULIB_ROOT, "metadata", "snapshot-meta.json"), {});
  const errors = await readJson(path.join(ULIB_ROOT, "errors.json"), []);

  const origin = inventory.filter((i) => i.source === "OriginKit");
  const byStatus = {};
  for (const i of origin) byStatus[i.status] = (byStatus[i.status] || 0) + 1;
  const structural = nears.filter((n) => n.status === "DUPLICATE_STRUCTURAL").length;
  const nearOnly = nears.length - structural;
  const variants = origin.filter((i) => i.status === "variant").length;
  const paidLocked = locked.filter((l) => l.reason === "paid-gated").length;
  const acctLocked = locked.length - paidLocked;

  console.log(`
ORIGINKIT COLLECTION REPORT

OriginKit discovered: ${snap?.totals?.items ?? origin.length}
Accessible (metadata + motion previews): ${origin.length}
Locked (code): ${locked.length}  [paid-gated: ${paidLocked} · account-required: ${acctLocked}]
Downloaded (source files): 0  (no official downloadable code endpoint; /api is robots-disallowed)
Unique: ${byStatus.unique || 0}
Exact duplicates: ${dupes.length}
Structural duplicates: ${structural}
Near duplicates: ${nearOnly}
Variants: ${variants}
Failed: ${errors.length}
Skipped (already inventoried): 0`);

  console.log(`\nBEST COMPONENTS FROM ORIGINKIT (quality score, public signals only):`);
  for (const q of [...quality].sort((a, b) => b.quality_score - a.quality_score).slice(0, 15)) {
    console.log(` ${String(q.quality_score).padStart(3)}  ${q.slug}  → ${q.verdict.preferred} (${q.verdict.reason || ""})`.slice(0, 130));
  }

  console.log(`\nTHREEUI vs ORIGINKIT:`);
  const wins = { ThreeUI: 0, OriginKit: 0, "OriginKit-unique": 0 };
  for (const q of quality) {
    const p = q.verdict.preferred;
    if (p === "ThreeUI") wins.ThreeUI += 1;
    else if (p === "OriginKit") wins.OriginKit += 1;
    else wins["OriginKit-unique"] += 1;
  }
  console.log(` ThreeUI preferred: ${wins.ThreeUI} (verified local source wins every overlap)`);
  console.log(` OriginKit preferred: ${wins.OriginKit}`);
  console.log(` OriginKit unique (no counterpart): ${wins["OriginKit-unique"]}`);
  console.log(`\nNote: OriginKit code is access-gated, so ThreeUI wins all overlaps by default until code access is granted.`);
}

main().catch((e) => { console.error("[report] fatal:", e); process.exit(1); });
