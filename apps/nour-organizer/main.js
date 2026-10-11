// Nour Organizer — Electron main process (offline, no network).
const { app, BrowserWindow, ipcMain, shell, dialog } = require("electron");
const path = require("path");
const fs = require("fs");
const crypto = require("crypto");
const { categorizeFile } = require("./lib/core");

const SKIP_FILES = new Set(["desktop.ini", "thumbs.db"]);

function safeListDir(targetDir) {
  const entries = fs.readdirSync(targetDir, { withFileTypes: true });
  const files = [];
  for (const e of entries) {
    if (!e.isFile()) continue;
    if (SKIP_FILES.has(e.name.toLowerCase())) continue;
    const full = path.join(targetDir, e.name);
    try {
      const st = fs.statSync(full);
      files.push({
        name: e.name,
        path: full,
        size: st.size,
        ext: path.extname(e.name).toLowerCase(),
        category: categorizeFile(e.name),
        mtime: st.mtimeMs,
      });
    } catch { /* locked file — skip */ }
  }
  return files;
}

function uniqueDest(dir, filename) {
  let dest = path.join(dir, filename);
  if (!fs.existsSync(dest)) return dest;
  const ext = path.extname(filename);
  const base = path.basename(filename, ext);
  let i = 1;
  while (fs.existsSync(dest)) {
    dest = path.join(dir, `${base} (${i})${ext}`);
    i += 1;
  }
  return dest;
}

function hashFile(filePath) {
  return new Promise((resolve, reject) => {
    const h = crypto.createHash("sha256");
    const s = fs.createReadStream(filePath);
    s.on("data", (d) => h.update(d));
    s.on("end", () => resolve(h.digest("hex")));
    s.on("error", reject);
  });
}

function createWindow() {
  const win = new BrowserWindow({
    height: 760,
    minHeight: 600,
    minWidth: 900,
    title: "Nour Organizer",
    webPreferences: { preload: path.join(__dirname, "preload.js") },
    width: 1100,
  });
  win.removeMenu();
  win.loadFile(path.join(__dirname, "renderer", "index.html"));
}

app.whenReady().then(() => {
  createWindow();
  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});

// ---- IPC ----
ipcMain.handle("pick-folder", async () => {
  const win = BrowserWindow.getFocusedWindow();
  const res = await dialog.showOpenDialog(win, { properties: ["openDirectory"] });
  if (res.canceled || !res.filePaths.length) return { dir: null };
  return { dir: res.filePaths[0] };
});

ipcMain.handle("get-default-folders", () => ({
  downloads: app.getPath("downloads"),
  desktop: app.getPath("desktop"),
  documents: app.getPath("documents"),
}));

ipcMain.handle("scan", (_e, targetDir) => {
  const files = safeListDir(targetDir);
  const stats = {};
  for (const f of files) {
    stats[f.category] = stats[f.category] || { count: 0, size: 0 };
    stats[f.category].count += 1;
    stats[f.category].size += f.size;
  }
  return { files, stats, total: files.length };
});

ipcMain.handle("organize", (_e, { targetDir, dryRun }) => {
  const files = safeListDir(targetDir);
  const plan = files.map((f) => ({
    from: f.path,
    to: path.join(targetDir, f.category, f.name),
    category: f.category,
    name: f.name,
  }));
  if (dryRun) return { moved: [], plan, dryRun: true };
  const moved = [];
  for (const p of plan) {
    try {
      fs.mkdirSync(path.dirname(p.to), { recursive: true });
      const dest = uniqueDest(path.dirname(p.to), path.basename(p.to));
      fs.renameSync(p.from, dest);
      moved.push({ from: p.from, to: dest, category: p.category });
    } catch (err) {
      moved.push({ from: p.from, to: null, category: p.category, error: String(err.message || err) });
    }
  }
  return { moved, plan, dryRun: false };
});

ipcMain.handle("find-duplicates", async (_e, targetDir) => {
  const files = safeListDir(targetDir);
  const bySize = new Map();
  for (const f of files) {
    if (!bySize.has(f.size)) bySize.set(f.size, []);
    bySize.get(f.size).push(f);
  }
  const groups = [];
  for (const [, sameSize] of bySize) {
    if (sameSize.length < 2 || sameSize[0].size === 0) continue;
    const byHash = new Map();
    for (const f of sameSize) {
      try {
        const h = await hashFile(f.path);
        if (!byHash.has(h)) byHash.set(h, []);
        byHash.get(h).push(f);
      } catch { /* unreadable — skip */ }
    }
    for (const [, g] of byHash) {
      if (g.length > 1) groups.push(g.map((x) => ({ name: x.name, path: x.path, size: x.size })));
    }
  }
  return { groups };
});

ipcMain.handle("trash", async (_e, filePath) => {
  // Safe delete → Windows Recycle Bin (recoverable).
  await shell.trashItem(filePath);
  return { ok: true };
});
