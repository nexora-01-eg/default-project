# ThreeUI Local Library

Reusable local copy of ThreeUI components/templates the account is officially allowed to access.
Built for reuse with OpenCode for NEXORA, SHE, client websites, and other projects.

## Official access mechanisms (discovered 2026-10-04)

| Path | What it gives | Auth |
|---|---|---|
| `npm i @designcodeio/threeui` (v1.2.0, MIT) | 50 parent components, 111 routes, 141 variants + 23 singletons (164 browse results), full source + assets | None (login-free) |
| GitHub `MengTo/threeui` raw files (`public/source-code.json`, `public/community-sync-report.json`) | Community source bundles used by the Code tab | None |
| `https://threeui.com/<category>` public pages | Titles, URLs, descriptions (metadata only) | None |
| `npx @designcodeio/threeui-cli add <slug>` (v0.1.0) | Pro implementation source bundles (NOT on npm) | **Browser OAuth PKCE required** — see below |
| ThreeUI MCP (`/mcp`) | Templates/components/prompts/source via agent | **Verified Pro membership required** |

Pricing: Pro $299 lifetime or $199/year (~679 premium items advertised).

## Authentication — Pro source (ACTION REQUIRED)

No authenticated browser/session was found in this environment, so Pro items are
recorded in `locked.json` as `locked` and are never bypassed. To entitle Pro source:

```powershell
npx @designcodeio/threeui-cli login
# a browser window opens ThreeUI sign-in + consent (OAuth PKCE).
# the session is stored with owner-only permissions and refreshed automatically.
npx @designcodeio/threeui-cli add <slug> --dir ./src
npx @designcodeio/threeui-cli logout   # when done
```

Never paste passwords, API keys, cookies, or tokens into chat. The `login`
flow above is the only supported step; after you complete it, re-run collection
and Pro items your account entitles will download normally.

## Usage

```powershell
cd threeui-library
npm run collect      # full official collection (Community now; Pro when entitled)
npm run collect -- --limit 5 --category hero     # smoke test subset
npm run collect -- --dry-run --limit 5           # plan without writing
npm run inventory    # rebuild inventory from local folders (offline)
npm run verify       # quality control (offline)
npm run update       # re-scan; download only new/changed; diff report
npm run report       # print THREEUI COLLECTION REPORT (offline)
```

Collector behavior: resume via `metadata/state.json`, 4x retry with backoff,
~450ms politeness delay, max 3 concurrent fetches, SHA-256 hashes, dedupe by
URL/slug/hash, `errors.json` log, never overwrites without version compare.

## Layout

```
threeui-library/
├── README.md  inventory.json  categories.json  locked.json
├── errors.json  duplicates.json
├── components/ templates/ landing-pages/ heroes/ sections/
├── backgrounds/ shaders/ 3d-assets/ buttons/ text-animation/
├── ui-elements/ motion-design/ variants/ assets/ metadata/ reports/
└── scripts/ (collector: collect/inventory/verify/update/report + lib/)
```

Each item: `item-name/{README.md, metadata.json, installation.md, preview-info.md, source/, assets/}`.

## License

Community component code is MIT (per upstream). Remote thumbnails/previews from
threeui.com are NOT redistributed. Pro source remains under the Pro license and
is only stored here if your entitled account downloaded it via the official CLI.
