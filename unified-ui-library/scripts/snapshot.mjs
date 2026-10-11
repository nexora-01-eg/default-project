// npm run origin-inventory — enumerate the OriginKit catalog from OFFICIAL
// PUBLIC pages only (homepage, /category/*, /sections*). No /api (robotsdisallowed),
// no auth, no bypass. Pages are cached under metadata/pages/ (24h) so reruns
// and update mode don't refetch. Output: metadata/originkit-registry.json.
import { promises as fs } from "node:fs";
import path from "node:path";
import { ULIB_ROOT, readJson, writeJson, nowIso, parseArgs } from "./lib/store.mjs";
import { fetchTextRetry } from "./lib/fetchx.mjs";

const SITE = "https://www.originkit.dev";
const PAGES = [
  "", "sections",
  "category/image-gallery", "category/interactive-elements", "category/animation",
  "category/background-animation", "category/games", "category/text",
  "category/button", "category/border", "category/image", "category/cursor",
  "category/loader", "sections/category/hero", "sections/category/features",
  "sections/category/pricing", "sections/category/cta", "sections/category/footer",
];

const args = parseArgs();
const REFRESH = Boolean(args.refresh);
const errors = [];

function field(src, key) {
  const m = src.match(new RegExp(`\\\\"${key}\\\\"\\s*:\\s*\\\\"((?:[^\\\\"]|\\\\.)*)\\\\"`, ""));
  return m ? m[1].replace(/\\"/g, '"') : null;
}
function fieldNum(src, key) {
  const m = src.match(new RegExp(`\\\\"${key}\\\\"\\s*:\\s*(\\d+)`, ""));
  return m ? Number(m[1]) : null;
}
function fieldBool(src, key) {
  const m = src.match(new RegExp(`\\\\"${key}\\\\"\\s*:\\s*(true|false)`, ""));
  return m ? m[1] === "true" : null;
}

/** Extract component/section registry entries from Next.js-escaped page HTML.
 * Strategy: locate the escaped `"registry":[` array, balance brackets while
 * skipping backslash-escapes, unescape one level, JSON.parse. Robust against
 * field order and nested content. */
export function extractRegistry(html) {
  const out = [];
  const BS = String.fromCharCode(92); // backslash (avoid escape hell)
  const Q = String.fromCharCode(34); // double quote
  const key = BS + Q + "registry" + BS + Q + ":[";
  let from = 0;
  while (true) {
    const k = html.indexOf(key, from);
    if (k < 0) break;
    let i = k + key.length - 1; // at '['
    let depth = 0;
    let end = -1;
    for (; i < html.length; i += 1) {
      const c = html[i];
      if (c === BS) { i += 1; continue; } // skip escaped char
      if (c === "[") depth += 1;
      else if (c === "]") {
        depth -= 1;
        if (depth === 0) { end = i; break; }
      }
    }
    if (end < 0) break;
    const raw = html.slice(k + key.length - 1, end + 1);
    // Unescape one level: \" -> " (real backslash escapes left for JSON.parse).
    const unesc = raw.split(BS + Q).join(Q);
    try {
      const arr = JSON.parse(unesc);
      if (Array.isArray(arr)) {
        for (const e of arr) {
          if (!e || typeof e.name !== "string") continue;
          if (e.kind !== "component" && e.kind !== "section") continue;
          out.push({
            name: e.name,
            displayName: String(e.displayName || e.name).slice(0, 200),
            kind: e.kind,
            category: e.category || "uncategorized",
            galleryMedia: e.galleryMedia || null,
            galleryPoster: e.galleryPoster || null,
            description: String(e.description || "").slice(0, 600),
            paid: typeof e.paid === "boolean" ? e.paid : null,
            featured: e.featured === true,
            copyCount: typeof e.copyCount === "number" ? e.copyCount : 0,
            createdAt: e.createdAt || null,
          });
        }
      }
    } catch (e) {
      errors.push({ note: `registry-parse: ${String(e.message).slice(0, 120)}` });
    }
    from = end + 1;
  }
  return out;
}

async function main() {
  const pagesDir = path.join(ULIB_ROOT, "metadata", "pages");
  await fs.mkdir(pagesDir, { recursive: true });
  const byName = new Map();
  const pageStats = [];

  for (const p of PAGES) {
    const file = path.join(pagesDir, (p || "home").replace(/\//g, "_") + ".html");
    let html = null;
    const st = await fs.stat(file).catch(() => null);
    const fresh = st && Date.now() - st.mtimeMs < 24 * 3600 * 1000;
    if (st && fresh && !REFRESH) {
      html = await fs.readFile(file, "utf8");
    } else {
      try {
        const r = await fetchTextRetry(`${SITE}/${p}`, { onError: (e) => errors.push(e) });
        if (!r.ok) { errors.push({ url: `${SITE}/${p}`, status: r.status, note: "page-fetch" }); continue; }
        html = r.text;
        await fs.writeFile(file, html, "utf8");
      } catch (e) {
        errors.push({ url: `${SITE}/${p}`, note: String(e.message) });
        continue;
      }
    }
    const entries = extractRegistry(html);
    let added = 0;
    for (const e of entries) {
      if (!byName.has(e.name)) { byName.set(e.name, { ...e, pages: [p || "home"] }); added += 1; }
      else {
        const prev = byName.get(e.name);
        // Merge-fill: keep the richest record.
        for (const k of ["description", "galleryMedia", "galleryPoster", "createdAt"]) {
          if (!prev[k] && e[k]) prev[k] = e[k];
        }
        if (e.paid !== null && prev.paid === null) prev.paid = e.paid;
        if (!prev.pages.includes(p || "home")) prev.pages.push(p || "home");
      }
    }
    pageStats.push({ page: p || "home", entries: entries.length, new: added });
  }

  const registry = [...byName.values()].sort((a, b) => a.name.localeCompare(b.name));
  const kinds = {}, cats = {};
  let paidTrue = 0, paidFalse = 0, paidNull = 0;
  for (const e of registry) {
    kinds[e.kind] = (kinds[e.kind] || 0) + 1;
    cats[e.category] = (cats[e.category] || 0) + 1;
    if (e.paid === true) paidTrue += 1;
    else if (e.paid === false) paidFalse += 1;
    else paidNull += 1;
  }

  await writeJson(path.join(ULIB_ROOT, "metadata", "originkit-registry.json"), registry);
  await writeJson(path.join(ULIB_ROOT, "metadata", "snapshot-meta.json"), {
    taken_at: nowIso(), source: SITE, pages: pageStats,
    totals: { items: registry.length, kinds, categories: cats, paidTrue, paidFalse, paidNull },
  });
  const cur = await readJson(path.join(ULIB_ROOT, "errors.json"), []);
  await writeJson(path.join(ULIB_ROOT, "errors.json"), [...cur, ...errors.map((e) => ({ ...e, logged_at: nowIso(), phase: "snapshot" }))]);

  console.log(`[snapshot] items=${registry.length} kinds=${JSON.stringify(kinds)} paid=${paidTrue}/${paidFalse}/null:${paidNull} errors=${errors.length}`);
}

main().catch((e) => { console.error("[snapshot] fatal:", e); process.exit(1); });
