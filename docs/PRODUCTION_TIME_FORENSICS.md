# PRODUCTION_TIME_FORENSICS — hook_second_v1_20260924

All times measured from file mtimes + `build.json:elapsed_s`. Session window
≈ 01:45 → 02:35 (≈50 min wall, 2026-09-25).

## 1. Length forensics: why 79.06 s

```
narration          69.24 s  (11 lines, measured per-line via ffprobe)
+ lead              1.50 s
+ 10 gaps × 0.45    4.50 s
+ tail/endcard      3.60 s
= timeline         78.85 s
+ concat tolerance  0.21 s
= rendered         79.06 s
```

Narration alone (69.24 s) exceeds 60 s, so **compression below 60 s is
impossible without cutting script lines**: dropping N04+N08 (−9.68 s) and
tightening gaps to 0.3 (−1.5 s) and tail to 2.5 (−1.1 s) still lands ≈66.5 s;
reaching <60 s requires cutting ≥3 lines (≈16 s), gutting PROBLEM/EXAMPLE
beats. The director set **no duration budget** — only `assert 60 <= total <= 90`
(pass-through, not a target). 79.06 s is the arithmetic consequence of an
11-line script at the measured 1.7 words/s rate plus fixed paddings.

## 2. Wall-clock breakdown (measured)

| Phase | Evidence | Duration | Class |
|---|---|---|---|
| Asset search: 376 ffprobes → index (02:00:24) + 60 thumbs + 5 contact sheets + visual review | `.cache/mh_index.json`, sheets mtimes | ~12 min | NECESSARY but OPTIMIZABLE (MH folder unindexed; rebuilt from zero every production) |
| TTS: 11 Piper lines (02:04:27–02:04:33) | narr WAV mtimes | seconds (RTF ~0.1) | NECESSARY (negligible) |
| STT verification: 3 spot + 1 full-track transcribe (10.8 s compute) | `project_20260924_*` mtimes 02:03–02:20 | ~5 min wall (mostly queueing/reading) | NECESSARY |
| Script authoring + 4 crash-fix cycles (unpack, planner keys, style schema, m4a-silence) | 4 tracebacks, run1 master 02:15:53 | ~10 min | OPTIMIZABLE (untested schema assumptions; no dry-run of plan stage alone) |
| Render run 1 (21 trim+fit re-encodes, concat, audio chain, mux, burn) | master 02:15:53 | ~5–6 min compute | NECESSARY but OPTIMIZABLE (no segment cache) |
| Frame review (30 frames) + analysis + repair decisions | review_sheet, transcriptions 02:16–02:26 | ~10 min | NECESSARY |
| Render run 2 | `build.json elapsed_s=315` (5.25 min), master 02:26:54 | 5.25 min compute | NECESSARY but OPTIMIZABLE (re-encoded all 21 segments for a 0.6 s + audio + ASS change) |
| Re-burn only (R4 gold fix) | master 02:29:54 | ~3 min | NECESSARY |
| Reports/manifests | — | ~5 min | NECESSARY |

## 3. Top 5 time consumers

1. **Video re-encoding loops** (~13+ min compute across 2 full renders + burn;
   42 segment re-encodes + 3 concats + 3 burns at 1080×1920) — OPTIMIZABLE:
   no segment-level cache; identical pixels re-encoded 3×.
2. **From-scratch asset discovery** (~12 min) — OPTIMIZABLE: persistent indexed
   arsenal (the MH folder is invisible to `catalog.json`) would reduce this to
   a query.
3. **Manual frame-level review + analysis** (~10 min) — NECESSARY (this is what
   found the black glitch, quiet audio, weak contrast, blue-gold bug).
4. **Debug-fix cycles** (~10 min, 4 crashes) — OPTIMIZABLE (validate plan
   objects against schemas before executing; container-format check).
5. **Report/manifest writing** (~5 min) — NECESSARY (provenance requirement).

TTS/STT are noise (<1 min compute combined). Nothing was BLOCKED-waiting; no
retries occurred. Production feels slow **relative to visual complexity**
because compute went to re-encoding identical B-roll pixels, while the
graphics layer that would have justified the time was never invoked.
