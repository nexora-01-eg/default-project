// Text + semantic helpers for duplicate detection and the search index.
import { createHash } from "node:crypto";

const STOP = new Set([
  "the", "a", "an", "and", "or", "of", "to", "in", "on", "with", "for", "is",
  "that", "this", "it", "as", "by", "at", "from", "into", "your", "you", "with",
  "component", "components", "effect", "effects", "section", "design", "page",
  "web", "site", "website", "modern", "drop", "code", "framer", "free",
]);

export function normalizeName(s) {
  return String(s || "").toLowerCase().replace(/[^a-z0-9]+/g, "");
}

export function tokens(s) {
  return String(s || "")
    .toLowerCase()
    .replace(/[^a-z0-9\s-]/g, " ")
    .split(/[\s-]+/)
    .map((t) => t.trim())
    .filter((t) => t.length > 1 && !STOP.has(t));
}

export function tokenSet(...texts) {
  return new Set(texts.flatMap(tokens));
}

export function jaccard(a, b) {
  if (!a.size && !b.size) return 0;
  let inter = 0;
  for (const t of a) if (b.has(t)) inter += 1;
  return inter / (a.size + b.size - inter);
}

export function shaHex(s) {
  return createHash("sha256").update(String(s), "utf8").digest("hex");
}

/** Family key: strips trailing variant suffixes like /02, -2, v3, " 2". */
export function familyKey(slug) {
  return String(slug || "")
    .toLowerCase()
    .replace(/[/_-]?(0?[2-9]|v[2-9]|\d{2,})$/, "")
    .replace(/[-_ ]?(2|3|4|ii|iii|iv|two|three)$/, "");
}

export const ANIMATION_KEYWORDS = [
  "shader", "webgl", "glsl", "particle", "particles", "cursor", "scroll",
  "hover", "spring", "magnetic", "marquee", "parallax", "3d", "three",
  "canvas", "trail", "ripple", "wave", "vortex", "galaxy", "fluid", "liquid",
  "glass", "glow", "neon", "halftone", "dither", "ascii", "pixel", "globe",
  "orbit", "carousel", "gallery", "flip", "reveal", "morph", "distortion",
  "loader", "background", "text", "button", "border", "cursor-follow",
  "mouse", "pointer", "drag", "physics", "chromatic", "bloom", "noise",
  "grid", "fire", "smoke", "water", "ink",
];

export function animationTags(...texts) {
  const blob = ` ${texts.join(" ").toLowerCase()} `;
  const out = [];
  for (const k of ANIMATION_KEYWORDS) {
    const key = k.trim();
    if (!key) continue;
    if (key === "3d" ? /\b3d\b/.test(blob) : blob.includes(key)) out.push(key);
  }
  return [...new Set(out)];
}

export function frameworkTags(...texts) {
  const blob = texts.join(" ").toLowerCase();
  const out = [];
  if (blob.includes("framer")) out.push("framer");
  if (blob.includes("react")) out.push("react");
  if (blob.includes("next")) out.push("next.js");
  if (blob.includes("vue")) out.push("vue");
  if (blob.includes("html") || blob.includes("full html")) out.push("html");
  if (blob.includes("tailwind")) out.push("tailwind");
  return [...new Set(out)];
}

// OriginKit category → unified category.
export const ORIGIN_TO_UNIFIED = {
  hero: "heroes",
  features: "features",
  pricing: "pricing",
  cta: "cta",
  footer: "navigation",
  "background-animation": "backgrounds",
  "interactive-elements": "interactive",
  text: "text-animation",
  "image-gallery": "galleries",
  image: "galleries",
  animation: "motion",
  button: "buttons",
  cursor: "interactive",
  loader: "motion",
  games: "interactive",
  border: "buttons",
};

// ThreeUI category → unified category.
export const THREEUI_TO_UNIFIED = {
  hero: "heroes",
  "landing-pages": "templates",
  sections: "sections",
  backgrounds: "backgrounds",
  "three-js": "3d",
  css: "motion",
  buttons: "buttons",
  "text-animation": "text-animation",
  "ui-elements": "interactive",
  "motion-design": "motion",
  components: "interactive",
  shaders: "webgl",
};
