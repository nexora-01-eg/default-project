// Nour Organizer Pro Max — offline renderer (AR/EN + dashboard + toasts).
let LANG = "ar";
let currentDir = "";
let lastScan = { files: [], stats: {}, total: 0 };
let lastDupGroups = [];

const CAT_COLORS = { Images: "#38bdf8", Videos: "#a78bfa", Documents: "#fbbf24", Programs: "#f472b6", Audio: "#34d399", Archives: "#fb7185", Others: "#94a3b8" };

const T = {
  ar: {
    navDash: "لوحة التحكم", navOrg: "التنظيم", navDup: "المكرر", navStats: "المساحة",
    safe: "حذف آمن لسلة المهملات فقط", scan: "افحص", preview: "معاينة التنظيم",
    org: "رتّب الآن في ثانية", orgShort: "رتّب الآن", dupScan: "اكشف المكرر",
    kFiles: "ملفات", kSize: "الحجم الكلي", kCats: "تصنيفات", kDup: "مجموعات مكررة",
    storageTitle: "توزيع المساحة", quickTitle: "إجراءات سريعة", planTitle: "خطة التنظيم",
    dupTitle: "الملفات المكررة — حذف آمن", statsTitle: "إيه واكل مساحتك؟",
    found: (n) => `لقينا ${n} ملف`, dupFound: (n) => `لقينا ${n} مجموعة مكررة`,
    noDup: "مفيش ملفات مكررة 🎉 — جهازك نضيف", trashed: "اتنقل لسلة المهملات ✅",
    organized: (n) => `اتنظم ${n} ملف بنجاح ✨`, previewDone: "المعاينة جاهزة — راجعها قبل التنفيذ",
    keep: "✅ احتفاظ", recycle: "🗑️ سلة المهملات", planHint: "بنعمل معاينة الأول — مفيش حاجة بتتحرك غير لما تدوس رتّب.",
  },
  en: {
    navDash: "Dashboard", navOrg: "Organize", navDup: "Duplicates", navStats: "Storage",
    safe: "Safe delete to Recycle Bin only", scan: "Scan", preview: "Preview",
    org: "Organize in 1 second", orgShort: "Organize now", dupScan: "Find duplicates",
    kFiles: "Files", kSize: "Total size", kCats: "Categories", kDup: "Duplicate groups",
    storageTitle: "Storage breakdown", quickTitle: "Quick actions", planTitle: "Organize plan",
    dupTitle: "Duplicates — safe delete", statsTitle: "What's eating your space?",
    found: (n) => `Found ${n} files`, dupFound: (n) => `Found ${n} duplicate groups`,
    noDup: "No duplicates 🎉 — clean!", trashed: "Moved to Recycle Bin ✅",
    organized: (n) => `Organized ${n} files ✨`, previewDone: "Preview ready — review before applying",
    keep: "✅ Keep", recycle: "🗑️ Recycle", planHint: "Dry-run first — nothing moves until you confirm.",
  },
};

function fmt(b) {
  if (!b && b !== 0) return "—";
  if (b === 0) return "0 B";
  const u = ["B", "KB", "MB", "GB", "TB"];
  const i = Math.min(Math.floor(Math.log(b) / Math.log(1024)), 4);
  return `${(b / 1024 ** i).toFixed(1)} ${u[i]}`;
}

function toast(msg, err = false) {
  const box = document.getElementById("toasts");
  const d = document.createElement("div");
  d.className = "toast" + (err ? " err" : "");
  d.textContent = msg;
  box.appendChild(d);
  setTimeout(() => d.remove(), 3200);
}

function t(k) { return T[LANG][k]; }

function applyLang() {
  document.querySelectorAll("[data-i18n]").forEach((el) => {
    const k = el.getAttribute("data-i18n");
    if (typeof T[LANG][k] === "string") el.textContent = T[LANG][k];
  });
  document.documentElement.lang = LANG;
  document.documentElement.dir = LANG === "ar" ? "rtl" : "ltr";
  document.getElementById("langBtn").textContent = LANG === "ar" ? "EN" : "عربي";
  document.getElementById("brandName").textContent = "Nour Organizer";
  renderAll();
}

