// Static site generator for the local ThreeUI library.
// Reads ../threeui-library/{inventory,locked,categories}.json + per-item docs,
// emits dependency-free static HTML into ./dist (works over file://).
import { promises as fs } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const SITE = path.resolve(HERE, "..", "dist");
const LIB = path.resolve(HERE, "..", "..", "threeui-library");
const CLEAN = process.argv.includes("--clean");

const esc = (s) =>
  String(s ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");

// Minimal markdown -> HTML (fenced code blocks, inline code, paragraphs).
function md(src) {
  const parts = String(src || "").split(/```/);
  let out = "";
  parts.forEach((p, i) => {
    if (i % 2 === 1) {
      const nl = p.indexOf("\n");
      const code = nl >= 0 ? p.slice(nl + 1) : p;
      out += `<pre><code>${esc(code.replace(/\n$/, ""))}</code></pre>`;
    } else {
      out += esc(p)
        .split(/\n{2,}/)
        .map((para) => {
          const line = para.replace(/\n/g, "<br>").replace(/`([^`]+)`/g, "<code>$1</code>");
          return line.trim() ? `<p>${line}</p>` : "";
        })
        .join("\n");
    }
  });
  return out;
}

const shell = (title, body, extraHead = "") => `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${esc(title)} — ThreeUI Local Library</title>
<link rel="stylesheet" href="${extraHead === "deep" ? "../styles.css" : "styles.css"}">
</head>
<body>
<header class="topbar">
  <a class="brand" href="${extraHead === "deep" ? "../index.html" : "index.html"}">◈ ThreeUI Local Library</a>
  <nav><a href="${extraHead === "deep" ? "../index.html" : "index.html"}">Browse</a></nav>
</header>
<main class="wrap">
${body}
</main>
<footer class="foot">Local copy of officially accessible ThreeUI Community source (MIT). Remote previews belong to threeui.com and are not redistributed. Pro items require an entitled account.</footer>
</body>
</html>`;

const badge = (access) =>
  access === "accessible"
    ? `<span class="badge ok">✓ ACCESSIBLE</span>`
    : `<span class="badge lock">🔒 LOCKED · PRO</span>`;

function fmtBytes(n) {
  if (!n && n !== 0) return "—";
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}

