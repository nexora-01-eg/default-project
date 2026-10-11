// npm run dedupe — 4-level duplicate detection: OriginKit vs ThreeUI index,
// plus OriginKit-internal variant families. Source-free honesty: structural
// verdicts without both sources are marked provisional, never exact.
// Output: duplicates.json (exact), near-duplicates.json (structural+near),
// metadata/originkit-families.json. Supports --limit N (sample test).
import path from "node:path";
import { ULIB_ROOT, readJson, writeJson, nowIso, parseArgs } from "./lib/store.mjs";
import { loadThreeUIIndex } from "./lib/threeui-index.mjs";
import { normalizeName, tokenSet, jaccard, familyKey, animationTags, ORIGIN_TO_UNIFIED } from "./lib/textx.mjs";

const args = parseArgs();
const LIMIT = args.limit ? Number(args.limit) : 0;

function originRecord(e) {
  const blob = [e.displayName, e.name, e.category, e.description].join(" ");
  return {
    source: "OriginKit",
    name: e.displayName || e.name,
    slug: e.name,
    norm: normalizeName(e.displayName || e.name),
    normSlug: normalizeName(e.name),
    unified: e.kind === "section" ? "sections" : ORIGIN_TO_UNIFIED[e.category] || "interactive",
    type: e.kind === "section" ? `${e.category}-section` : `${e.category}-component`,
    category: e.category,
    kind: e.kind,
    url: `https://www.originkit.dev/${e.kind === "section" ? "sections" : "components"}/${e.name}`,
    tokens: tokenSet(blob),
    anim: animationTags(blob),
    family: familyKey(e.name),
    paid: e.paid,
    raw: e,
  };
}

async function main() {
  const registry = await readJson(path.join(ULIB_ROOT, "metadata", "originkit-registry.json"), []);
  const threeui = await loadThreeUIIndex();
  const byNorm = new Map(threeui.map((t) => [t.norm, t]));
  const bySlug = new Map(threeui.map((t) => [normalizeName(t.slug), t]));

  let queue = registry;
  if (LIMIT > 0) {
    // Sample biased to include likely overlaps for a meaningful test.
    const prefer = ["predictive-arc", "globe-study", "structure-flow", "halftone-bloom", "ascii-rain"];
    const picked = [];
    for (const p of prefer) {
      const hit = registry.find((r) => r.name === p);
      if (hit) picked.push(hit);
    }
    for (const r of registry) {
      if (picked.length >= LIMIT) break;
      if (!picked.includes(r)) picked.push(r);
    }
    queue = picked;
  }

  const exact = [];
  const near = [];
  const families = new Map();

  for (const e of queue) {
    const o = originRecord(e);
    // L4 — family grouping (within OriginKit).
    if (!families.has(o.family)) families.set(o.family, []);
    families.get(o.family).push(o.slug);

    // L1 — exact: slug or normalized-name match against ThreeUI.
    const hit = bySlug.get(o.normSlug) || byNorm.get(o.norm);
    if (hit) {
      exact.push({
        name: o.name, slug: o.slug, source: "OriginKit",
        status: "DUPLICATE_EXACT",
        duplicate_of: hit.slug, duplicate_of_source: "ThreeUI",
        reason: "identical slug/normalized name in both libraries",
        comparison: `origin:${o.slug} ⇔ threeui:${hit.slug} (metadata-level: ThreeUI holds verified source; OriginKit code is access-gated)`,
        unified: o.unified,
        detected_at: nowIso(),
      });
      continue;
    }

    // L2/L3 — score every ThreeUI item; keep best.
    let best = null;
    for (const t of threeui) {
      const jt = jaccard(o.tokens, t.tokens);
      const sharedAnim = o.anim.filter((a) => t.anim.includes(a));
      const sameCat = o.unified === t.unified;
      // Structural requires same role + shared animation tech + strong tokens.
      const structural = sameCat && sharedAnim.length >= 2 && jt >= 0.30;
      const score = jt + (sameCat ? 0.15 : 0) + Math.min(0.2, sharedAnim.length * 0.05);
      if (!best || score > best.score) best = { slug: t.slug, jt, sharedAnim, sameCat, structural, score };
    }
    if (best && best.structural) {
      near.push({
        name: o.name, slug: o.slug, source: "OriginKit",
        status: "DUPLICATE_STRUCTURAL",
        duplicate_of: best.slug, duplicate_of_source: "ThreeUI",
        reason: `same category (${o.unified}), shared animation tech [${best.sharedAnim.join(", ")}], token overlap ${best.jt.toFixed(2)} — provisional, OriginKit source unverified`,
        comparison: `token-jaccard=${best.jt.toFixed(2)} anim=[${best.sharedAnim.join(",")}]`,
        provisional: true,
        unified: o.unified,
        detected_at: nowIso(),
      });
    } else if (best && best.score >= 0.35) {
      near.push({
        name: o.name, slug: o.slug, source: "OriginKit",
        status: "NEAR_DUPLICATE",
        duplicate_of: best.slug, duplicate_of_source: "ThreeUI",
        reason: `functional overlap (score ${best.score.toFixed(2)}): ${best.sameCat ? "same category; " : ""}shared tech [${best.sharedAnim.join(", ") || "—"}]`,
        comparison: `token-jaccard=${best.jt.toFixed(2)}`,
        unified: o.unified,
        detected_at: nowIso(),
      });
    }
    // else: UNIQUE (recorded at collect time).
  }

  const famOut = [...families.entries()]
    .filter(([, v]) => v.length > 1)
    .map(([family, members]) => ({ family, members: members.sort(), count: members.length }))
    .sort((a, b) => b.count - a.count);

  if (!LIMIT) {
    await writeJson(path.join(ULIB_ROOT, "duplicates.json"), exact);
    await writeJson(path.join(ULIB_ROOT, "near-duplicates.json"), near);
    await writeJson(path.join(ULIB_ROOT, "metadata", "originkit-families.json"), famOut);
  }
  console.log(`[dedupe] scanned=${queue.length} exact=${exact.length} structural/near=${near.length} families=${famOut.length}${LIMIT ? " (SAMPLE — not saved)" : ""}`);
  for (const d of [...exact, ...near].slice(0, 15)) {
    console.log(` - [${d.status}] origin:${d.slug} ⇔ threeui:${d.duplicate_of}`);
  }
}

main().catch((e) => { console.error("[dedupe] fatal:", e); process.exit(1); });