function badge(cat) {
  const c = CAT_COLORS[cat] || "#94a3b8";
  return `<span class="badge" style="background:${c}22;color:${c};border:1px solid ${c}55">${cat}</span>`;
}

function donutSVG(stats) {
  const total = Object.values(stats).reduce((a, s) => a + s.size, 0);
  if (!total) return `<div class="empty">—</div>`;
  let acc = 0;
  const R = 54, C = 2 * Math.PI * R;
  const segs = Object.entries(stats).sort((a, b) => b[1].size - a[1].size).map(([cat, s]) => {
    const frac = s.size / total;
    const dash = `${(frac * C).toFixed(1)} ${(C - frac * C).toFixed(1)}`;
    const off = (-acc * C).toFixed(1);
    acc += frac;
    return `<circle r="${R}" cx="70" cy="70" fill="none" stroke="${CAT_COLORS[cat] || "#888"}" stroke-width="16" stroke-dasharray="${dash}" stroke-dashoffset="${off}" stroke-linecap="butt" transform="rotate(-90 70 70)"/>`;
  }).join("");
  return `<svg width="140" height="140" viewBox="0 0 140 140">${segs}</svg>`;
}

function renderAll() {
  const { stats, total, files } = lastScan;
  const totalSize = files.reduce((a, f) => a + f.size, 0);
  document.getElementById("kFiles").textContent = total || "—";
  document.getElementById("kSize").textContent = total ? fmt(totalSize) : "—";
  document.getElementById("kCats").textContent = Object.keys(stats).length || "—";
  document.getElementById("kDup").textContent = lastDupGroups.length || "—";
  document.getElementById("kFilesSub").textContent = currentDir;
  document.getElementById("donut").innerHTML = donutSVG(stats);
  document.getElementById("donutTotal").textContent = fmt(totalSize);
  const max = Math.max(1, ...Object.values(stats).map((s) => s.size));
  document.getElementById("legend").innerHTML = Object.entries(stats).sort((a, b) => b[1].size - a[1].size)
    .map(([cat, s]) => `<div class="leg"><span class="dot" style="background:${CAT_COLORS[cat]}"></span><b>${cat}</b><span class="muted">${s.count} • ${fmt(s.size)}</span></div>`).join("");
  document.getElementById("stats").innerHTML = Object.entries(stats).sort((a, b) => b[1].size - a[1].size)
    .map(([cat, s]) => `<div class="bar-row">${badge(cat)}<div class="track"><div class="fill" style="width:${Math.round((s.size / max) * 100)}%;background:${CAT_COLORS[cat]}"></div></div><span>${s.count} • ${fmt(s.size)}</span></div>`).join("") || `<div class="empty">—</div>`;
  document.getElementById("quickStats").innerHTML = Object.entries(stats).sort((a, b) => b[1].size - a[1].size).slice(0, 3)
    .map(([cat, s]) => `<div class="bar-row">${badge(cat)}<div class="track"><div class="fill" style="width:${Math.round((s.size / max) * 100)}%;background:${CAT_COLORS[cat]}"></div></div><span>${fmt(s.size)}</span></div>`).join("");
  const pill = document.getElementById("dupCount");
  pill.textContent = lastDupGroups.length;
  pill.classList.toggle("hidden", !lastDupGroups.length);
}

async function doScan() {
  const btn = document.getElementById("btnScan");
  btn.disabled = true;
  try {
    lastScan = await window.organizer.scan(currentDir);
    document.getElementById("scanInfo").textContent = t("found")(lastScan.total);
    renderAll();
  } catch (e) { toast(String(e.message || e), true); }
  btn.disabled = false;
}

