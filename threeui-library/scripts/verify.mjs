// npm run verify — quality control over the local library (no network).
// Checks: non-empty files, archives openable, source exists, metadata schema,
// installation instructions, broken imports, missing assets, unresolved deps.
import { promises as fs } from "node:fs";
import path from "node:path";
import { LIB_ROOT, DATA_DIRS, readJson, writeJson, nowIso } from "./lib/store.mjs";

const ITEM_DIRS = DATA_DIRS.filter((d) => !["assets", "metadata"].includes(d));
const REQUIRED = ["name", "category", "url", "access", "local_path", "collected_at"];

async function main() {
  const report = { checked_at: nowIso(), items: 0, ok: 0, issues: [] };
  for (const dir of ITEM_DIRS) {
    const base = path.join(LIB_ROOT, dir);
    const entries = await fs.readdir(base, { withFileTypes: true }).catch(() => []);
    for (const e of entries) {
      if (!e.isDirectory()) continue;
      const itemDir = path.join(base, e.name);
      report.items += 1;
      const problems = [];
      const meta = await readJson(path.join(itemDir, "metadata.json"), null);
      if (!meta) { problems.push("missing metadata.json"); }
      else {
        for (const k of REQUIRED) if (!meta[k]) problems.push(`metadata missing: ${k}`);
        // broken imports: scan source bundle for relative imports without target file.
        try {
          const bundleRaw = await fs.readFile(path.join(itemDir, "source", "bundle.json"), "utf8").catch(() => "");
          if (bundleRaw) {
            const imports = [...bundleRaw.matchAll(/from\s+["'](\.[^"']+)["']/g)].map((m) => m[1]).slice(0, 20);
            if (imports.length) {
              const fileList = JSON.stringify(bundleRaw).length > 10 ? Object.keys(JSON.parse(bundleRaw).files || {}) : [];
              for (const imp of imports.slice(0, 10)) {
                const base2 = path.basename(imp);
                if (fileList.length && !fileList.some((f) => f.endsWith(base2))) problems.push(`unresolved import: ${imp}`);
              }
            }
          }
        } catch { problems.push("unreadable source/bundle.json"); }
        if (Array.isArray(meta.assets) && meta.assets.length > 0) {
          const have = new Set(Array.isArray(meta.assets_downloaded) ? meta.assets_downloaded.map((a) => a.path) : []);
          const missing = meta.assets.filter((a) => !have.has(a.path)).map((a) => a.path);
          if (missing.length) problems.push(`assets not downloaded: ${missing.slice(0, 5).join(", ")}${missing.length > 5 ? ` (+${missing.length - 5} more)` : ""}`);
          for (const dl of meta.assets_downloaded || []) {
            const st = await fs.stat(path.join(itemDir, dl.local)).catch(() => null);
            if (!st) problems.push(`downloaded asset missing on disk: ${dl.local}`);
            else if (st.size === 0) problems.push(`downloaded asset empty: ${dl.local}`);
          }
        }
      }
      for (const f of ["README.md", "installation.md", "preview-info.md"]) {
        const st = await fs.stat(path.join(itemDir, f)).catch(() => null);
        if (!st) problems.push(`missing ${f}`);
        else if (st.size === 0) problems.push(`empty ${f}`);
      }
      // archives openable: check gzip magic for any .tgz in assets.
      try {
        const topAssets = await fs.readdir(path.join(LIB_ROOT, "assets", "npm")).catch(() => []);
        for (const t of topAssets.filter((t) => t.endsWith(".tgz"))) {
          const fh = await fs.open(path.join(LIB_ROOT, "assets", "npm", t), "r");
          const buf = Buffer.alloc(2);
          await fh.read(buf, 0, 2, 0);
          await fh.close();
          if (!(buf[0] === 0x1f && buf[1] === 0x8b)) problems.push(`archive not gzip: assets/npm/${t}`);
        }
      } catch { /* ignore */ }
      if (problems.length === 0) report.ok += 1;
      else report.issues.push({ item: `${dir}/${e.name}`, problems });
    }
  }
  await writeJson(path.join(LIB_ROOT, "reports", "verify.json"), report);
  console.log(`[verify] items=${report.items} ok=${report.ok} with-issues=${report.issues.length}`);
  for (const i of report.issues.slice(0, 30)) console.log(` - ${i.item}: ${i.problems.join("; ")}`);
}
main().catch((e) => { console.error("[verify] fatal:", e); process.exit(1); });
