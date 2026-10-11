# PIPELINE.md — staged dataflow (v0.3: inspect + analyze_audio live)

```
INPUT → INSPECT → ANALYZE → UNDERSTAND → PLAN → EXECUTE → RENDER → QC → FIX? → FINAL
```

| Stage | Artifact | Status |
|---|---|---|
| inspect | `analysis/media_info.json` | ✅ implemented (ffprobe; per-stream audio detail since Phase 3) |
| analyze_audio | `analysis/audio_analysis.json` (volumes, loudness, silence[], non_silent[]) | ✅ Phase 3 |
| transcribe (standalone) | `analysis/transcript.json` (language, segments, words, fillers) | ✅ Phase 5/6 (`transcribe` CLI; `analyze` stays model-free by design) |
| scenes (standalone) | `analysis/scenes.json` (boundaries, frames, method) | ✅ Phase 7 (`scenes` CLI; `analyze` stays lightweight by design) |
| edit-plan | `edit/edit_decision.json` (KEEP/REMOVE on source timeline) | ✅ Phase 8 (`edit` CLI; plan only, no rendering) |
| render (EDL execution) | `renders/*.mp4` + `*_manifest.json` (plan→render→QC) | ✅ Phase 9 (`render` CLI EDL mode; `--keep` legacy preserved) |
| edit-intelligence | `edit/edit_intelligence.json` + `edit/refined_edit_decision.json` | ✅ Phase 10 (`edit-analyze` CLI; analysis only, no rendering) |
| visual intelligence | `visual/visual_analysis.json` + `visual/frames/` | ✅ Phase 11 (`visual` CLI; analysis only, no rendering) |
| editor brain | `editing/editor_plan.json` (style-driven plan, no rendering) | ✅ Phase 12 (`editor-plan` CLI; planning only) |
| plan approval | `editing/approved_edit_plan.json` (immutable snapshot) | ✅ Phase 13 (`approve-plan` CLI) |
| plan execution | `renders/plan_*.mp4` + `plan_*_manifest.json` (approved ops only) | ✅ Phase 13 (`render-plan` CLI; dry-run available) |
| captions | `captions/caption_plan.json` + sidecars; `render-plan --captions` | ✅ Phase 14 (`captions` + `approve-captions` CLIs; sidecar + burned-in) |
| visual captions | `captions/visual_caption_plan.json` + visual approval; render auto-detects | ✅ Phase 15 (`caption-visual` + `approve-caption-visual`; analysis only unless approved+rendered) |
| caption pacing | `editing/caption_pacing_plan.json` + `editing/approved_caption_pacing_plan.json` | ✅ Phase 16 (`caption-pacing` + `approve-caption-pacing`; analysis only, no rendering, no EDL mutation) |
| pacing execution | `editing/approved_caption_pacing_execution.json` + `edit/caption_pacing_execution_plan.json` + `renders/*_pacing_manifest.json` | ✅ Phase 17 (`approve-caption-pacing-execution` + `execute-caption-pacing`; derived EDL via Phase 13 engine, caption/visual remap, QC) |
| analyze (scenes/speech/faces…) | `analysis/*.json` | Phases 5–7 |
| understand/plan | `edit/edit_decision.json`, `edit/render_plan.json` | Phase 8 |
| execute/render | `renders/*.mp4` + `*_validation.json` | ✅ Phase 4 engine (`render` CLI live); presets Phase 12 |
| qc/fix | `qc/QC_REPORT.json`, ≤3 retries | Phase 13 (shares Phase 4 `QCReport` model) |

Cache: `.cache/<sha>.json` + per-project copies. Same file+config never re-analyzed.
`analyze` CLI runs inspect + analyze_audio with independent cache keys and JSONL events.
