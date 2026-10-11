// Catalog enumeration using ONLY official, public ThreeUI mechanisms:
//  1. npm registry metadata for @designcodeio/threeui (Community, MIT, login-free)
//  2. GitHub Community repo raw files (source-code.json, community-sync-report.json, package.json)
//  3. threeui.com public category/browse pages (metadata: title/url/description only)
// Pro items are NEVER fetched without entitlement — they are recorded as LOCKED.
import path from "node:path";
import { fetchJson, fetchText, mapLimit } from "./fetchx.mjs";
import { LIB_ROOT, slugify } from "./store.mjs";

export const SITE = "https://threeui.com";
export const NPM_META_URL = "https://registry.npmjs.org/@designcodeio%2Fthreeui";
export const GH_RAW = "https://raw.githubusercontent.com/MengTo/threeui/main";
export const URLS = {
  npmMeta: NPM_META_URL,
  npmPackageJson: `${GH_RAW}/package.json`,
  syncReport: `${GH_RAW}/public/community-sync-report.json`,
  sourceCode: `${GH_RAW}/public/source-code.json`,
};

// 11 official top-level categories observed on threeui.com nav.
export const CATEGORIES = [
  { id: "sections", path: "/sections", dir: "sections", label: "Sections" },
  { id: "landing-pages", path: "/landing-pages", dir: "landing-pages", label: "Landing Pages" },
  { id: "3d-assets", path: "/3d-assets", dir: "3d-assets", label: "3D Assets" },
  { id: "text-animation", path: "/text-animation", dir: "text-animation", label: "Text Animation" },
  { id: "ui-elements", path: "/ui-elements", dir: "ui-elements", label: "UI Elements" },
  { id: "backgrounds", path: "/backgrounds", dir: "backgrounds", label: "Backgrounds" },
  { id: "buttons", path: "/buttons", dir: "buttons", label: "Buttons" },
  { id: "hero", path: "/hero", dir: "heroes", label: "Hero" },
  { id: "three-js", path: "/three-js", dir: "components", label: "Three.js Components" },
  { id: "css", path: "/css", dir: "components", label: "CSS" },
  { id: "motion-design", path: "/motion-design", dir: "motion-design", label: "Motion Design" },
];

export const PRO_CLI = "@designcodeio/threeui-cli";
export const COMMUNITY_PKG = "@designcodeio/threeui";

/** Map a catalog URL to a local data dir. */
export function dirForCategory(categoryId, type = "") {
  const t = String(type).toLowerCase();
  if (t.includes("shader")) return "shaders";
  if (t.includes("template")) return "templates";
  if (t.includes("variant")) return "variants";
  const found = CATEGORIES.find((c) => c.id === categoryId);
  return found ? found.dir : "components";
}

/** Detect Pro-gated entries from public metadata ONLY (no bypass attempt). */
export function isProHint(entry) {
  const blob = JSON.stringify(entry || {}).toLowerCase();
  return (
    blob.includes("get pro") ||
    blob.includes("/pricing") ||
    /(^|[^a-z])pro([^a-z]|$)/.test(blob) && blob.includes("premium") ||
    blob.includes("premium landing")
  );
}

// Navigation/listing routes are never "items" — drop them from locked candidates.
const NAV_DROP = new Set([
  "browse", "pricing", "installation", "mcp", "sponsorship", "privacy",
  "terms", "affiliates", "signin", "sign-in", "login", "api", "search", "github",
]);

/** Keep only detail-like public paths (probable components/templates). */
export function isDetailPath(p) {
  const segs = String(p || "").split("?")[0].split("#")[0].split("/").filter(Boolean);
  if (segs.length < 2) return false;
  if (NAV_DROP.has(segs[0])) return false;
  if (segs.length === 2 && segs[0] === "sections") return false; // subcategory listing
  return true;
}

/**
 * Parse public HTML category pages for anchor metadata.
 * Only extracts <a href> + link text (public navigation data).
 */
export function parseAnchors(html, base = SITE) {
  const items = [];
  const re = /<a[^>]+href="([^"]+)"[^>]*>([\s\S]{0,300}?)<\/a>/gi;
  let m;
  const seen = new Set();
  while ((m = re.exec(html)) !== null) {
    let href = m[1].trim();
    if (!href.startsWith("/")) continue;
    if (/\.(png|jpe?g|webp|svg|ico|css|js)(\?|$)/i.test(href)) continue;
    const text = m[2].replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim().slice(0, 160);
    const url = base + href.split("#")[0];
    if (seen.has(url)) continue;
    seen.add(url);
    items.push({ url, path: href.split("#")[0], title: text });
  }
  return items;
}

/**
 * Normalize the many possible shapes of public/source-code.json into items.
 * Defensive: the upstream file is a "source bundles used by the Code tab" map.
 */
