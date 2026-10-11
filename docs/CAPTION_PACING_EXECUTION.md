# CAPTION_PACING_EXECUTION.md — Phase 17 (`engine/editing/caption_pacing_execution.py`)

Approval-gated execution of Phase 16 pacing recommendations. Intelligence
stays in Phase 16; this phase only validates, translates, and renders what
was explicitly approved — through the existing Phase 13 engine, Phase 14
caption mapping, and Phase 15 visual validation.

```text
CaptionPacingPlan -> approved_caption_pacing_plan.json
        -> approve-caption-pacing-execution -> derived EDL + execution plan
        -> execute-caption-pacing -> Phase 13 execute -> captions -> QC -> manifest
```

## Approval distinction

| Approval | Meaning | Artifact |
|---|---|---|
| `approve-caption-pacing` | "I approve the intelligence/recommendations." | `editing/approved_caption_pacing_plan.json` |
| `approve-caption-pacing-execution` | "These specific recommendations may become edit operations." | `editing/approved_caption_pacing_execution.json` |

The two are never merged. States: `RECOMMENDED | APPROVED | EXECUTED | INVALID`
(creation → `APPROVED`; successful render or cache reuse → `EXECUTED`).
The state/wall-clock fields are excluded from all hashes.

## Executable recommendations

- **TRIM** — only when explicitly approved, SAFE, valid range, covered by a
  base-EDL REMOVE, not explicitly unapproved by the base approval (when one
  exists), cue mapping valid, no partial cue overlap, visual preview clean.
- **SPLIT** — only when explicitly approved and SAFE. A split preserves both
  sides (no deletion); it has no timeline effect in Phase 17 and is recorded
  as boundary metadata. If it cannot be represented, it stays NOOP.

## Non-executable (planning-only, preserved as metadata)

`ACCELERATE_VISUAL`, `HOLD_LONGER`, `CHANGE_VISUAL`,
`ADD_CUTAWAY_OPPORTUNITY`, `REVIEW`, `KEEP` → modes `VISUAL_CHANGE`,
`CUTAWAY_OPPORTUNITY`, `HOLD`, `NOOP`. Never cuts, never speed changes,
never B-roll, never placement changes. Explicitly selecting one fails loudly.

## EDL compatibility

Phase 17 is not a second edit-decision engine. Every TRIM must be contained
in a base-EDL (`edit/edit_decision.json`) REMOVE; otherwise
`REJECTED / NOOP` with reason `pacing recommendation conflicts with approved
EDL`. The derived EDL (`KEEP`-all except approved TRIMs, `px_NNNN` ids,
provenance in `metadata`) is built by interval subtraction; the base EDL is
never mutated. If `editing/approved_edit_plan.json` exists it is validated,
and TRIMs over explicitly unapproved removals are rejected.

## Caption mapping (Phase 14 reused)

`map_cues_to_output` over the derived keeps. Per-cue outcomes:
`PRESERVED` (all words survive), `TRIMMED` (some dropped),
`SPLIT` (existing ≥0.8 s sub-cue behavior), `DROPPED` (none survive, with
`SOURCE_RANGE_REMOVED` word evidence). Mapped text must equal surviving-word
text; mapped words must sit inside mapped cues — else the approval fails.
A TRIM straddling a cue boundary is blocked as `PARTIAL_CAPTION_OVERLAP`.
Word order, language, style, and fonts are preserved; timestamps are mapped,
never invented.

## Visual-caption mapping (Phase 15 reused, immutable)

Placements/emphasis/adaptations are carried by cue id through the new
timeline (split sub-cues inherit via the existing base-id lookup). Positions
are never relocated. The existing `_visual_qc_checks` run on the preview at
approval time: any failure blocks with `VISUAL_CAPTION_REVIEW_REQUIRED`.
A present-but-unapproved visual plan fails loudly (no silent fallback to
standard captions). Arabic/RTL text is byte-preserved; integrity checked.

## Rendering (Phase 13 reused, nothing rewritten)

Derived EDL + derived approval → `compose_timeline` → `_execute_ops` →
`extended_qc` → `apply_captions` (caption approval mode: sidecar or
burned-in). No new FFmpeg gateway; no new subtitle renderer; no new audio
policy. Anything unrepresentable fails at plan stage, before FFmpeg.

## QC

`extended_qc` (duration, streams, A/V sync, black frames, silence, decode)
plus the caption layer QC (`verify_sidecars` / `visible_caption_check` +
visual checks + audio-preserved). Any failure → unsuccessful execution.

## Cache

Render reuse scans `renders/*_pacing_manifest.json` for `kind ==
pacing-execution`, `status == completed`, full identity match (source, base
EDL + base approval, all plan/approval hashes, execution + derived hashes,
caption mode, style, encoder, render config, code version), live output
file, and re-probed duration. Corrupt output re-renders. Never filename-only
trust.

## FFmpeg preflight

`execute-caption-pacing` checks `which_ffmpeg` + `ffprobe_path` first and
reports `FFmpeg: AVAILABLE / MISSING`. Missing binaries fail explicitly
(exit 5), create no output, never report `EXECUTED`. Dry-run is fully
offline (no media, no encoder probing).

## Failure behavior / exit codes

- `2` — approval/selection/input (`PacingExecutionError`, missing project).
- `6` — validation (drift, bad mapping, QC fail).
- `5` — execution (preflight, render, encoder).
- `0` — success (incl. dry-run and cache reuse).

Failures name the artifact, hash, recommendation, media-touched state, and
cleanup. Failed renders keep the workdir diagnostics (existing Phase 13
rule); successful temp files are cleaned.

## CLI

```powershell
python -m engine.cli approve-caption-pacing-execution <pid> --recommendation-id rec_0001 [--recommendation-id ...]
python -m engine.cli approve-caption-pacing-execution <pid> --all-safe
python -m engine.cli execute-caption-pacing <pid> --dry-run
python -m engine.cli execute-caption-pacing <pid> [--force] [--encoder auto] [--output name.mp4] [--json]
```

`--all-safe` selects only SAFE, executable, conflict-free recommendations
(never CAUTION/UNSAFE/REVIEW/planning-only).

## Artifacts

- `editing/approved_caption_pacing_execution.json` (immutable snapshot)
- `edit/caption_pacing_execution_plan.json` (canonical derived plan)
- `renders/pacing_<stamp>.mp4` + `renders/<stem>_pacing_manifest.json`
  (runtime manifest with full provenance + recommendation inventories)

## Limitations

- SPLIT has no media effect (boundary metadata only).
- Visual recommendations are metadata only (future visual phases).
- Caption mode follows the caption approval (no per-execution override).
- Base-approval exclusion applies only when `approved_edit_plan.json` exists.
- `RECOMMENDED`/`INVALID` states are reserved for operator workflows.

## Future extension points

Visual execution of `CHANGE_VISUAL`/`ADD_CUTAWAY_OPPORTUNITY` metadata,
per-execution caption-mode override, `INVALID` lifecycle transitions.
