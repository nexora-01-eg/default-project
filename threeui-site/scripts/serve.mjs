// Zero-dependency local server. Serves the whole workspace root so the site
// (threeui-site/dist) can iframe local library renders (threeui-library/…).
// Run: npm run serve   →  http://localhost:8099/threeui-site/dist/
import http from "node:http";
import { promises as fs } from "node:fs";
import path from "node:path";

const ROOT = path.resolve(process.argv[2] || path.join(process.cwd(), ".."));
const PORT = Number(process.argv[3] || 8099);

const MIME = {
  ".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
  ".js": "text/javascript; charset=utf-8", ".mjs": "text/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8", ".svg": "image/svg+xml",
  ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
  ".webp": "image/webp", ".gif": "image/gif", ".woff": "font/woff",
  ".woff2": "font/woff2", ".ttf": "font/ttf", ".mp4": "video/mp4",
};

const server = http.createServer(async (req, res) => {
  try {
    const url = new URL(req.url, "http://x");
    let p = path.normalize(path.join(ROOT, decodeURIComponent(url.pathname)));
    if (!p.startsWith(ROOT)) { res.writeHead(403); res.end("forbidden"); return; }
    const st = await fs.stat(p).catch(() => null);
    if (st && st.isDirectory()) p = path.join(p, "index.html");
    const buf = await fs.readFile(p).catch(() => null);
    if (!buf) { res.writeHead(404); res.end("not found"); return; }
    res.writeHead(200, { "Content-Type": MIME[path.extname(p).toLowerCase()] || "application/octet-stream" });
    res.end(buf);
  } catch {
    res.writeHead(500); res.end("error");
  }
});

server.listen(PORT, () => {
  console.log(`[serve] workspace root: ${ROOT}`);
  console.log(`[serve] open: http://localhost:${PORT}/threeui-site/dist/`);
});
