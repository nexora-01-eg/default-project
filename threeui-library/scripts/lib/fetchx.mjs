// Polite, rate-limited fetch with retries. No auth bypass: only plain public GETs.
// Pro endpoints are NEVER called without a user-created OAuth session.
const DEFAULT_DELAY_MS = 450;
let lastCall = 0;

export function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

export async function politeDelay(minMs = DEFAULT_DELAY_MS) {
  const now = Date.now();
  const wait = Math.max(0, minMs + lastCall - now);
  if (wait > 0) await sleep(wait);
  lastCall = Date.now();
}

/**
 * fetchWithRetry — GET with exponential backoff for transient failures.
 * Logs every failed attempt to the provided onError collector, never throws
 * for HTTP 404/403 (returns { ok:false }) so the caller can mark LOCKED/skip.
 */
export async function fetchWithRetry(url, options = {}, retry = {}) {
  const { tries = 4, baseMs = 800, timeoutMs = 30000, onError = null } = retry;
  let attempt = 0;
  let lastErr = null;
  while (attempt < tries) {
    attempt += 1;
    try {
      await politeDelay();
      const ctrl = new AbortController();
      const t = setTimeout(() => ctrl.abort(), timeoutMs);
      const res = await fetch(url, {
        ...options,
        signal: ctrl.signal,
        headers: {
          "User-Agent": "threeui-library-collector/1.0 (+local dev use; polite crawl)",
          Accept: options?.headers?.Accept || "*/*",
          ...(options?.headers || {}),
        },
      });
      clearTimeout(t);
      if (res.ok) return res;
      // 404/403/401 on public pages: NOT retried as bypass — record and stop.
      if ([401, 403, 404, 410].includes(res.status)) {
        onError?.({ url, attempt, status: res.status, note: "non-retryable public status" });
        return res;
      }
      // 429/5xx: retry with backoff.
      lastErr = new Error(`HTTP ${res.status} for ${url}`);
      onError?.({ url, attempt, status: res.status, note: "retryable status" });
    } catch (err) {
      lastErr = err;
      onError?.({ url, attempt, status: 0, note: String(err?.message || err) });
    }
    const backoff = baseMs * 2 ** (attempt - 1) + Math.floor(Math.random() * 250);
    await sleep(backoff);
  }
  throw lastErr || new Error(`Failed to fetch ${url}`);
}

export async function fetchJson(url, retry) {
  const res = await fetchWithRetry(url, { headers: { Accept: "application/json" } }, retry);
  if (!res.ok) return { ok: false, status: res.status, data: null };
  try {
    return { ok: true, status: 200, data: await res.json() };
  } catch (err) {
    retry?.onError?.({ url, attempt: 0, status: 200, note: `json-parse-failed: ${err.message}` });
    return { ok: false, status: 200, data: null };
  }
}

export async function fetchText(url, retry) {
  const res = await fetchWithRetry(url, { headers: { Accept: "text/html,application/json,text/plain" } }, retry);
  if (!res.ok) return { ok: false, status: res.status, text: "" };
  return { ok: true, status: 200, text: await res.text() };
}

/**
 * Run async tasks with bounded concurrency (default 3) to avoid hammering.
 */
export async function mapLimit(items, limit, fn) {
  const out = new Array(items.length);
  let i = 0;
  const workers = new Array(Math.min(limit, items.length)).fill(0).map(async () => {
    while (true) {
      const idx = i++;
      if (idx >= items.length) return;
      out[idx] = await fn(items[idx], idx);
    }
  });
  await Promise.all(workers);
  return out;
}
