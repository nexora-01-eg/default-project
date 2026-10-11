import { promises as fs } from "node:fs";
const files = [
  ["buttons/liquid-metal-button", "src/shaders/liquid-metal-button/liquid-metal-button.html"],
  ["heroes/globe-study", "src/shaders/text-path-studies/sources/text-on-a-path.html"],
  ["heroes/constellation-field", "src/shaders/neuform-isolated/sources/constellation-field.html"],
  ["heroes/constellation-field", "src/shaders/neuform-isolated/sources/particle-network.html"],
  ["shaders/spark-badge", "src/shaders/spark-badge/spark-badge.html"],
  ["shaders/uplink-loader", "src/shaders/uplink-loader/uplink-loader.html"],
  ["shaders/matrix-field", "src/shaders/neuform-isolated/sources/matrix-field.html"],
  ["shaders/wireframe-forms", "src/shaders/neuform-isolated/sources/wireframe-forms.html"],
  ["shaders/diagnostics-panel", "src/shaders/neuform-isolated/sources/diagnostics-panel.html"],
  ["heroes/performance-gauges", "src/shaders/neuform-isolated/sources/performance-gauges.html"],
  ["shaders/gallery-heading", "src/shaders/neuform-isolated/sources/gallery-heading.html"],
  ["shaders/article-headings", "src/shaders/neuform-isolated/sources/glassblown-neon.html"],
];
for (const [item, rel] of files) {
  const p = ["..", "threeui-library", item, "source", ...rel.split("/")].join("/");
  const code = await fs.readFile(p, "utf8");
  const refs = [...code.matchAll(/(?:src|href)=["'](?!https?:|data:|#|\/)([^"']+)["']/gi)].map((m) => m[1]);
  console.log(`${rel.split("/").pop()} :: relative-refs: ${refs.length ? refs.join(",") : "-"}`);
}