async function doOrganize(dryRun) {
  const prog = document.getElementById("progress");
  const fill = prog.querySelector(".p-fill");
  prog.classList.remove("hidden");
  fill.style.width = "30%";
  try {
    const res = await window.organizer.organize(currentDir, dryRun);
    fill.style.width = "100%";
    const list = dryRun ? res.plan : res.moved;
    document.getElementById("planCount").textContent = list.length;
    document.getElementById("plan").innerHTML = list.slice(0, 80).map((p) =>
      `<div class="plan-item">${badge(p.category)}<code>${p.from}</code><span>→</span><code>${p.to || "ERROR"}</code></div>`).join("") || `<div class="empty">—</div>`;
    toast(dryRun ? t("previewDone") : t("organized")(res.moved.filter((x) => x.to).length));
    if (!dryRun) { await doScan(); switchView("dashboard"); }
  } catch (e) { toast(String(e.message || e), true); }
  setTimeout(() => prog.classList.add("hidden"), 600);
}

async function doDups() {
  const box = document.getElementById("dups");
  box.innerHTML = `<div class="empty">…</div>`;
  try {
    const { groups } = await window.organizer.findDuplicates(currentDir);
    lastDupGroups = groups;
    renderAll();
    box.innerHTML = groups.length ? "" : `<div class="empty">${t("noDup")}</div>`;
    if (groups.length) toast(t("dupFound")(groups.length));
    groups.forEach((g, i) => {
      const div = document.createElement("div");
      div.className = "dup-group";
      div.innerHTML = `<b>#${i + 1} • ${fmt(g[0].size)} • ${g.length} files</b>`;
      g.forEach((f, idx) => {
        const row = document.createElement("div");
        row.className = "dup-file";
        const left = document.createElement("code");
        left.textContent = f.path;
        row.appendChild(left);
        if (idx > 0) {
          const b = document.createElement("button");
          b.textContent = t("recycle");
          b.onclick = async () => { await window.organizer.trash(f.path); toast(t("trashed")); row.remove(); };
          row.appendChild(b);
        } else {
          const k = document.createElement("span");
          k.textContent = t("keep");
          row.appendChild(k);
        }
        div.appendChild(row);
      });
      box.appendChild(div);
    });
  } catch (e) { toast(String(e.message || e), true); }
}

function switchView(name) {
  document.querySelectorAll(".nav").forEach((b) => b.classList.toggle("active", b.dataset.view === name));
  document.querySelectorAll(".view").forEach((v) => v.classList.toggle("active", v.id === `view-${name}`));
}

async function init() {
  document.querySelectorAll(".nav").forEach((b) => b.onclick = () => switchView(b.dataset.view));
  const folders = await window.organizer.getDefaultFolders();
  currentDir = folders.downloads;
  document.getElementById("folderPath").textContent = currentDir;
  const setDir = (d, btn) => {
    currentDir = d;
    document.getElementById("folderPath").textContent = currentDir;
    document.querySelectorAll(".seg").forEach((s) => s.classList.remove("active"));
    btn.classList.add("active");
    doScan();
  };
  document.getElementById("btnDownloads").onclick = (e) => setDir(folders.downloads, e.currentTarget);
  document.getElementById("btnDesktop").onclick = (e) => setDir(folders.desktop, e.currentTarget);
  document.getElementById("btnCustom").onclick = async (e) => {
    const res = await window.organizer.pickFolder();
    if (res && res.dir) setDir(res.dir, e.currentTarget);
  };
  document.getElementById("langBtn").onclick = () => { LANG = LANG === "ar" ? "en" : "ar"; applyLang(); };
  document.getElementById("btnScan").onclick = doScan;
  document.getElementById("btnPreview").onclick = () => { switchView("organize"); doOrganize(true); };
  document.getElementById("btnPreview2").onclick = () => doOrganize(true);
  document.getElementById("btnOrganize").onclick = () => { switchView("organize"); doOrganize(false); };
  document.getElementById("btnOrganize2").onclick = () => doOrganize(false);
  document.getElementById("btnDup").onclick = doDups;
  document.getElementById("btnDup2").onclick = () => { switchView("duplicates"); doDups(); };
  applyLang();
  doScan();
}

init();
