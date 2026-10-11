// npm run inventory — rebuild inventory.json / categories.json / duplicates.json
// from local item folders + locked.json (no network).
import { promises as fs } from "node:fs";
import path from "node:path";
import { LIB_ROOT, DATA_DIRS, readJson, writeJson, nowIso } from "./lib/store.mjs";
import { SITE } from "./lib/catalog.mjs";

const ITEM_DIRS = DATA_DIRS.filter((d) => !["assets", "metadata"].includes(d));

async function main() {
  const inventory = [];
  const seenSlug = new Set();
  const seenUrl = new Map();
  const duplicates = [];
  for (const dir of ITEM_DIRS) {
    const base = path.join(LIB_ROOT, dir);
    const entries = await fs.readdir(base, { withFileTypes: true }).catch(() => []);
    for (const e of entries) {
      if (!e.isDirectory()) continue;
      const metaPath = path.join(base, e.name, "metadata.json");
      const meta = await readJson(metaPath, null);
      if (!meta) continue;
      // Self-heal older metadata: flag shared category fallback URLs so they
      // never count as URL duplicates.
      if (meta.url_is_fallback === undefined) {
        meta.url_is_fallback = meta.url === `${SITE}/${meta.category}`;
        await writeJson(metaPath, meta);
      }
      inventory.push(meta);
      const slugK = String(meta.slug).toLowerCase();
      if (seenSlug.has(slugK)) duplicates.push({ slug: meta.slug, url: meta.url, duplicate_of: slugK, note: "same slug in two folders", detected_at: nowIso() });
      else seenSlug.add(slugK);
      // Only specific (non-fallback) URLs participate in URL-duplicate detection.
      if (!meta.url_is_fallback && meta.url) {
        const k = String(meta.url).toLowerCase();
        if (seenUrl.has(k)) duplicates.push({ slug: meta.slug, url: meta.url, duplicate_of: seenUrl.get(k), detected_at: nowIso() });
        else seenUrl.set(k, meta.slug);
      }
    }
  }
  inventory.sort((a, b) => String(a.slug).localeCompare(String(b.slug)));
  const counts = {};
  for (const i of inventory) counts[i.category || "unknown"] = (counts[i.category || "unknown"] || 0) + 1;
  await writeJson(path.join(LIB_ROOT, "inventory.json"), inventory);
  const prevCats = await readJson(path.join(LIB_ROOT, "categories.json"), {});
  await writeJson(path.join(LIB_ROOT, "categories.json"), { updated_at: nowIso(), counts, categories: prevCats.categories });
  await writeJson(path.join(LIB_ROOT, "duplicates.json"), duplicates);
  const locked = await readJson(path.join(LIB_ROOT, "locked.json"), []);
  console.log(`[inventory] items=${inventory.length} locked=${locked.length} duplicates=${duplicates.length}`);
  console.log(JSON.stringify(counts, null, 2));
}
main().catch((e) => { console.error("[inventory] fatal:", e); process.exit(1); });
