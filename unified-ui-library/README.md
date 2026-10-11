# Unified UI Library — ThreeUI + OriginKit

One high-quality local library for OpenCode (NEXORA, SHE, client sites,
cinematic landing pages, ecommerce, 3D/WebGL, SaaS). No duplicates.

## Sources

| Source | Items | Code access | Mechanism |
|---|---|---|---|
| ThreeUI (`../threeui-library`, untouched) | 43 Community components, verified source | ✅ local, MIT | npm `@designcodeio/threeui` + GitHub |
| OriginKit (`originkit.dev`) | 546 components + 58 sections (metadata + motion previews) | 🔒 app-gated (paid flag / account) | Official public pages only — no CLI/package/MCP endpoint exists; `/api` is robots-disallowed and never touched |

## Commands

```powershell
npm run origin-inventory  # enumerate OriginKit catalog (cached 24h, --refresh to refetch)
npm run collect-origin    # full pipeline: snapshot → dedupe → compare → unified outputs
npm run collect-origin -- --limit 8   # sample test (writes nothing)
npm run dedupe             # 4-level duplicate detection (supports --limit)
npm run compare            # quality scores + preferred-source verdicts
npm run verify             # integrity checks (incl. ThreeUI untouched)
npm run report             # ORIGINKIT COLLECTION REPORT
npm run update             # re-scan, diff, download only what's new/useful
```

## Duplicate detection (4 levels)

1. **Exact** — slug/normalized-name match → `DUPLICATE_EXACT`, no second copy.
2. **Structural** — same category + shared animation tech + token overlap → provisional (OriginKit source unverified, never claimed as certain).
3. **Near-duplicate** — functional overlap score → kept as record, no source stored twice.
4. **Variants** — same family (`ribbon-glow`, `/02`, `/03`…) grouped under one family key.

Never dedupes on names alone for non-exact levels; same-category items are kept.

## Unlocking OriginKit code (requires you, in a browser)

1. Create a free account (login lives at `auth.originkit.dev`).
2. Paid-flagged items need a paid plan — no public pricing page was found; check the account/billing area after login.
3. Never paste passwords/tokens here. After you have access, tell me and I will wire the entitled download path.

## Files

`inventory.json` (unified records) · `locked.json` (gated code) ·
`duplicates.json` · `near-duplicates.json` · `categories.json` ·
`dependencies.json` · `errors.json` · `metadata/search-index.json` (agent search:
tokens + animation/framework facets) · `metadata/quality.json` ·
`metadata/originkit-registry.json` (raw enumeration) ·
`metadata/originkit-families.json` (variant groups).
Category folders hold items that have real local source; OriginKit records
live in the JSON index until code access is granted.
