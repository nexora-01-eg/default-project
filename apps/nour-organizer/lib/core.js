// Pure offline logic — shared by main process + tests (no Electron here).
const path = require("path");

const CATEGORIES = {
  Images: [".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg", ".ico", ".tiff", ".heic"],
  Videos: [".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v"],
  Documents: [".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt", ".csv", ".md", ".rtf", ".odt"],
  Programs: [".exe", ".msi", ".bat", ".cmd", ".ps1"],
  Audio: [".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a"],
  Archives: [".zip", ".rar", ".7z", ".tar", ".gz"],
};

function categorizeFile(filename) {
  const ext = path.extname(filename).toLowerCase();
  for (const [cat, exts] of Object.entries(CATEGORIES)) {
    if (exts.includes(ext)) return cat;
  }
  return "Others";
}

function groupDuplicatesBySize(files) {
  // files: [{path, size}]
  const bySize = new Map();
  for (const f of files) {
    if (!bySize.has(f.size)) bySize.set(f.size, []);
    bySize.get(f.size).push(f);
  }
  // Only groups with 2+ files of identical size AND size > 0 are candidates.
  return [...bySize.values()].filter((g) => g.length > 1 && g[0].size > 0);
}

function formatBytes(bytes) {
  if (!bytes) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  const i = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  return `${(bytes / 1024 ** i).toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
}

module.exports = { CATEGORIES, categorizeFile, groupDuplicatesBySize, formatBytes };
