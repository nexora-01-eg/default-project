# RENDER_EXECUTION.md — Phase 9 EDL → media (`engine/rendering/execution.py`)

The renderer EXECUTES decisions; it never invents them. Zero ffmpeg argv
here — all media work goes through the Phase 4 gateway (`trim`, `concat`,
`select_encoder`, `validate_output`).

## Flow

```
EDL (edit/edit_decision.json)
  -> validate_edl (fail BEFORE ffmpeg; never silently repair)
  -> ExecutionPlan (KEEP segments + source->output offsets)
  -> trim each keep (accurate re-encode, explicitly resolved encoder)
  -> join: direct copy (1 keep) | re-encode concat (N keeps)
  -> validate_render (QC + start-time/sync extras)
  -> renders/<name>.mp4 + renders/<name>_manifest.json
```

## Source vs output timeline

EDL coordinates are source seconds. The plan maps each KEEP to an output
offset (cumulative kept durations). Example: KEEP 0→5, REMOVE 5→8, KEEP
8→12 renders 9 s with source 8→12 at output 5→9. Mapping is stored in the
manifest (`mapping[]`).

## Audio handling

Re-encode to AAC on every join (correctness first); accurate trims keep
audio in sync by construction. Audio-less sources render video-only
(gateway `concat` uses `-an` when parts lack audio — Phase 9 addition).
Audio-only sources are refused clearly (no video stream to encode).

## Encoder selection

`select_encoder()` once per render (verified HW → CPU fallback; this box:
`h264_qsv`). Explicit `--encoder` overrides. Bogus encoders fail at trim
time with the ffmpeg error surfaced (no silent fallback to another plan).

## A/V validation

`validate_output` (duration/resolution/fps/codecs) plus: video start ≈ 0,
audio start ≈ 0, container-vs-audio duration delta ≤ `av_sync_tol`.
Verdict `pass` required or the render raises (`validation_failed` stage,
diagnostics kept).

## Failure behavior

Missing source/EDL, invalid EDL, ffmpeg/encoder failure, QC failure →
`RenderError{stage: input|plan|execute|validate}` → CLI exits 2 (bad input),
5 (plan/execute), 6 (validation). Sources never touched; temp workdir is
kept on failure (path in the error) and removed on success.

## Render manifest

`kind, status, project, source, edl_hash, config, renderer_version,
encoder(+reason), output, source/expected/actual durations, keep/remove
counts, mapping, processing_s, realtime_factor, qc, warnings, cached`.
`edl_hash` covers decisions+policy+source+duration (not wall-clock).

## Caching / reuse

Identity = source + edl_hash + config + renderer version. A completed
manifest whose output exists AND re-probes within tolerance is reused
(`cached: true`, file untouched). Corrupt outputs re-render — never reused.

## CLI

`video-engine render <project>`: EDL mode when `edit/edit_decision.json`
exists (`--edl` forces it, missing → exit 2); `--keep` forces legacy
range mode; otherwise legacy full transcode. `--fast` maps to
`accurate=False` (widened tolerance). `--json` prints the manifest.

## Config (`RenderConfig`)

`container mp4, video_encoder auto, preset veryfast, audio_codec aac,
fps/resolution policies source-only (Phase 9), accurate, duration_tol 0.4,
av_sync_tol 0.5, overwrite, timeout`. Unknown keys / non-source policies
are rejected explicitly — small API by design.
