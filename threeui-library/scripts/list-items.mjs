import { promises as fs } from "node:fs";
const inv = JSON.parse(await fs.readFile("inventory.json", "utf8"));
for (const m of inv) {
  const files = (m.written_files || []).map((f) => f.path.split("/").pop()).join(",");
  const assets = (m.assets_downloaded || []).map((a) => a.local.split("/").pop()).join(",");
  console.log(`${m.slug} | cat=${m.category} type=${m.type} | files: ${files} | assets: ${assets || "-"}`);
}