export function normalizeSourceCodeJson(data) {
  if (!data) return [];
  // Shape A: { "<slug>": { files: {...}, ... } }
  // Shape B: { components: [...] } / { bundles: {...} } / [...]
  if (Array.isArray(data)) return data.map((e, i) => normalizeEntry(e, i));
  if (Array.isArray(data.components)) return data.components.map((e, i) => normalizeEntry(e, i));
  if (Array.isArray(data.items)) return data.items.map((e, i) => normalizeEntry(e, i));
  const bag = data.bundles || data.sources || data.files ? null : data;
  if (bag && typeof bag === "object" && !Array.isArray(bag)) {
    const keys = Object.keys(bag);
    // Heuristic: map-like bundle object with >3 keys and object values.
    if (keys.length > 0 && keys.every((k) => typeof bag[k] === "object") && keys.length < 5000) {
      if (keys.some((k) => /files|source|code|slug/i.test(JSON.stringify(bag[k]).slice(0, 500)))) {
        return keys.map((k) => normalizeEntry({ slug: k, ...bag[k] }, 0));
      }
    }
  }
  for (const key of ["bundles", "sources", "entries"]) {
    const v = data[key];
    if (v && typeof v === "object" && !Array.isArray(v)) {
      return Object.entries(v).map(([k, e]) => normalizeEntry({ slug: k, ...(typeof e === "object" ? e : { value: e }) }, 0));
    }
  }
  return [{ _unrecognizedShape: true, topKeys: Object.keys(data).slice(0, 20) }];
}

function normalizeEntry(e, i) {
  if (typeof e === "string") return { slug: slugify(e), name: e, _index: i };
  return {
    slug: slugify(e.slug || e.id || e.name || `entry-${i}`),
    name: e.name || e.title || e.slug || e.id || `entry-${i}`,
    ...e,
    _index: i,
  };
}

/**
 * Build the master catalog:
 *  - community[]: accessible without auth (from source-code.json + npm + site pages)
 *  - lockedHints[]: pages/entries that publicly advertise Pro gating
 */
export async function buildCatalog({ onError, includeSitePages = true } = {}) {
  const errors = [];
  const err = (e) => { errors.push(e); onError?.(e); };
  const retry = { onError: err };

  const [npmMeta, syncReport, sourceCode] = await Promise.all([
    fetchJson(URLS.npmMeta, retry),
    fetchJson(URLS.syncReport, retry),
    fetchJson(URLS.sourceCode, retry),
  ]);

  const npmVersion = npmMeta.data?.["dist-tags"]?.latest || null;
  const npmTarball = (npmVersion && npmMeta.data?.versions?.[npmVersion]?.dist?.tarball) || null;
  const npmIntegrity = (npmVersion && npmMeta.data?.versions?.[npmVersion]?.dist?.integrity) || null;

  const normalized = normalizeSourceCodeJson(sourceCode.data);
  const unrecognized = normalized.length === 1 && normalized[0]._unrecognizedShape;

  let siteAnchors = [];
  if (includeSitePages) {
    siteAnchors = (
      await mapLimit(CATEGORIES, 3, async (cat) => {
        const r = await fetchText(SITE + cat.path, retry);
        if (!r.ok) return [];
        return parseAnchors(r.text).map((a) => ({ ...a, category: cat.id }));
      })
    ).flat();
  }

  // Merge: prefer source-code.json entries (they carry real source); enrich with site anchors.
  const bySlug = new Map();
  for (const e of unrecognized ? [] : normalized) {
    if (!e || !e.slug) continue;
    bySlug.set(e.slug, {
      name: e.name || e.slug,
      slug: e.slug,
      category: e.category || guessCategory(e),
      url: e.url || e.previewUrl || null,
      type: e.type || guessType(e),
      tags: Array.isArray(e.tags) ? e.tags : [],
      referenceId: e.id || e.referenceId || null,
      access: "accessible",
      source_available: true,
      source_type: "community-bundle",
      package: COMMUNITY_PKG,
      version: npmVersion,
      raw: pickSmall(e),
    });
  }
  // Site detail-page anchors that don't match a Community bundle slug become
  // locked candidates (Pro-gated or unverified). Nav/listing routes are dropped.
  const anchorOnly = [];
  for (const a of siteAnchors) {
    if (!isDetailPath(a.path)) continue;
    const slug = slugify(a.path.split("/").filter(Boolean).pop() || a.title);
    if (!bySlug.has(slug) && a.title) {
      anchorOnly.push({
        name: a.title.slice(0, 120),
        slug,
        category: a.category,
        url: a.url,
        type: "page",
        tags: [],
        access: "unknown",
        source_available: false,
        source_type: "unverified",
        package: null,
        version: null,
      });
    }
  }

  return {
    npm: { package: COMMUNITY_PKG, version: npmVersion, tarball: npmTarball, integrity: npmIntegrity },
    syncReport: syncReport.data || null,
    sourceEntries: unrecognized ? [] : normalized,
    sourceShapeUnrecognized: unrecognized ? normalized[0] : null,
    siteAnchors,
    community: [...bySlug.values()],
    anchorOnly,
    errors,
  };
}

function guessCategory(e) {
  const blob = JSON.stringify(e).toLowerCase();
  for (const c of CATEGORIES) if (blob.includes(c.id)) return c.id;
  if (blob.includes("landing")) return "landing-pages";
  if (blob.includes("hero")) return "hero";
  return "three-js";
}

function guessType(e) {
  const blob = JSON.stringify(e).toLowerCase();
  if (blob.includes("landing")) return "landing-page";
  if (blob.includes("hero")) return "hero";
  if (blob.includes("shader") || blob.includes("glsl")) return "shader";
  if (blob.includes("background")) return "background";
  if (blob.includes("button")) return "button";
  if (blob.includes("template")) return "template";
  return "component";
}

function pickSmall(e) {
  const { files, file, code, source, ...rest } = e;
  const slim = { ...rest };
  if (files && typeof files === "object") slim.fileList = Object.keys(files).slice(0, 50);
  return slim;
}

export { LIB_ROOT };
export { path };
