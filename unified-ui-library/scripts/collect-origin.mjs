// npm run collect-origin — DISCOVER → IDENTIFY → COMPARE → CLASSIFY →
// DOWNLOAD-ONLY-IF-USEFUL. Orchestrates snapshot→dedupe→compare in-process,
// then writes the unified inventory, locked.json, search index, categories.
// OriginKit code has no official downloadable endpoint (no CLI/package/MCP
// endpoint found; /api is robots-disallowed; code is app-gated) → code is
// recorded as LOCKED, media/metadata hotlinked only, nothing reconstructed.
import path from "node:path";
import { spawnSync } from "node:child_process";
import { ULIB_ROOT, readJson, writeJson, nowIso, parseArgs } from "./lib/store.mjs";
import { loadThreeUIIndex } from "./lib/threeui-index.mjs";
import { tokenSet, animationTags, frameworkTags, familyKey, normalizeName, ORIGIN_TO_UNIFIED, THREEUI_TO_UNIFIED } from "./lib/textx.mjs";
import { originScore, threeuiScore } from "./compare.mjs";

const args = parseArgs();
const LIMIT = args.limit ? Number(args.limit) : 0;
const DRY_RUN = Boolean(args["dry-run"]);

function run(script, extra = []) {
  const r = spawnSync("node", [ `./scripts/${script}`, ...extra ], { cwd: ULIB_ROOT, encoding: "utf8" });
  process.stdout.write(r.stdout || "");
  if (r.status !== 0) { process.stderr.write(r.stderr || ""); throw new Error(`${script} failed`); }
}

