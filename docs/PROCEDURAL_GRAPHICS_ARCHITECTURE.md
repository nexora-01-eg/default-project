# Procedural Graphics Architecture

## Providers and contracts

- **svgwrite adapter**: stat cards, lower thirds, callouts, arrows — JSON contract {kind,title,body,w,h,colors} → deterministic SVG file (smoke: `stat.svg`, valid XML). Rasterization needs Chromium/resvg (pending) — SVG currently ships as vector sidecar.
- **Pillow path**: fullscreen stat cards / title cards / thumbnails as PNG segments (smoke: "87% FASTER" gold-on-dark card, frame-verified). Latin + numerals only — Arabic raster shaping needs arabic_reshaper/python-bidi (TIER 2, not installed), so Arabic text stays in the libass path where shaping is correct.
- **Fabric/Paper/ECharts/Vega/Mermaid/three.js**: contract-level only (TIER 2) behind the future Chromium runtime.
- **vtracer + scour**: documented path for logo/icon vectorization + SVG optimization (not yet wired).

## Consistency rules

Single palette per production (BLACK/GOLD verified in smoke), one font family in burns (Arial path), uniform saturation treatment option (smoke used restrained, documented), distinct-sources cap with reuse accounting (visual_review ASSET_REPETITION).
