# Installation — gallery-heading

Official Community source (MIT, login-free).

```bash
npm install @designcodeio/threeui@1.2.0
```

```tsx
import { Component } from "@designcodeio/threeui";
import "@designcodeio/threeui/style.css";
```

Full-HTML components expect runtime files at the same root-relative URLs as
the ThreeUI preview. Copy needed files from
`node_modules/@designcodeio/threeui/lib-dist/assets/` into your app's `public/
directory, or override `sourceUrl` / `assetBaseUrl` props where available.

Pro source (if this item is Pro-gated) is NOT on npm. With an active Pro
membership, authenticate once in the browser and install:

```bash
npx @designcodeio/threeui-cli login
npx @designcodeio/threeui-cli add <slug> --dir ./src
```

Source: https://threeui.com