async function main() {
  if (CLEAN) await fs.rm(SITE, { recursive: true, force: true });
  await fs.mkdir(path.join(SITE, "items"), { recursive: true });
  await fs.mkdir(path.join(SITE, "locked"), { recursive: true });

  const inventory = JSON.parse(await fs.readFile(path.join(LIB, "inventory.json"), "utf8"));
  const locked = JSON.parse(await fs.readFile(path.join(LIB, "locked.json"), "utf8"));
  const cats = JSON.parse(await fs.readFile(path.join(LIB, "categories.json"), "utf8"));

  const used = new Set();
  const slugify = (s) =>
    String(s || "item").toLowerCase().normalize("NFKD").replace(/[̀-ͯ]/g, "")
      .replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 100) || "item";
  const uniq = (base) => {
    const dot = base.lastIndexOf(".");
    const stem = dot > 0 ? base.slice(0, dot) : base;
    const ext = dot > 0 ? base.slice(dot) : "";
    let f = base, i = 2;
    while (used.has(f)) f = `${stem}-${i++}${ext}`;
    used.add(f);
    return f;
  };

  const index = [];
  let num = 0;

  // ---------- accessible item pages (#1..N) ----------
  const sortedInv = [...inventory].sort((a, b) => String(a.slug).localeCompare(String(b.slug)));
  for (const m of sortedInv) {
    num += 1;
    const file = uniq(`${m.slug}.html`);
    const page = `items/${file}`;
    index.push({ num, slug: m.slug, name: m.name, category: m.category, type: m.type, access: "accessible", url: m.url, page, preview_image: m.preview_image || null });

    const itemDir = path.join(LIB, m.local_path);
    const read = async (f) => (await fs.readFile(path.join(itemDir, f), "utf8").catch(() => ""));
    const installation = await read("installation.md");

    const files = Array.isArray(m.written_files) ? m.written_files : [];
    const filesRows = files.length
      ? files.map((f) => `<tr><td><code>${esc(f.path)}</code></td><td>${fmtBytes(f.bytes)}</td><td>${f.verified ? "✓ checked" : "—"}</td></tr>`).join("\n")
      : `<tr><td colspan="3">No file list recorded.</td></tr>`;

    const assets = Array.isArray(m.assets_downloaded) ? m.assets_downloaded : [];
    const assetsRows = assets.length
      ? assets.map((a) => `<tr><td><code>${esc(a.local)}</code></td><td>${fmtBytes(a.bytes)}</td><td>${a.verified ? "✓ checked" : a.deduped ? "shared copy" : "—"}</td></tr>`).join("\n")
      : `<tr><td colspan="3">No extra files needed — code only.</td></tr>`;

    const deps = (m.dependencies || []).map((d) => `<li><code>${esc(d)}</code></li>`).join("") || "<li>—</li>";
    const tags = (m.tags || []).map((t) => `<span class="tag">${esc(t)}</span>`).join(" ") || "—";

    // Local live render: first self-contained .html file saved in source/.
    const liveFile = files.map((f) => f.path).find((p) => /\.html?$/i.test(p) && !/bundle\.json$/i.test(p)) || null;
    const liveRel = liveFile ? `../../threeui-library/${m.local_path}/source/${liveFile}` : null;
    const liveSection = liveRel
      ? `<section class="card" id="live">
  <h2>▶ Play it here — live</h2>
  <p class="note">This is your local copy running for real. If it stays blank here, open this site through the local server (<code>npm run serve</code> in <code>threeui-site</code>) instead of double-clicking the file.</p>
  <div class="preview-frame tall"><iframe src="${esc(liveRel)}" title="Live local render" loading="lazy"></iframe></div>
</section>`
      : `<section class="card" id="live">
  <h2>▶ Play it here</h2>
  <p class="note">This one is a code component (not a full page), so it runs inside your project after install — see “How to install” below. Its official online demo is one click away.</p>
  <p><a class="btn" href="${esc(m.url)}" target="_blank" rel="noopener">See it move on threeui.com ↗</a></p>
</section>`;

    const body = `
<p class="crumb"><a href="../index.html">Library</a> / ${esc(m.category)} / ${esc(m.slug)}</p>
<h1><span class="num-big">#${num}</span> ${esc(m.name)}</h1>
<p>${badge("accessible")} <span class="tag">${esc(m.category)}</span> <span class="tag">${esc(m.type || "")}</span> ${tags}</p>

${liveSection}

<section class="card" id="installation">
  <h2>How to install</h2>
  ${md(installation)}
</section>

<section class="card" id="source">
  <h2>Code files <span class="count">${files.length}</span></h2>
  <p class="note">Stored in <code>threeui-library/${esc(m.local_path)}/source/</code> — ready to copy into your project.</p>
  <table><thead><tr><th>File</th><th>Size</th><th>Check</th></tr></thead><tbody>${filesRows}</tbody></table>
</section>

<section class="card" id="assets">
  <h2>Extra files <span class="count">${assets.length}</span></h2>
  <table><thead><tr><th>File</th><th>Size</th><th>Check</th></tr></thead><tbody>${assetsRows}</tbody></table>
</section>

<section class="card" id="dependencies">
  <h2>What it needs</h2>
  <ul>${deps}</ul>
</section>

<section class="card" id="metadata">
  <h2>Details</h2>
  <pre><code>${esc(JSON.stringify({ number: num, name: m.name, slug: m.slug, category: m.category, url: m.url, type: m.type, package: m.package, version: m.version, collected_at: m.collected_at, local_path: m.local_path }, null, 2))}</code></pre>
</section>`;
    await fs.writeFile(path.join(SITE, page), shell(`#${num} ${m.name}`, body, "deep"));
  }

  // ---------- locked pages (continue numbering) ----------
  const sortedLocked = [...locked].sort((a, b) => String(a.name).localeCompare(String(b.name)));
  for (const l of sortedLocked) {
    num += 1;
    const tail = String(l.url || "").split("?")[0].split("#")[0].split("/").filter(Boolean).pop() || l.name;
    const lslug = l.slug || slugify(tail);
    const file = uniq(`${slugify(lslug)}.html`);
    const page = `locked/${file}`;
    index.push({ num, slug: lslug, name: l.name, category: l.category, type: l.type || "page", access: "locked", url: l.url, page, preview_image: l.preview_image || null });
    const poster = l.preview_image
      ? `<img class="poster" src="${esc(l.preview_image)}" alt="Official preview poster" loading="lazy" referrerpolicy="no-referrer" onerror="this.remove()">`
      : `<div class="poster ph">🔒<br><small>poster not exposed</small></div>`;
    const body = `
<p class="crumb"><a href="../index.html">Library</a> / ${esc(l.category || "")} / locked</p>
<h1><span class="num-big">#${num}</span> ${esc(l.name)}</h1>
<p>${badge("locked")} <span class="tag">${esc(l.category || "")}</span>${l.runtime ? ` <span class="tag">${esc(l.runtime)}</span>` : ""}</p>
<section class="card" id="look">
  <h2>What it looks like</h2>
  ${l.blurb ? `<p>${esc(l.blurb)}</p>` : ""}
  ${poster}
  <p><a class="btn" href="${esc(l.url)}" target="_blank" rel="noopener">See it move on threeui.com ↗</a></p>
</section>
<section class="card" id="unlock">
  <h2>How to unlock</h2>
  <p>Pro item — the code was never copied here. With an active ThreeUI Pro membership:</p>
  <pre><code>npx @designcodeio/threeui-cli login\nnpx @designcodeio/threeui-cli add ${esc(lslug)} --dir ./src</code></pre>
  <p>Then in <code>threeui-library</code> run <code>npm run update</code>, and rebuild this site with <code>npm run rebuild</code>. Tell me the number (<strong>#${num}</strong>) and I will fetch it for you.</p>
</section>`;
    await fs.writeFile(path.join(SITE, page), shell(`#${num} ${l.name}`, body, "deep"));
  }

  // ---------- index ----------
  const allCats = [...new Set(index.map((i) => i.category))].sort();
  const acc = index.filter((i) => i.access === "accessible").length;
  const lok = index.length - acc;
  const chips = ["all", "accessible", "locked", ...allCats]
    .map((c) => `<button class="chip" data-f="${esc(c)}">${esc(c)}</button>`)
    .join("\n");
  const indexBody = `
<h1>ThreeUI Local Library</h1>
<p class="stats"><strong>${acc}</strong> accessible · <strong>${lok}</strong> locked (Pro) · <strong>${index.length}</strong> total catalogued</p>
<div class="toolbar">
  <input id="q" type="search" placeholder="Type a number (#12) or a name…" autocomplete="off">
  <div class="chips">${chips}</div>
</div>
<div id="grid" class="grid"></div>
<p id="empty" class="note" hidden>No matches. Try another search or filter.</p>
<script src="data.js"></script>
<script src="app.js"></script>`;
  await fs.writeFile(path.join(SITE, "index.html"), shell("Browse", indexBody));
  await fs.writeFile(path.join(SITE, "data.js"), `window.THREEUI_INDEX = ${JSON.stringify(index)};\n`);

  await fs.writeFile(path.join(SITE, "app.js"), `// Client-side search + filter (no network, works over file://).
const grid = document.getElementById("grid");
const q = document.getElementById("q");
const empty = document.getElementById("empty");
let active = "all";
const chips = [...document.querySelectorAll(".chip")];
function paintChips() { chips.forEach((c) => c.classList.toggle("on", c.dataset.f === active)); }
chips.forEach((c) => c.addEventListener("click", () => { active = c.dataset.f; paintChips(); render(); }));
q.addEventListener("input", render);
function card(i) {
  const lock = i.access === "accessible"
    ? '<span class="badge ok">✓ FREE</span>'
    : '<span class="badge lock">🔒 PRO</span>';
  const img = i.preview_image
    ? '<img class="thumb" src="' + i.preview_image + '" alt="" loading="lazy" referrerpolicy="no-referrer" onerror="this.remove()">'
    : '<div class="thumb ph"><span>' + esc((i.type || "?").slice(0, 1).toUpperCase()) + '</span></div>';
  return '<a class="item" href="' + i.page + '">' +
    '<div class="num">#' + i.num + '</div>' + img +
    '<div class="item-top">' + lock + '<span class="tag">' + esc(i.category) + '</span></div>' +
    '<h3>' + esc(i.name) + '</h3>' +
    '<p class="muted">' + esc(i.type || "") + '</p></a>';
}
function esc(s) { return String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;"); }
function render() {
  const term = q.value.trim().toLowerCase();
  const list = window.THREEUI_INDEX.filter((i) => {
    if (active === "accessible" && i.access !== "accessible") return false;
    if (active === "locked" && i.access !== "locked") return false;
    if (!["all", "accessible", "locked"].includes(active) && i.category !== active) return false;
    if (term && !(i.name + " " + i.slug + " " + i.category + " " + (i.type || "") + " #" + i.num + " " + i.num).toLowerCase().includes(term)) return false;
    return true;
  });
  grid.innerHTML = list.map(card).join("");
  empty.hidden = list.length > 0;
}
paintChips(); render();
`);

  await fs.writeFile(path.join(SITE, "styles.css"), `:root { --bg: #0c0e14; --card: #151926; --line: #262c40; --txt: #e8eaf2; --mut: #9aa1b8; --acc: #6ee7b7; --warn: #fbbf24; --btn: #4f7cff; }
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--txt); font-family: "Segoe UI", system-ui, Arial, sans-serif; }
.topbar { display: flex; justify-content: space-between; align-items: center; padding: 12px 20px; border-bottom: 1px solid var(--line); background: #10141f; position: sticky; top: 0; }
.brand { color: var(--txt); text-decoration: none; font-weight: 700; }
.topbar nav a { color: var(--mut); text-decoration: none; margin-left: 16px; }
.wrap { max-width: 1100px; margin: 0 auto; padding: 24px 20px 60px; }
.foot { text-align: center; color: var(--mut); font-size: 12px; padding: 24px; border-top: 1px solid var(--line); }
.stats { color: var(--mut); }
.toolbar { display: flex; flex-direction: column; gap: 12px; margin: 16px 0 20px; }
#q { padding: 12px 14px; border-radius: 10px; border: 1px solid var(--line); background: var(--card); color: var(--txt); font-size: 15px; }
.chips { display: flex; flex-wrap: wrap; gap: 8px; }
.chip { padding: 6px 12px; border-radius: 999px; border: 1px solid var(--line); background: transparent; color: var(--mut); cursor: pointer; }
.chip.on { background: var(--btn); border-color: var(--btn); color: #fff; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); gap: 14px; }
.item { display: block; background: var(--card); border: 1px solid var(--line); border-radius: 12px; padding: 14px; text-decoration: none; color: var(--txt); }
.item:hover { border-color: var(--btn); }
.item h3 { margin: 10px 0 4px; font-size: 16px; }
.muted { color: var(--mut); font-size: 12px; margin: 0; }
.badge { font-size: 11px; font-weight: 700; padding: 3px 8px; border-radius: 6px; }
.badge.ok { background: #123f2c; color: var(--acc); }
.badge.lock { background: #3f2f12; color: var(--warn); }
.tag { font-size: 11px; color: var(--mut); border: 1px solid var(--line); padding: 3px 8px; border-radius: 6px; margin-right: 4px; }
.card { background: var(--card); border: 1px solid var(--line); border-radius: 12px; padding: 18px; margin: 16px 0; }
.card h2 { margin-top: 0; }
.count { font-size: 12px; color: var(--mut); }
.note { color: var(--mut); font-size: 13px; }
.crumb { color: var(--mut); font-size: 13px; }
.crumb a { color: var(--mut); }
.preview-frame iframe { width: 100%; height: 480px; border: 1px solid var(--line); border-radius: 8px; background: #fff; }
.preview-frame.tall iframe { height: 640px; background: #000; }
.poster { width: 100%; border-radius: 8px; border: 1px solid var(--line); }
.poster.ph { aspect-ratio: 1200/630; display: grid; place-items: center; color: var(--mut); font-size: 40px; background: #10141f; text-align: center; }
.num { position: absolute; top: 10px; left: 10px; background: #000c; border: 1px solid var(--line); font-weight: 800; font-size: 15px; padding: 3px 10px; border-radius: 8px; }
.num-big { color: var(--btn); font-size: 0.7em; }
.item { position: relative; padding: 0; overflow: hidden; }
.item .item-top, .item h3, .item .muted { padding-left: 14px; padding-right: 14px; }
.item .muted { padding-bottom: 14px; }
.item-top { margin-top: 12px; }
.thumb { width: 100%; aspect-ratio: 1200/630; object-fit: cover; display: block; background: #10141f; border-bottom: 1px solid var(--line); }
.thumb.ph { display: grid; place-items: center; font-size: 64px; font-weight: 800; color: #2c3450; }
.btn { display: inline-block; background: var(--btn); color: #fff; padding: 10px 16px; border-radius: 8px; text-decoration: none; margin: 10px 12px 0 0; }
.pkg { color: var(--mut); font-size: 13px; }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th, td { text-align: left; padding: 8px; border-bottom: 1px solid var(--line); }
code { background: #0a0d15; padding: 2px 6px; border-radius: 5px; font-size: 12.5px; }
pre { background: #0a0d15; padding: 14px; border-radius: 8px; overflow-x: auto; }
pre code { background: none; padding: 0; }
ul { line-height: 1.9; }
`);

  console.log(`[site] pages: ${inventory.length} items + ${locked.length} locked = ${index.length} total`);
  console.log(`[site] output: ${SITE}`);
}

main().catch((e) => { console.error("[site] fatal:", e); process.exit(1); });
