// ThreeUI side index for duplicate detection. Read-only: never modifies it.
import path from "node:path";
import { THREEUI_ROOT, readJson } from "./store.mjs";
import { normalizeName, tokenSet, animationTags, frameworkTags, THREEUI_TO_UNIFIED } from "./textx.mjs";

export async function loadThreeUIIndex() {
  const inv = await readJson(path.join(THREEUI_ROOT, "inventory.json"), []);
  return inv.map((m) => {
    const name = m.name || m.slug;
    const blob = [name, m.slug, m.type, m.category, (m.tags || []).join(" "), (m.dependencies || []).join(" ")].join(" ");
    return {
      source: "ThreeUI",
      name,
      slug: m.slug,
      norm: normalizeName(name),
      unified: THREEUI_TO_UNIFIED[m.category] || "interactive",
      type: m.type || "",
      category: m.category || "",
      url: m.url || null,
      tokens: tokenSet(blob),
      anim: animationTags(blob, (m.written_files || []).map((f) => f.path).join(" ")),
      frameworks: frameworkTags(blob),
      deps: m.dependencies || [],
      files: (m.written_files || []).map((f) => f.path),
      fingerprint: m.fingerprint || null,
      local_path: m.local_path ? `../threeui-library/${m.local_path}` : null,
      hasSource: (m.written_files || []).length > 0,
    };
  });
}
