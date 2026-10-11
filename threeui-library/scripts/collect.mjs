// npm run collect — enumerate the official catalog, download everything the
// account is legitimately allowed to access, record the rest as LOCKED.
// Respects: resume (metadata/state.json), retries, rate limits, dedupe, hashes.
import { promises as fs } from "node:fs";
import path from "node:path";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import {
  LIB_ROOT, ensureDirs, readJson, writeJson, slugify,
  sha256Hex, nowIso, loadState, saveState,
} from "./lib/store.mjs";
import { fetchWithRetry, mapLimit } from "./lib/fetchx.mjs";
import { buildCatalog, dirForCategory, SITE, PRO_CLI, COMMUNITY_PKG } from "./lib/catalog.mjs";

const execFileAsync = promisify(execFile);
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
const ONLY_CATEGORY = args.category || null;
const DRY_RUN = Boolean(args["dry-run"]);

const errors = [];
const onError = (e) => errors.push(e);

function depReportFor(item, npmPkgJson) {
  const deps = [];
  if (npmPkgJson?.peerDependencies) {
    for (const [k, v] of Object.entries(npmPkgJson.peerDependencies)) deps.push(`${k}@${v}`);
  }
  const blob = JSON.stringify(item.raw || {}).toLowerCase();
  if (blob.includes("gsap")) deps.push("gsap (detected in source)");
  if (blob.includes("lenis")) deps.push("lenis (detected in source)");
  if (blob.includes("webgl2")) deps.push("WebGL2");
  else if (blob.includes("webgl")) deps.push("WebGL");
  if (blob.includes("glsl") || blob.includes("shader")) deps.push("GLSL shader");
  return [...new Set(deps)];
}

function installationMd(item, npmVersion) {
  return `# Installation — ${item.name}\n\nOfficial Community source (MIT, login-free).\n\n\`\`\`bash\nnpm install ${COMMUNITY_PKG}@${npmVersion || "latest"}\n\`\`\`\n\n\`\`\`tsx\nimport { Component } from "${COMMUNITY_PKG}";\nimport "${COMMUNITY_PKG}/style.css";\n\`\`\`\n\nFull-HTML components expect runtime files at the same root-relative URLs as\nthe ThreeUI preview. Copy needed files from\n\`node_modules/${COMMUNITY_PKG}/lib-dist/assets/\` into your app's \`public/\ndirectory, or override \`sourceUrl\` / \`assetBaseUrl\` props where available.\n\nPro source (if this item is Pro-gated) is NOT on npm. With an active Pro\nmembership, authenticate once in the browser and install:\n\n\`\`\`bash\nnpx ${PRO_CLI} login\nnpx ${PRO_CLI} add <slug> --dir ./src\n\`\`\`\n\nSource: ${item.url || SITE}\n`;
}

async function downloadToFile(url, dest) {
  const res = await fetchWithRetry(url, {}, { tries: 4, onError });
  if (!res.ok) throw new Error(`HTTP ${res.status} for ${url}`);
  const buf = Buffer.from(await res.arrayBuffer());
  await fs.mkdir(path.dirname(dest), { recursive: true });
  await fs.writeFile(dest, buf);
  return { bytes: buf.length, sha256: sha256Hex(buf) };
}