async function main() {
  if (!DRY_RUN) run("snapshot.mjs", REFRESH_ARGS());
  const registry = await readJson(path.join(ULIB_ROOT, "metadata", "originkit-registry.json"), []);
  const threeui = await loadThreeUIIndex();

  if (!DRY_RUN) { run("dedupe.mjs", LIMIT ? ["--limit", String(LIMIT)] : []); run("compare.mjs", LIMIT ? ["--limit", String(LIMIT)] : []); }
  const dupes = DRY_RUN ? [] : await readJson(path.join(ULIB_ROOT, "duplicates.json"), []);
  const nears = DRY_RUN ? [] : await readJson(path.join(ULIB_ROOT, "near-duplicates.json"), []);
  const quality = DRY_RUN ? [] : await readJson(path.join(ULIB_ROOT, "metadata", "quality.json"), []);
  const qBy = new Map(quality.map((q) => [q.slug, q]));
  const bySlug = new Map(threeui.map((t) => [t.slug, t]));

  let queue = registry;
  if (LIMIT > 0) queue = queue.slice(0, LIMIT);

  const inventory = [];
  const locked = [];
  const seenFam = new Map();

  // ThreeUI side: reference entries (source stays in threeui-library untouched).
  if (!LIMIT) {
    for (const t of threeui) {
      const ts = threeuiScore(t);
      inventory.push({
        name: t.name, slug: t.slug, source: "ThreeUI",
        original_url: t.url, category: t.unified, type: t.type,
        status: "unique", preferred: true, similar_to: [],
        dependencies: t.deps, framework: t.frameworks, animation: t.anim,
        tags: [...t.tokens].slice(0, 20),
        local_path: t.local_path, quality_score: ts.score,
      });
    }
  }

  let unique = 0, skippedDup = 0;
  for (const e of queue) {
    const o = qBy.get(e.name);
    const score = o ? o.quality_score : originScore(e).score;
    const overlap = [...dupes, ...nears].find((d) => d.slug === e.name);
    const unified = e.kind === "section" ? "sections" : ORIGIN_TO_UNIFIED[e.category] || "interactive";
    const blob = [e.displayName, e.name, e.category, e.description].join(" ");
    const fam = familyKey(e.name);
    const famCount = (seenFam.get(fam) || 0) + 1;
    seenFam.set(fam, famCount);

    const base = {
      name: e.displayName || e.name, slug: e.name, source: "OriginKit",
      original_url: `https://www.originkit.dev/${e.kind === "section" ? "sections" : "components"}/${e.name}`,
      category: unified, type: e.kind === "section" ? `${e.category}-section` : `${e.category}-component`,
      preferred: false, similar_to: overlap ? [overlap.duplicate_of] : [],
      dependencies: [], framework: frameworkTags(blob, "framer react"),
      animation: animationTags(blob),
      tags: [...tokenSet(blob)].slice(0, 20),
      local_path: null, quality_score: score,
      family: famCount > 1 || registry.some((x) => x !== e && familyKey(x.name) === fam) ? fam : null,
      motion_preview: e.galleryMedia || null, poster: e.galleryPoster || null,
      collected_at: nowIso(),
    };

    // Code access: no official downloadable endpoint → LOCKED (never bypassed).
    const codeLocked = { ...base, access: "locked" };
    if (e.paid === true) {
      locked.push({ ...codeLocked, reason: "paid-gated", note: "Registry flags paid:true. Code only inside the OriginKit app — needs account + paid plan." });
    } else {
      locked.push({ ...codeLocked, reason: "account-required-unverified", note: "No paid flag, but no public code endpoint exists; app likely needs at least a free account (auth.originkit.dev)." });
    }

    if (overlap && overlap.status === "DUPLICATE_EXACT") {
      inventory.push({ ...base, status: "duplicate", duplicate_of: overlap.duplicate_of, reason: overlap.reason, comparison: overlap.comparison });
      skippedDup += 1;
    } else if (overlap && overlap.status !== "DUPLICATE_EXACT") {
      inventory.push({ ...base, status: overlap.status === "DUPLICATE_STRUCTURAL" ? "near_duplicate" : "near_duplicate", duplicate_of: overlap.duplicate_of, reason: overlap.reason, comparison: overlap.comparison });
      unique += 0; // near-dupes kept as records, no source stored
    } else {
      inventory.push({ ...base, status: base.family ? "variant" : "unique" });
      unique += 1;
    }
  }

  // Search index for future agents: tokens + facets per item.
  const searchIndex = inventory.map((i) => ({
    slug: i.slug, name: i.name, source: i.source, category: i.category,
    type: i.type, status: i.status, quality_score: i.quality_score,
    tokens: [...tokenSet(i.name, i.slug, i.category, i.type, (i.animation || []).join(" "), (i.tags || []).join(" "))],
    animation: i.animation || [], framework: i.framework || [],
    poster: i.poster || null, motion_preview: i.motion_preview || null,
    local_path: i.local_path, original_url: i.original_url,
  }));

  const counts = {};
  for (const i of inventory) counts[i.category] = (counts[i.category] || 0) + 1;

  if (!DRY_RUN && !LIMIT) {
    await writeJson(path.join(ULIB_ROOT, "inventory.json"), inventory);
    await writeJson(path.join(ULIB_ROOT, "locked.json"), locked);
    await writeJson(path.join(ULIB_ROOT, "categories.json"), { updated_at: nowIso(), counts });
    await writeJson(path.join(ULIB_ROOT, "dependencies.json"), {
      generated_at: nowIso(),
      threeui: { package: "@designcodeio/threeui", version: "1.2.0", peer: ["react>=18 <20", "react-dom>=18 <20", "three>=0.149 <1"] },
      originkit: { delivery: "Framer + React code components (in-app copy)", inferred_frameworks: ["framer", "react"], note: "No public package/CLI; dependencies per-component unknown until code access" },
    });
    await writeJson(path.join(ULIB_ROOT, "metadata", "search-index.json"), searchIndex);
    const errs = await readJson(path.join(ULIB_ROOT, "errors.json"), []);
    void errs;
  }

  console.log(`\n[collect-origin] scanned=${queue.length} unique=${unique} exact-dupes-skipped=${skippedDup} locked(code)=${locked.length}`);
}

function REFRESH_ARGS() {
  return args.refresh ? ["--refresh"] : [];
}

main().catch((e) => { console.error("[collect-origin] fatal:", e); process.exit(1); });
