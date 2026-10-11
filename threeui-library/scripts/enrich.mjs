// npm run enrich — attach officially exposed public metadata (poster image,
// description, runtime) to locked.json entries by reading each page's public
// SEO tags (og:image, JSON-LD). No login, no bypass: same public data as titles.
import { promises as fs } from "node:fs";
import path from "node:path";
import { LIB_ROOT, readJson, writeJson, nowIso } from "./lib/store.mjs";
import { fetchText, mapLimit } from "./lib/fetchx.mjs";

const rawArgs = process.argv.slice(2);
const args = {};
for (let k = 0; k < rawArgs.length; k += 1) {
  const m = rawArgs[k].match(/^--([^=\s]+)(=(.*))?$/);
  if (m) {
    if (m[3] !== undefined) args[m[1]] = m[3];
    else if (k + 1 < rawArgs.length && !rawArgs[k + 1].startsWith("--")) args[m[1]] = rawArgs[k + 1];
    else args[m[1]] = true;
  }
}
const LIMIT = args.limit ? Number(args.limit) : 0;
const REFRESH = Boolean(args.refresh);

const errors = [];
const onError = (e) => errors.push(e);

function meta(html, prop) {
  const m = html.match(new RegExp(`<meta[^>]+property="${prop}"[^>]+content="([^"]+)"`, "i"))
    || html.match(new RegExp(`<meta[^>]+content="([^"]+)"[^>]+property="${prop}"`, "i"));
  return m ? m[1] : null;
}
function metaName(html, name) {
  const m = html.match(new RegExp(`<meta[^>]+name="${name}"[^>]+content="([^"]+)"`, "i"))
    || html.match(new RegExp(`<meta[^>]+content="([^"]+)"[^>]+name="${name}"`, "i"));
  return m ? m[1] : null;
}
function decode(s) {
  return String(s || "").replace(/&amp;/g, "&").replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&quot;/g, '"').replace(/&#39;|&apos;/g, "'").slice(0, 400);
}

async function main() {
  const lockedPath = path.join(LIB_ROOT, "locked.json");
  const locked = await readJson(lockedPath, []);
  const statePath = path.join(LIB_ROOT, "metadata", "enrich-state.json");
  const state = await readJson(statePath, { done: {} });

  let queue = locked.filter((l) => l.url && (REFRESH || !l.preview_image) && !state.done[l.url]);
  if (LIMIT > 0) queue = queue.slice(0, LIMIT);
  console.log(`[enrich] ${queue.length} pages to read (state has ${Object.keys(state.done).length} done)`);

  let ok = 0;
  await mapLimit(queue, 2, async (l) => {
    try {
      const r = await fetchText(l.url, { onError });
      if (!r.ok) { state.done[l.url] = { at: nowIso(), status: r.status }; return; }
      const html = r.text;
      let ld = null;
      const ldm = html.match(/<script id="threeui-structured-data" type="application\/ld\+json">([\s\S]*?)<\/script>/);
      if (ldm) { try { ld = JSON.parse(ldm[1]); } catch { /* ignore */ } }
      l.preview_image = meta(html, "og:image") || ld?.image || l.preview_image || null;
      l.blurb = decode(meta(html, "og:description") || metaName(html, "description") || ld?.description || null);
      l.runtime = (html.match(/<p>Runtime:\s*([^<]+)<\/p>/) || [])[1]?.trim() || ld?.runtimePlatform || l.runtime || null;
      l.languages = Array.isArray(ld?.programmingLanguage) ? ld.programmingLanguage : l.languages || null;
      l.page_title = decode(meta(html, "og:title") || null);
      l.enriched_at = nowIso();
      state.done[l.url] = { at: nowIso(), status: 200 };
      ok += 1;
    } catch (e) {
      onError({ url: l.url, note: `enrich: ${e.message}` });
    }
  });

  await writeJson(lockedPath, locked);
  await writeJson(statePath, state);
  if (errors.length) {
    const cur = await readJson(path.join(LIB_ROOT, "errors.json"), []);
    await writeJson(path.join(LIB_ROOT, "errors.json"), [...cur, ...errors.map((e) => ({ ...e, logged_at: nowIso(), phase: "enrich" }))]);
  }
  console.log(`[enrich] enriched=${ok} failed=${errors.length}`);
}

main().catch((e) => { console.error("[enrich] fatal:", e); process.exit(1); });