async function main() {
  await ensureDirs();
  const started = nowIso();
  console.log(`[collect] building official catalog (dry-run=${DRY_RUN})…`);

  const cat = await buildCatalog({ onError });
  let items = cat.community;
  if (ONLY_CATEGORY) items = items.filter((i) => i.category === ONLY_CATEGORY);
  items.sort((a, b) => a.slug.localeCompare(b.slug));
  if (LIMIT > 0) items = items.slice(0, LIMIT);

  // locked.json: detail-page anchors we cannot verify Community source for.
  // Pro-gated ones stay LOCKED until the user authenticates with the official
  // CLI (never bypassed). --rebuild-locked drops stale/nav entries and rebuilds.
  const REBUILD_LOCKED = Boolean(args["rebuild-locked"]);
  const prevLocked = REBUILD_LOCKED ? [] : await readJson(path.join(LIB_ROOT, "locked.json"), []);
  const lockedByUrl = new Map(prevLocked.map((l) => [l.url, l]));
  for (const a of cat.anchorOnly.slice(0, 5000)) {
    if (!lockedByUrl.has(a.url)) {
      lockedByUrl.set(a.url, {
        name: a.name, category: a.category, url: a.url,
        access: "locked", reason: "pro-auth-required-or-unverified",
        note: `Run 'npx ${PRO_CLI} login' with an active Pro membership to entitle Pro source. Community items need no login.`,
        source_available: false, collected_at: started,
      });
    }
  }

  // npm package manifest (peer deps for dependency report) + tarball (download once).
  let npmPkgJson = null;
  try {
    const r = await fetchWithRetry("https://raw.githubusercontent.com/MengTo/threeui/main/package.json", {}, { onError });
    if (r.ok) npmPkgJson = JSON.parse(await r.text());
  } catch (e) { onError({ url: "package.json", note: String(e.message) }); }

  let npmTarballInfo = null;
  if (cat.npm.tarball && !DRY_RUN) {
    const dest = path.join(LIB_ROOT, "assets", "npm", `${COMMUNITY_PKG.replace("/", "-")}-${cat.npm.version}.tgz`);
    try {
      const st = await fs.stat(dest).catch(() => null);
      if (!st || st.size === 0) {
        console.log(`[collect] downloading ${cat.npm.tarball}`);
        npmTarballInfo = await downloadToFile(cat.npm.tarball, dest);
        npmTarballInfo.path = path.relative(LIB_ROOT, dest);
      } else {
        npmTarballInfo = { path: path.relative(LIB_ROOT, dest), bytes: st.size, note: "cached" };
      }
    } catch (e) { onError({ url: cat.npm.tarball, note: `npm-tarball: ${e.message}` }); }
  }

  // Per-item folders.
  const state = await loadState();
  const inventory = await readJson(path.join(LIB_ROOT, "inventory.json"), []);
  const invBySlug = new Map(inventory.map((i) => [i.slug, i]));
  const seenUrls = new Map();
  const seenSlugs = new Set();
  const duplicates = [];
  const assetIndex = await readJson(path.join(LIB_ROOT, "metadata", "asset-index.json"), {});
  let downloaded = 0, skipped = 0, updated = 0;

  await mapLimit(items, 3, async (item) => {
    try {
      const dir = dirForCategory(item.category, item.type);
      const slug = slugify(item.slug);
      const localDir = path.join(LIB_ROOT, dir, slug);
      const localPath = path.relative(LIB_ROOT, localDir);
      const urlIsFallback = !item.url;
      const urlKey = String(item.url || "").toLowerCase();
      // Identity is the slug (unique per run). Shared fallback category URLs
      // are references, not identities — only specific URLs participate in
      // URL-duplicate detection.
      if (seenSlugs.has(slug)) {
        duplicates.push({ slug, url: item.url, duplicate_of: slug, note: "same slug twice in one run", detected_at: nowIso() });
        return;
      }
      seenSlugs.add(slug);
      if (!urlIsFallback) {
        if (seenUrls.has(urlKey)) {
          duplicates.push({ slug, url: item.url, duplicate_of: seenUrls.get(urlKey), detected_at: nowIso() });
          return;
        }
        seenUrls.set(urlKey, slug);
      }

      const prev = invBySlug.get(slug);
      const bundleForPrint = cat.sourceEntries.find((e) => slugify(e.slug || e.id || e.name) === slug);
      const bundleSig = bundleForPrint && Array.isArray(bundleForPrint.files)
        ? bundleForPrint.files.map((f) => `${f.path}:${f.sha256 || f.bytes}`).join("|")
        : JSON.stringify(item.raw || {});
      const fingerprint = sha256Hex(Buffer.from(JSON.stringify({ s: slug, v: cat.npm.version, b: bundleSig })));
      if (prev && prev.fingerprint === fingerprint && state.completed[slug] && !DRY_RUN) {
        const s = await fs.stat(path.join(localDir, "metadata.json")).catch(() => null);
        if (s) { skipped += 1; return; }
      }

      const entry = {
        name: item.name, slug, category: item.category,
        url: item.url || `${SITE}/${item.category}`,
        url_is_fallback: urlIsFallback,
        type: item.type, tags: item.tags || [],
        access: "accessible", source_available: true,
        source_type: item.source_type || "community-bundle",
        package: COMMUNITY_PKG, version: cat.npm.version,
        dependencies: depReportFor(item, npmPkgJson),
        assets: item.raw?.fileList || [],
        local_path: localDir ? localPath.replace(/\\/g, "/") : "",
        fingerprint, collected_at: nowIso(),
      };

      if (!DRY_RUN) {
        await fs.mkdir(path.join(localDir, "source"), { recursive: true });
        await fs.mkdir(path.join(localDir, "assets"), { recursive: true });
        // Materialize the officially exposed Community source bundle.
        // Upstream shape: { files: [{ path, language, bytes, sha256, code }], sharedFilePaths, ... }
        const bundle = cat.sourceEntries.find((e) => slugify(e.slug || e.id || e.name) === slug);
        const writtenFiles = [];
        const hashMismatches = [];
        if (bundle) {
          await fs.writeFile(path.join(localDir, "source", "bundle.json"), JSON.stringify(bundle, null, 2));
          const files = Array.isArray(bundle.files) ? bundle.files : [];
          for (const f of files) {
            if (!f || !f.path || typeof f.code !== "string") continue;
            // Guard: only relative in-bundle paths, never absolute/parent escapes.
            const rel = String(f.path).replace(/\\/g, "/").replace(/^\/+/, "");
            if (!rel || rel.includes("..") || path.isAbsolute(rel)) {
              onError({ slug, url: item.url, note: `unsafe bundle path skipped: ${f.path}` });
              continue;
            }
            const dest = path.join(localDir, "source", rel);
            await fs.mkdir(path.dirname(dest), { recursive: true });
            await fs.writeFile(dest, f.code, "utf8");
            const actual = sha256Hex(Buffer.from(f.code, "utf8"));
            const expected = f.sha256;
            const ok = !expected || actual === String(expected).replace(/^SHA-256\s*/i, "");
            if (!ok) hashMismatches.push({ path: rel, expected, actual });
            writtenFiles.push({ path: rel, bytes: Buffer.byteLength(f.code), sha256: actual, verified: ok });
          }
          if (Array.isArray(bundle.sharedFilePaths) && bundle.sharedFilePaths.length) {
            await fs.writeFile(path.join(localDir, "source", "shared-files.json"), JSON.stringify(bundle.sharedFilePaths, null, 2));
          }
        }
        if (hashMismatches.length) onError({ slug, url: item.url, note: `sha256 mismatch: ${JSON.stringify(hashMismatches).slice(0, 300)}` });
        entry.written_files = writtenFiles;
        entry.shared_files = Array.isArray(bundle?.sharedFilePaths) ? bundle.sharedFilePaths : [];
        // Binary/public assets (fonts, images, models...): official GitHub Community
        // repo raw files (MIT) — verified against the recorded SHA-256 digests.
        // Deduped via asset-index so the same bytes are never downloaded twice.
        const GH_RAW = "https://raw.githubusercontent.com/MengTo/threeui/main";
        const declaredAssets = Array.isArray(bundle?.assets) ? bundle.assets : [];
        const downloadedAssets = [];
        for (const a of declaredAssets) {
          try {
            if (!a || !a.path) continue;
            const rel = String(a.path).replace(/\\/g, "/").replace(/^\/+/, "");
            if (!rel || rel.includes("..")) { onError({ slug, note: `unsafe asset path skipped: ${a.path}` }); continue; }
            const key = String(a.sha256 || `${rel}:${a.bytes || 0}`);
            const base = rel.split("/").pop();
            let destName = base;
            const indexed = assetIndex[key];
            if (indexed) {
              const srcAbs = path.join(LIB_ROOT, indexed.path);
              const exists = await fs.stat(srcAbs).catch(() => null);
              if (exists && exists.size > 0) {
                destName = base;
                const dest = path.join(localDir, "assets", destName);
                if (path.resolve(dest) !== path.resolve(srcAbs)) await fs.copyFile(srcAbs, dest);
                downloadedAssets.push({ path: rel, local: `assets/${destName}`, bytes: exists.size, sha256: a.sha256 || null, deduped: true });
                continue;
              }
            }
            const res = await fetchWithRetry(`${GH_RAW}/${rel}`, {}, { tries: 4, onError });
            if (!res.ok) { onError({ slug, url: `${GH_RAW}/${rel}`, status: res.status, note: "asset not publicly available — left for Pro/CLI path" }); continue; }
            const buf = Buffer.from(await res.arrayBuffer());
            if (a.bytes && buf.length !== a.bytes) { onError({ slug, note: `asset size mismatch ${rel}: got ${buf.length}, want ${a.bytes}` }); continue; }
            const actual = sha256Hex(buf);
            if (a.sha256 && actual !== a.sha256) { onError({ slug, note: `asset sha mismatch ${rel}` }); continue; }
            if (await fs.stat(path.join(localDir, "assets", destName)).catch(() => null)) {
              const existing = await fs.readFile(path.join(localDir, "assets", destName));
              if (sha256Hex(existing) !== actual) destName = `${actual.slice(0, 8)}-${base}`;
              else { downloadedAssets.push({ path: rel, local: `assets/${destName}`, bytes: buf.length, sha256: actual, deduped: true }); assetIndex[key] = { path: path.join(dir, slug, "assets", destName).replace(/\\/g, "/"), bytes: buf.length }; continue; }
            }
            await fs.writeFile(path.join(localDir, "assets", destName), buf);
            assetIndex[key] = { path: path.join(dir, slug, "assets", destName).replace(/\\/g, "/"), bytes: buf.length };
            downloadedAssets.push({ path: rel, local: `assets/${destName}`, bytes: buf.length, sha256: actual, verified: true });
          } catch (e) { onError({ slug, note: `asset failed ${a?.path}: ${e.message}` }); }
        }
        entry.assets = declaredAssets.map((a) => ({ path: a.path, mimeType: a.mimeType || null, bytes: a.bytes || null, sha256: a.sha256 || null }));
        entry.assets_downloaded = downloadedAssets;
        await fs.writeFile(path.join(localDir, "metadata.json"), JSON.stringify(entry, null, 2));
        await fs.writeFile(path.join(localDir, "README.md"),
          `# ${item.name}\n\n- Category: ${item.category}\n- Type: ${item.type}\n- Official URL: ${entry.url}\n- Package: \`${COMMUNITY_PKG}@${cat.npm.version || "latest"}\`\n- Access: accessible (Community, MIT)\n\nSee \`installation.md\` and \`preview-info.md\`.\n`);
        await fs.writeFile(path.join(localDir, "installation.md"), installationMd(item, cat.npm.version));
        await fs.writeFile(path.join(localDir, "preview-info.md"),
          `# Preview — ${item.name}\n\nOfficial preview: ${entry.url}\n\nRemote thumbnails/previews on threeui.com are NOT redistributed locally (per Community license).\nOpen the URL above to inspect the live component before reuse.\n`);
        // Verify non-empty source marker.
        const st = await fs.stat(path.join(localDir, "metadata.json"));
        if (st.size === 0) throw new Error("empty metadata.json after write");
        state.completed[slug] = { at: nowIso(), fingerprint };
        if (prev) updated += 1; else downloaded += 1;
      } else {
        downloaded += 1;
      }
      invBySlug.set(slug, entry);
    } catch (e) {
      onError({ slug: item.slug, url: item.url, note: String(e.message) });
    }
  });

  const categories = {};
  for (const i of invBySlug.values()) categories[i.category] = (categories[i.category] || 0) + 1;

  if (!DRY_RUN) {
    await writeJson(path.join(LIB_ROOT, "inventory.json"), [...invBySlug.values()]);
    await writeJson(path.join(LIB_ROOT, "categories.json"), { updated_at: nowIso(), counts: categories, categories: (await readJson(path.join(LIB_ROOT, "categories.json"), {})).categories || undefined });
    await writeJson(path.join(LIB_ROOT, "locked.json"), [...lockedByUrl.values()]);
    await writeJson(path.join(LIB_ROOT, "duplicates.json"), duplicates);
    await writeJson(path.join(LIB_ROOT, "metadata", "asset-index.json"), assetIndex);
    await saveState(state);
    // errors.json: append new errors this run.
    if (errors.length) {
      const cur = await readJson(path.join(LIB_ROOT, "errors.json"), []);
      await writeJson(path.join(LIB_ROOT, "errors.json"), [...cur, ...errors.map((e) => ({ ...e, logged_at: nowIso() }))]);
    }
    // Dependency report.
    await writeJson(path.join(LIB_ROOT, "metadata", "dependencies.json"), {
      generated_at: nowIso(), package: COMMUNITY_PKG, version: cat.npm.version,
      peerDependencies: npmPkgJson?.peerDependencies || {},
      dependencies: npmPkgJson?.dependencies || {},
      notes: ["react/react-dom/three are peer deps", "three128/three165 aliases bundled", "GSAP/Lenis/WebGL2/GLSL recorded per-item when detected"],
    });
  }

  const failed = errors.length;
  console.log(`\nTHREEUI COLLECTION REPORT (collect)\nTotal discovered: ${cat.community.length + cat.anchorOnly.length}\nAccessible: ${cat.community.length}\nLocked: ${lockedByUrl.size}\nDownloaded: ${downloaded}\nSkipped: ${skipped}\nUpdated: ${updated}\nDuplicates: ${duplicates.length}\nFailed: ${failed}`);
  console.log(`Categories: ${JSON.stringify(categories)}`);
  if (cat.sourceShapeUnrecognized) console.log("[collect] NOTE: upstream source-code.json shape changed; recorded for inspection in errors log.");
}

main().catch((e) => { console.error("[collect] fatal:", e); process.exit(1); });
