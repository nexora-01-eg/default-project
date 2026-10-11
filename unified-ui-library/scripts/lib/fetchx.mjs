// Polite fetch with retry (public GETs only). No auth, no /api (robots-disallowed).
const DELAY_MS = 700;
let lastCall = 0;
export const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function polite() {
  const wait = Math.max(0, DELAY_MS + lastCall - Date.now());
  if (wait > 0) await sleep(wait);
  lastCall = Date.now();
}

export async function fetchTextRetry(url, { tries = 4, onError = null } = {}) {
  let lastErr = null;
  for (let a = 1; a <= tries; a += 1) {
    try {
      await polite();
      const ctrl = new AbortController();
      const t = setTimeout(() => ctrl.abort(), 45000);
      const res = await fetch(url, {
        signal: ctrl.signal,
        headers: { "User-Agent": "unified-ui-library/1.0 (+local dev use; polite crawl)" },
      });
      clearTimeout(t);
      if (res.ok) return { ok: true, status: 200, text: await res.text() };
      onError?.({ url, attempt: a, status: res.status, note: "http-status" });
      if ([401, 403, 404, 410].includes(res.status)) return { ok: false, status: res.status, text: "" };
      lastErr = new Error(`HTTP ${res.status}`);
    } catch (e) {
      lastErr = e;
      onError?.({ url, attempt: a, status: 0, note: String(e?.message || e) });
    }
    await sleep(800 * 2 ** (a - 1));
  }
  throw lastErr || new Error(`fetch failed: ${url}`);
}

export async function mapLimit(items, limit, fn) {
  const out = new Array(items.length);
  let i = 0;
  await Promise.all(
    new Array(Math.min(limit, items.length)).fill(0).map(async () => {
      while (true) {
        const idx = i++;
        if (idx >= items.length) return;
        out[idx] = await fn(items[idx], idx);
      }
    })
  );
  return out;
}
