// npm run compare — quality scoring (public signals only, documented) +
// preferred-source verdicts for overlapping components. Supports --limit N.
import path from "node:path";
import { ULIB_ROOT, readJson, writeJson, nowIso, parseArgs } from "./lib/store.mjs";
import { loadThreeUIIndex } from "./lib/threeui-index.mjs";
import { fileURLToPath } from "node:url";

const isMain = process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1];

const args = parseArgs();
const LIMIT = args.limit ? Number(args.limit) : 0;

/** OriginKit score 0–100 from officially exposed public signals. */
export function originScore(e) {
  let s = 0;
  const why = [];
  if (e.description) { s += 15; why.push("has description"); }
  if (e.galleryPoster) { s += 10; why.push("has poster"); }
  if (e.galleryMedia) { s += 15; why.push("has motion preview"); }
  if (e.featured) { s += 15; why.push("featured by OriginKit"); }
  if (e.copyCount > 0) { const p = Math.min(10, Math.round(Math.log10(e.copyCount + 1) * 5)); s += p; why.push(`copied ${e.copyCount}×`); }
  if (e.createdAt) {
    const ageDays = (Date.now() - new Date(e.createdAt).getTime()) / 86400000;
    const p = Math.max(0, Math.min(10, Math.round(10 - ageDays / 60)));
    s += p; why.push("recency");
  }
  if (e.paid !== true) { s += 15; why.push("not paywalled"); }
  if ((e.description || "").length > 120) { s += 10; why.push("rich description"); }
  return { score: Math.min(100, s), why };
}

/** ThreeUI score 0–100: source availability dominates (verified local files). */
export function threeuiScore(t) {
  let s = 0;
  const why = [];
  if (t.hasSource) { s += 40; why.push("verified local source"); }
  if (t.files.length >= 3) { s += 10; why.push(`${t.files.length} source files`); }
  if (t.deps.length) { s += 10; why.push("documented dependencies"); }
  if (t.anim.length >= 2) { s += 10; why.push(`tech: ${t.anim.slice(0, 3).join(",")}`); }
  if (t.tokens.size > 8) { s += 10; why.push("rich metadata"); }
  s += 10; why.push("MIT Community licensed");
  return { score: Math.min(100, s), why: why.slice(0, 5) };
}

async function main() {
  const registry = await readJson(path.join(ULIB_ROOT, "metadata", "originkit-registry.json"), []);
  const threeui = await loadThreeUIIndex();
  const dupes = await readJson(path.join(ULIB_ROOT, "duplicates.json"), []);
  const nears = await readJson(path.join(ULIB_ROOT, "near-duplicates.json"), []);
  const bySlug = new Map(threeui.map((t) => [t.slug, t]));

  let queue = registry;
  if (LIMIT > 0) queue = queue.slice(0, LIMIT);

  const compared = queue.map((e) => {
    const o = originScore(e);
    const overlap = [...dupes, ...nears].find((d) => d.slug === e.name);
    let verdict = { preferred: "OriginKit-unique", reason: "no ThreeUI counterpart" };
    if (overlap) {
      const t = bySlug.get(overlap.duplicate_of);
      const ts = t ? threeuiScore(t) : { score: 0, why: [] };
      if (ts.score >= o.score) {
        verdict = { preferred: "ThreeUI", reason: `ThreeUI ${ts.score} vs OriginKit ${o.score}: verified local source wins (OriginKit code access-gated)` };
      } else {
        verdict = { preferred: "OriginKit", reason: `OriginKit ${o.score} vs ThreeUI ${ts.score}` };
      }
      verdict.threeui_score = ts.score;
      verdict.overlap = overlap.status;
      verdict.overlap_with = overlap.duplicate_of;
    }
    return {
      slug: e.name, displayName: e.displayName, quality_score: o.score,
      quality_why: o.why, verdict, compared_at: nowIso(),
    };
  });

  if (!LIMIT) await writeJson(path.join(ULIB_ROOT, "metadata", "quality.json"), compared);
  const top = [...compared].sort((a, b) => b.quality_score - a.quality_score).slice(0, 10);
  console.log(`[compare] scored=${compared.length}${LIMIT ? " (SAMPLE — not saved)" : ""}`);
  for (const t of top) console.log(` - ${t.quality_score} ${t.slug} → ${t.verdict.preferred}`);
}

if (isMain) main().catch((e) => { console.error("[compare] fatal:", e); process.exit(1); });
