"""CLI: video-engine analyze|render|edit|qc|status|doctor (stdlib argparse)."""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from dataclasses import asdict
from pathlib import Path

from engine.core import orchestrator
from engine.core.project_store import load_project, mark_stage, project_dir, write_artifact


def _cmd_analyze(args) -> int:
    overrides: dict = {}
    if args.silence_db is not None:
        overrides["silence_db"] = args.silence_db
    if args.min_silence is not None:
        overrides["min_silence_s"] = args.min_silence
    try:
        result = orchestrator.run_inspect(args.input, template=args.template,
                                          preset=args.preset, overrides=overrides or None)
    except Exception as exc:  # human-readable, never a traceback for expected errors
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0


def _cmd_status(args) -> int:
    try:
        project = load_project(args.project)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(project.to_dict(), indent=2))
    return 0


def _cmd_doctor(_args) -> int:
    from engine.core.media import ffprobe_path
    from engine.rendering.ffmpeg import ffmpeg_config_state, which_ffmpeg
    report = {
        "python": sys.version.split()[0],
        "ffmpeg": which_ffmpeg() or "NOT FOUND",
        "ffmpeg_source": ffmpeg_config_state()["source"],
        "ffprobe": ffprobe_path() or "NOT FOUND",
        "git": shutil.which("git") or "NOT FOUND",
        "node": shutil.which("node") or "NOT FOUND",
    }
    print(json.dumps(report, indent=2))
    ok = report["ffmpeg"] != "NOT FOUND" and report["ffprobe"] != "NOT FOUND"
    if not ok:
        print("HINT: install missing tools with `.\\setup.ps1 -Install`", file=sys.stderr)
        return 3
    return 0


def _parse_ranges(spec: str) -> list[tuple[float, float]]:
    spans: list[tuple[float, float]] = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            s_raw, e_raw = part.split("-", 1)
            spans.append((float(s_raw), float(e_raw)))
        except ValueError:
            raise ValueError(f"bad range {part!r}: expected START-END (e.g. 0-5,8-12.5)")
    if not spans:
        raise ValueError("empty --keep spec")
    return spans


def _cmd_render(args) -> int:
    from engine.core.media import MediaProbeError, probe
    from engine.rendering.execution import RenderError, render_edl_for_project
    from engine.rendering.ffmpeg import (
        ENCODER_CODEC, FfmpegError, ValidateExpect, render_keep, select_encoder,
        validate_output,
    )
    try:
        project = load_project(args.project)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    edl_path = project_dir(project.id) / "edit" / "edit_decision.json"
    if args.keep:
        return _cmd_render_ranges(args, project)
    if args.edl and not edl_path.is_file():
        print(f"ERROR: missing EDL edit/edit_decision.json (run edit first)",
              file=sys.stderr)
        return 2
    if edl_path.is_file():
        overrides = {"video_encoder": args.encoder, "accurate": not args.fast}
        try:
            result = render_edl_for_project(project.id, overrides,
                                            out_name=args.out)
        except RenderError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 6 if exc.stage == "validate" else 5
        m = result["manifest"]
        print(f"project : {result['project']}  cached: {result['cached']}")
        print(f"output  : {result['output']}")
        print(f"encoder : {m.get('encoder')}  ({m.get('encoder_reason')})")
        print(f"expected: {m.get('expected_duration')}s  actual: "
              f"{m.get('actual_duration')}s  keeps: {m.get('keep_segments')}")
        print(f"qc      : {m.get('qc', {}).get('verdict')}  "
              f"rtf: {m.get('realtime_factor')}x")
        print(f"manifest: renders/{Path(result['output']).stem}_manifest.json")
        if args.json:
            print(json.dumps(m, indent=2, ensure_ascii=False))
        return 0
    # No EDL: legacy full-duration transcode (Phase 4 behavior preserved).
    args.keep = None
    return _cmd_render_ranges(args, project)


def _cmd_approve_plan(args) -> int:
    from engine.editing.approval import ApprovalError, approve_plan
    try:
        result = approve_plan(
            args.project,
            include=args.include, exclude=args.exclude,
            broll_map=args.broll_map, broll_audio=args.broll_audio,
            broll_fit=args.broll_fit)
    except (ApprovalError, FileNotFoundError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    a = result["approval"]
    print(f"project : {result['project']}")
    print(f"cuts    : {len(a.get('approved_cuts', []))} approved  "
          f"broll: {len(a.get('broll_assignments', []))} assigned  "
          f"jump: {len(a.get('jump_approvals', []))} reviewed")
    if a.get("warnings"):
        print(f"warnings: {len(a['warnings'])} (see editing/approved_edit_plan.json)")
        for w in a["warnings"][:5]:
            print(f"  - {w}")
    print("artifact: editing/approved_edit_plan.json (immutable snapshot - render needs no re-approval unless inputs change)")
    if args.json:
        print(json.dumps(a, indent=2, ensure_ascii=False))
    return 0


def _cmd_render_plan(args) -> int:
    from engine.editing.approval import ApprovalError
    from engine.rendering.plan_execute import dry_run_plan, render_plan_for_project
    from engine.rendering.execution import RenderError
    from engine.subtitles.captions import CaptionError
    if args.dry_run:
        try:
            plan = dry_run_plan(args.project, captions=args.captions)
        except (RenderError, ApprovalError, CaptionError, FileNotFoundError) as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2
        print(f"project : {plan['project']}  (DRY RUN - nothing rendered)")
        print(f"expected: {plan['expected_duration']}s  "
              f"ops: {len(plan['operations'])}  encoder: {plan['encoder']}")
        for op in plan["operations"]:
            extra = f" asset={op['asset_id']}" if op.get("asset_id") else ""
            print(f"  {op['operation_id']} {op['action']:14s} "
                  f"src {op['source_start']}->{op['source_end']}  "
                  f"out {op['output_start']}->{op['output_end']}{extra}")
        print(f"assets  : {list(plan['assets'])}")
        print(f"qc plan : {', '.join(plan['qc_plan'])}")
        if plan.get("captions"):
            cap = plan["captions"]
            print(f"captions: {cap.get('cue_count')} cues, "
                  f"{cap.get('mode')}/{cap.get('style')}, "
                  f"qc verdict would gate render")
            vis = cap.get("visual", {}) or {}
            if vis:
                print(f"visual  : {vis.get('state')} "
                      f"(placements {vis.get('placements', '?')}, "
                      f"emphasis {vis.get('emphasis_cues', '?')})")
        if plan.get("warnings"):
            print(f"warnings: {len(plan['warnings'])}")
        if args.json:
            print(json.dumps(plan, indent=2, ensure_ascii=False))
        return 0
    overrides = {}
    if args.encoder != "auto":
        overrides["video_encoder"] = args.encoder
    try:
        result = render_plan_for_project(args.project,
                                         overrides or None,
                                         out_name=args.output,
                                         force=args.force,
                                         captions=args.captions)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except RenderError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2 if exc.stage == "input" else (6 if exc.stage == "validate" else 5)
    except CaptionError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    m = result["manifest"]
    print(f"project : {result['project']}  cached: {result['cached']}")
    print(f"output  : {result['output']}")
    print(f"encoder : {m.get('encoder')}  ({m.get('encoder_reason')})")
    print(f"expected: {m.get('expected_duration')}s  actual: {m.get('actual_duration')}s")
    print(f"qc      : {m.get('qc', {}).get('verdict')}  "
          f"rtf: {m.get('realtime_factor')}x")
    if m.get("caption_mode"):
        print(f"captions: {m.get('caption_count')} cues, {m.get('caption_mode')}/"
              f"{m.get('caption_style')}, qc {m.get('caption_qc', {}).get('verdict')}")
    print(f"manifest: renders/{Path(result['output']).stem}_plan_manifest.json")
    if args.json:
        print(json.dumps(m, indent=2, ensure_ascii=False))
    return 0


def _cmd_captions(args) -> int:
    from engine.subtitles.captions import CaptionError, caption_plan_for_project
    from engine.subtitles.formats import FormatError, write_ass, write_srt, write_vtt
    overrides = {}
    if args.style:
        overrides["caption_style"] = args.style
    try:
        result = caption_plan_for_project(args.project,
                                          overrides or None,
                                          force=args.force)
    except (CaptionError, FormatError, FileNotFoundError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    plan = result["plan"]
    max_cps = max([c.get("reading_cps", 0) for c in plan.get("cues", [])] or [0])
    print(f"project : {result['project']}  cached: {result['cached']}")
    print(f"cues    : {plan.get('cue_count')}  lang: {plan.get('language')}  "
          f"style: {plan.get('style')}")
    print(f"max cps : {max_cps}  warnings: {len(plan.get('warnings', []))}")
    if args.format in ("srt", "all"):
        out = project_dir(result["project"]) / "captions" / "captions.srt"
        out.write_text(write_srt(plan.get("cues", [])), encoding="utf-8")
        print(f"srt     : captions/captions.srt")
    if args.format in ("vtt", "all"):
        out = project_dir(result["project"]) / "captions" / "captions.vtt"
        out.write_text(write_vtt(plan.get("cues", []), plan.get("language", "")),
                       encoding="utf-8")
        print(f"vtt     : captions/captions.vtt")
    print("artifact: captions/caption_plan.json (plan only - video untouched)")
    if args.json:
        print(json.dumps(plan, indent=2, ensure_ascii=False))
    return 0


def _cmd_approve_captions(args) -> int:
    from engine.subtitles.captions import CaptionError, approve_captions
    try:
        result = approve_captions(args.project, mode=args.mode, style=args.style,
                                  font_family=args.font_family,
                                  font_file=args.font_file)
    except (CaptionError, FileNotFoundError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    a = result["approval"]
    print(f"project : {result['project']}")
    print(f"mode    : {a.get('mode')}  style: {a.get('style')}  "
          f"font: {(a.get('font', {}) or {}).get('family')}")
    if a.get("warnings"):
        print(f"warnings: {len(a['warnings'])} (see editing/approved_captions.json)")
    print("artifact: editing/approved_captions.json (base approval untouched)")
    if args.json:
        print(json.dumps(a, indent=2, ensure_ascii=False))
    return 0


def _cmd_caption_visual(args) -> int:
    from engine.subtitles.visual_captions import (
        VisualCaptionError,
        caption_visual_for_project,
    )
    try:
        result = caption_visual_for_project(args.project, style_name=args.style,
                                            force=args.force,
                                            dry_run=args.dry_run)
    except (VisualCaptionError, FileNotFoundError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    plan = result["plan"]
    emph = sum(1 for e in plan.get("emphasis", [])
               if e.get("emphasis_type", "none") != "none")
    print(f"project : {result['project']}  cached: {result['cached']}"
          f"{'  (DRY RUN - nothing written)' if result.get('dry_run') else ''}")
    print(f"cues    : {len(plan.get('placements', []))} placed  "
          f"emphasis: {emph}  conflicts: {len(plan.get('conflicts', []))}")
    if plan.get("warnings"):
        print(f"warnings: {len(plan['warnings'])} (see visual caption plan)")
    if not result.get("dry_run"):
        print("artifact: captions/visual_caption_plan.json (plan only - nothing rendered)")
    if args.json:
        print(json.dumps(plan, indent=2, ensure_ascii=False))
    return 0


def _cmd_approve_caption_visual(args) -> int:
    from engine.subtitles.visual_captions import (
        VisualCaptionError,
        approve_caption_visual,
    )
    try:
        result = approve_caption_visual(args.project)
    except (VisualCaptionError, FileNotFoundError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    a = result["approval"]
    print(f"project : {result['project']}")
    print(f"visual plan hash: {a.get('visual_plan_hash', '')[:12]}...  "
          f"style: {a.get('style')}")
    print("artifact: captions/approved_visual_caption_plan.json")
    if args.json:
        print(json.dumps(a, indent=2, ensure_ascii=False))
    return 0
    m = result["manifest"]
    print(f"project : {result['project']}  cached: {result['cached']}")
    print(f"output  : {result['output']}")
    print(f"encoder : {m.get('encoder')}  ({m.get('encoder_reason')})")
    print(f"expected: {m.get('expected_duration')}s  actual: {m.get('actual_duration')}s")
    print(f"qc      : {m.get('qc', {}).get('verdict')}  "
          f"rtf: {m.get('realtime_factor')}x")
    print(f"manifest: renders/{Path(result['output']).stem}_plan_manifest.json")
    if args.json:
        print(json.dumps(m, indent=2, ensure_ascii=False))
    return 0


def _cmd_render_ranges(args, project) -> int:
    from engine.core.media import MediaProbeError, probe
    from engine.rendering.ffmpeg import (
        ENCODER_CODEC, FfmpegError, ValidateExpect, render_keep, select_encoder,
        validate_output,
    )
    try:
        info = probe(project.input_path)
    except MediaProbeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    try:
        keep = _parse_ranges(args.keep) if args.keep else [(0.0, info.duration)]
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    log_file = project_dir(project.id) / "logs" / "run.jsonl"
    try:
        if args.encoder == "auto":
            sel = select_encoder()
            encoder, reason = sel["selected_encoder"], sel["reason"]
        else:
            encoder, reason = args.encoder, f"explicitly requested ({args.encoder})"
        out_name = args.out or f"render_{time.strftime('%Y%m%d_%H%M%S')}.mp4"
        dst = project_dir(project.id) / "renders" / out_name
        accurate = not args.fast
        render_keep(project.input_path, keep, dst, encoder=encoder,
                    accurate=accurate, log_file=log_file)
    except (FfmpegError, ValueError, MediaProbeError) as exc:
        mark_stage(project, "render", "failed", str(exc)[:300])
        print(f"ERROR: {exc}", file=sys.stderr)
        return 5
    expect = ValidateExpect(
        duration=sum(e - s for s, e in keep),
        duration_tol=0.4 if accurate else 1.0,
        width=info.width or None, height=info.height or None,
        fps=info.fps or None,
        video_codec=ENCODER_CODEC.get(encoder),
        audio_codec="aac" if (info.audio_codec and accurate) else None,
        require_audio=bool(info.audio_codec))
    report = validate_output(dst, expect)
    write_artifact(project.id, "renders", Path(dst).stem + "_validation.json",
                   asdict(report))
    mark_stage(project, "render", "done" if report.verdict == "pass" else "validation_failed",
               f"renders/{Path(dst).name}")
    print(json.dumps({"project": project.id, "output": str(dst),
                      "encoder": encoder, "reason": reason,
                      "validation": asdict(report)}, indent=2))
    return 0 if report.verdict == "pass" else 6


def _cmd_notyet(args) -> int:
    try:
        orchestrator.run_edit()
    except NotImplementedError as exc:
        print(f"NOT IMPLEMENTED ({args.command}): {exc}", file=sys.stderr)
        return 4
    return 0


def _cmd_edit(args) -> int:
    from engine.editing.decisions import EditError, build_edl_for_project
    overrides: dict = {}
    if args.min_silence is not None:
        overrides["edit_min_silence_s"] = args.min_silence
    if args.silence_pad_before is not None:
        overrides["edit_silence_pad_before"] = args.silence_pad_before
    if args.silence_pad_after is not None:
        overrides["edit_silence_pad_after"] = args.silence_pad_after
    if args.no_fillers:
        overrides["edit_remove_fillers"] = False
    if args.filler_pad is not None:
        overrides["edit_filler_pad_s"] = args.filler_pad
    try:
        result = build_edl_for_project(args.project, overrides or None)
    except (EditError, FileNotFoundError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    e = result["edl"]
    print(f"project : {result['project']}  cached: {result['cached']}")
    print(f"decisions: {e.get('decision_count')}  kept: {e.get('kept_duration')}s  "
          f"removed: {e.get('removed_duration')}s  ratio: {e.get('removal_ratio')}")
    for d in e.get("decisions", [])[:10]:
        print(f"  {d['decision_id']} {d['action']:6s} {d['start']} -> {d['end']}  "
              f"{d['reason']} (conf {d['confidence']}, scene {d['scene_id']})")
    if e.get("decision_count", 0) > 10:
        print(f"  ... ({e['decision_count'] - 10} more, see edit/edit_decision.json)")
    if e.get("warnings"):
        print(f"warnings: {len(e['warnings'])} (see edit/edit_decision.json)")
    print("artifact: edit/edit_decision.json  (plan only - source untouched, nothing rendered)")
    if args.json:
        print(json.dumps(e, indent=2, ensure_ascii=False))
    return 0


def _cmd_edit_analyze(args) -> int:
    from engine.editing.intelligence import IntelError, run_intelligence_for_project
    overrides: dict = {}
    if args.safety_mode is not None:
        overrides["intel_safety_mode"] = args.safety_mode
    if args.enable_repetition:
        overrides["intel_repetition_removal"] = True
    if args.no_safety_net:
        overrides["intel_safety_net"] = False
    if args.no_jumpcut:
        overrides["intel_enable_jumpcut"] = False
    if args.no_pacing:
        overrides["intel_enable_pacing"] = False
    if args.min_keep is not None:
        overrides["intel_min_keep_s"] = args.min_keep
    try:
        result = run_intelligence_for_project(args.project, overrides or None)
    except (IntelError, FileNotFoundError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    intel, ref = result["intelligence"], result["refined_edl"]
    saf = {}
    for s in intel.get("cut_safety", []):
        saf[s["status"]] = saf.get(s["status"], 0) + 1
    print(f"project : {result['project']}  cached: {result['cached']}")
    print(f"safety  : {saf or 'no removals assessed'}  "
          f"changes: {len(intel.get('refined_changes', []))}")
    print(f"scenes  : {len(intel.get('scene_metrics', []))}  "
          f"repetitions: {len(intel.get('repetitions', []))}  "
          f"jump-cuts: {len(intel.get('jump_cuts', []))}")
    print(f"refined : {ref.get('decision_count')} decisions, "
          f"removed {ref.get('removed_duration')}s")
    if intel.get("warnings"):
        print(f"warnings: {len(intel['warnings'])} (see edit_intelligence.json)")
    print("artifacts: edit/edit_intelligence.json + edit/refined_edit_decision.json "
          "(analysis only - nothing rendered)")
    if args.json:
        print(json.dumps(intel, indent=2, ensure_ascii=False))
    return 0


def _cmd_editor_plan(args) -> int:
    from engine.editing.brain import BrainError, run_editor_brain_for_project
    try:
        target = float(args.target_duration) if args.target_duration is not None else None
        result = run_editor_brain_for_project(
            args.project, style_name=args.style,
            target_duration=target, aggressive=args.aggressive)
    except (BrainError, FileNotFoundError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    plan = result["plan"]
    verdicts = {}
    for c in plan.get("cut_plan", []):
        verdicts[c["verdict"]] = verdicts.get(c["verdict"], 0) + 1
    print(f"project : {result['project']}  cached: {result['cached']}")
    print(f"style   : {plan.get('editing_style', {}).get('name')}  "
          f"hook: {plan.get('hook', {}).get('recommended_opening_strategy')}")
    print(f"cuts    : {verdicts or 'no removals proposed'}  "
          f"broll: {len(plan.get('broll_plan', []))}  "
          f"risks: {len(plan.get('quality_risks', []))}")
    print(f"story   : {[(s['classification'], s['confidence']) for s in plan.get('story_structure', [])][:6]}")
    if plan.get("warnings"):
        print(f"warnings: {len(plan['warnings'])} (see editing/editor_plan.json)")
    print("artifact: editing/editor_plan.json (planning only - nothing rendered)")
    if args.json:
        print(json.dumps(plan, indent=2, ensure_ascii=False))
    return 0


def _cmd_visual(args) -> int:
    from engine.analysis.visual import VisualError, run_visual_for_project
    overrides: dict = {}
    if args.samples_per_scene is not None:
        overrides["visual_mode"] = "per_scene"
        overrides["visual_samples_per_scene"] = args.samples_per_scene
    if args.fps is not None:
        overrides["visual_mode"] = "fps"
        overrides["visual_fps"] = args.fps
    if args.mode is not None:
        overrides["visual_mode"] = args.mode
    try:
        result = run_visual_for_project(args.project, overrides or None,
                                        force=args.force)
    except (VisualError, FileNotFoundError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    r = result["result"]
    caps = r.get("capabilities", {})
    print(f"project : {result['project']}  cached: {result['cached']}")
    print("capabilities:")
    for name, cap in caps.items():
        print(f"  {name:17s} {cap.get('status')} ({cap.get('backend')})")
    print(f"scenes  : {r.get('scenes_analyzed')}  "
          f"frames: {len(r.get('frame_samples', []))}  "
          f"time: {r.get('processing_s')}s")
    if r.get("warnings"):
        print(f"warnings: {len(r['warnings'])} (see visual/visual_analysis.json)")
    if r.get("errors"):
        print(f"errors  : {len(r['errors'])} (see visual/visual_analysis.json)")
    print("artifact: visual/visual_analysis.json (analysis only - nothing rendered)")
    if args.json:
        print(json.dumps(r, indent=2, ensure_ascii=False))
    return 0


def _cmd_caption_pacing(args) -> int:
    from engine.editing.caption_pacing import (
        PacingError,
        run_caption_pacing_for_project,
    )
    try:
        result = run_caption_pacing_for_project(
            args.project, style_name=args.style, force=args.force,
            dry_run=args.dry_run)
    except (PacingError, FileNotFoundError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    plan = result["plan"]
    by_action: dict[str, int] = {}
    for r in plan.get("recommendations", []):
        by_action[r["action"]] = by_action.get(r["action"], 0) + 1
    print(f"project : {result['project']}  cached: {result['cached']}"
          f"{'  (DRY RUN - nothing written)' if result.get('dry_run') else ''}")
    print(f"signals : {len(plan.get('signals', []))}  "
          f"recommendations: {len(plan.get('recommendations', []))} {by_action}")
    print(f"safety  : {plan.get('safety_summary', {}).get('counts', {})}")
    if plan.get("warnings"):
        print(f"warnings: {len(plan['warnings'])} (see caption pacing plan)")
    if not result.get("dry_run"):
        print("artifact: editing/caption_pacing_plan.json (plan only - nothing rendered)")
    if args.json:
        print(json.dumps(plan, indent=2, ensure_ascii=False))
    return 0


def _cmd_approve_caption_pacing(args) -> int:
    from engine.editing.caption_pacing import (
        PacingError,
        approve_caption_pacing,
    )
    try:
        result = approve_caption_pacing(args.project)
    except (PacingError, FileNotFoundError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    a = result["approval"]
    print(f"project : {result['project']}")
    print(f"pacing plan hash: {a.get('pacing_plan_hash', '')[:12]}...  "
          f"style: {a.get('style')}")
    print("artifact: editing/approved_caption_pacing_plan.json")
    if args.json:
        print(json.dumps(a, indent=2, ensure_ascii=False))
    return 0


def _cmd_approve_pacing_execution(args) -> int:
    from engine.editing.caption_pacing_execution import (
        PacingExecutionError,
        approve_caption_pacing_execution,
    )
    try:
        result = approve_caption_pacing_execution(
            args.project, recommendation_ids=args.recommendation_id,
            all_safe=args.all_safe)
    except (PacingExecutionError, FileNotFoundError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    a = result["approval"]
    pol = a.get("generated_execution_policy", {})
    print(f"project : {result['project']}")
    print(f"approved: {a.get('approved_recommendation_ids', [])}  "
          f"rejected: {a.get('rejected_recommendation_ids', [])}")
    print(f"policy  : {pol.get('selection')}  caption mode: {pol.get('caption_mode')}  "
          f"trims: {pol.get('trim_count')}  splits: {pol.get('split_count')}")
    print("artifact: editing/approved_caption_pacing_execution.json "
          "(intelligence approval is separate)")
    if args.json:
        print(json.dumps(a, indent=2, ensure_ascii=False))
    return 0


def _cmd_execute_pacing(args) -> int:
    from engine.editing.caption_pacing_execution import (
        PacingExecutionError,
        dry_run_pacing_execution,
        execute_caption_pacing_for_project,
    )
    from engine.rendering.execution import RenderError
    if args.dry_run:
        try:
            result = dry_run_pacing_execution(args.project)
        except (PacingExecutionError, FileNotFoundError) as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2
        print(f"project : {result['project']}  (DRY RUN - nothing written)")
        print(f"approved: {result['approved_recommendation_ids']}  "
              f"rejected: {result['rejected_recommendation_ids']}")
        for op in result["executable_ops"]:
            print(f"  {op['op_id']} {op['mode']:6s} src={op['source']} "
                  f"out={op['output']} safety={op['safety']}")
        print(f"caption impact: {result['caption_impact']}  "
              f"predicted duration: {result['predicted_duration']}s  "
              f"mode: {result['caption_mode']}")
        if result.get("warnings"):
            print(f"warnings: {len(result['warnings'])} (see execution preview)")
        if args.json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    overrides = {}
    if args.encoder != "auto":
        overrides["video_encoder"] = args.encoder
    try:
        result = execute_caption_pacing_for_project(
            args.project, overrides or None, args.output, args.force)
    except (PacingExecutionError, FileNotFoundError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except RenderError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 6 if exc.stage == "validate" else \
            2 if exc.stage == "input" else 5
    m = result["manifest"]
    print(f"project : {result['project']}  cached: {result['cached']}")
    print(f"output  : {result['output']}")
    print(f"encoder : {m.get('encoder')}  ({m.get('encoder_reason')})")
    print(f"executed: {m.get('recommendations_executed')}  "
          f"rejected: {m.get('recommendations_rejected')}  "
          f"planning-only: {m.get('recommendations_planning_only')}")
    print(f"qc      : {m.get('qc', {}).get('verdict')}  "
          f"manifest: renders/{Path(result['output']).stem}_pacing_manifest.json")
    if args.json:
        print(json.dumps(m, indent=2, ensure_ascii=False))
    return 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="video-engine", description="Local AI video editing engine (v0.1)")
    sub = ap.add_subparsers(dest="command", required=True)

    p = sub.add_parser("analyze", help="inspect media and create a project")
    p.add_argument("input", help="input video file")
    p.add_argument("--template", default="youtube")
    p.add_argument("--preset", default="youtube_1080p")
    p.add_argument("--silence-db", type=float, default=None,
                   help="silence threshold in dB (default from config, -35)")
    p.add_argument("--min-silence", type=float, default=None,
                   help="minimum silence duration in seconds (default 0.5)")
    p.set_defaults(func=_cmd_analyze)

    for name in ("qc",):
        p = sub.add_parser(name, help=f"{name} (lands in a later phase)")
        p.add_argument("input", nargs="?")
        p.set_defaults(func=_cmd_notyet)

    p = sub.add_parser("edit", help="build edit decision list from project analysis (plan only)")
    p.add_argument("project", help="project id with analysis artifacts")
    p.add_argument("--min-silence", type=float, default=None,
                   help="silence removal threshold in seconds (default 0.8)")
    p.add_argument("--silence-pad-before", type=float, default=None)
    p.add_argument("--silence-pad-after", type=float, default=None)
    p.add_argument("--no-fillers", action="store_true",
                   help="keep filler words (no RULE B removals)")
    p.add_argument("--filler-pad", type=float, default=None,
                   help="padding around filler removals in seconds (default 0.08)")
    p.add_argument("--json", action="store_true", help="print full EDL JSON")
    p.set_defaults(func=_cmd_edit)

    p = sub.add_parser("edit-analyze",
                       help="editing intelligence over a base EDL (analysis only)")
    p.add_argument("project", help="project id with edit/edit_decision.json")
    p.add_argument("--safety-mode", default=None,
                   help="conservative (UNSAFE reverts) | strict (+CAUTION reverts)")
    p.add_argument("--enable-repetition", action="store_true",
                   help="opt-in: remove 2nd+ exact repetitions")
    p.add_argument("--no-safety-net", action="store_true",
                   help="disable UNSAFE revert (measure only)")
    p.add_argument("--no-jumpcut", action="store_true", help="skip jump-cut analysis")
    p.add_argument("--no-pacing", action="store_true", help="skip pacing metrics")
    p.add_argument("--min-keep", type=float, default=None,
                   help="minimum keep duration for safety flags")
    p.add_argument("--json", action="store_true", help="print full report JSON")
    p.set_defaults(func=_cmd_edit_analyze)

    p = sub.add_parser("render", help="render project: EDL if present, else keep-ranges")
    p.add_argument("project", help="project id from analyze")
    p.add_argument("--keep", default=None,
                   help='keep ranges START-END,... e.g. "0-5,8-12.5" (overrides EDL mode)')
    p.add_argument("--edl", action="store_true",
                   help="force EDL mode (fail if edit/edit_decision.json is missing)")
    p.add_argument("--encoder", default="auto",
                   help="auto (probe machine) or explicit ffmpeg encoder name")
    p.add_argument("--fast", action="store_true",
                   help="stream-copy trims (fast, keyframe-approximate) instead of accurate re-encode")
    p.add_argument("--out", default=None, help="output filename inside renders/")
    p.add_argument("--json", action="store_true", help="print full manifest JSON (EDL mode)")
    p.set_defaults(func=_cmd_render)

    p = sub.add_parser("visual", help="visual intelligence over project scenes (analysis only)")
    p.add_argument("project", help="project id with analysis/media_info.json + scenes.json")
    p.add_argument("--force", action="store_true", help="bypass cache and re-analyze")
    p.add_argument("--samples-per-scene", type=int, default=None,
                   help="N evenly spaced samples per scene (sets per_scene mode)")
    p.add_argument("--fps", type=float, default=None,
                   help="sampling rate in frames/sec (sets fps mode)")
    p.add_argument("--mode", default=None,
                   help="middle|bme|per_scene|fps (default from config: bme)")
    p.add_argument("--json", action="store_true", help="print full report JSON")
    p.set_defaults(func=_cmd_visual)

    p = sub.add_parser("editor-plan",
                       help="professional editing plan over project analysis (planning only)")
    p.add_argument("project", help="project id with analysis + base EDL")
    p.add_argument("--style", default="general",
                   help="talking_head|podcast|interview|educational|tutorial|commentary|social_short|documentary|cinematic|corporate|general")
    p.add_argument("--target-duration", type=float, default=None,
                   help="desired final duration in seconds (advisory only)")
    p.add_argument("--aggressive", action="store_true",
                   help="brisker preset shift (never overrides safety vetoes)")
    p.add_argument("--json", action="store_true", help="print full plan JSON")
    p.set_defaults(func=_cmd_editor_plan)

    p = sub.add_parser("approve-plan",
                       help="explicitly approve an editor plan (immutable snapshot)")
    p.add_argument("project", help="project id with editing/editor_plan.json")
    p.add_argument("--include", action="append", default=None,
                   help="approve only these cut decision_ids (repeatable)")
    p.add_argument("--exclude", action="append", default=None,
                   help="leave these cut decision_ids unapproved (repeatable)")
    p.add_argument("--broll-map", action="append", default=None,
                   help='assign asset: "START-END=PATH[@OFFSET]" (repeatable)')
    p.add_argument("--broll-audio", default="mute",
                   help="mute|original (mix/duck unsupported in Phase 13)")
    p.add_argument("--broll-fit", default="cover",
                   help="cover|contain|crop|letterbox (default: cover)")
    p.add_argument("--json", action="store_true", help="print full approval JSON")
    p.set_defaults(func=_cmd_approve_plan)

    p = sub.add_parser("render-plan",
                       help="render an approved plan (dry-run available)")
    p.add_argument("project", help="project id with approved plan")
    p.add_argument("--dry-run", action="store_true",
                   help="validate + show plan without rendering anything")
    p.add_argument("--force", action="store_true", help="bypass render reuse")
    p.add_argument("--output", default=None, help="output filename inside renders/")
    p.add_argument("--encoder", default="auto",
                   help="auto (verified HW) or explicit ffmpeg encoder name")
    p.add_argument("--captions", action="store_true",
                   help="apply approved captions after base render (requires caption approval)")
    p.add_argument("--json", action="store_true", help="print full manifest JSON")
    p.set_defaults(func=_cmd_render_plan)

    p = sub.add_parser("captions", help="build caption plan from transcript (plan only)")
    p.add_argument("project", help="project id with analysis/transcript.json")
    p.add_argument("--style", default=None,
                   help="default|clean|social|cinematic|minimal (default from config)")
    p.add_argument("--format", default="all",
                   help="sidecar formats to emit: all|srt|vtt (default: all)")
    p.add_argument("--force", action="store_true", help="bypass plan cache")
    p.add_argument("--json", action="store_true", help="print full plan JSON")
    p.set_defaults(func=_cmd_captions)

    p = sub.add_parser("approve-captions",
                       help="explicitly approve a caption plan for rendering")
    p.add_argument("project", help="project id with captions/caption_plan.json")
    p.add_argument("--mode", default="sidecar",
                   help="sidecar|burned_in (default: sidecar)")
    p.add_argument("--style", default=None, help="style preset (default: plan style)")
    p.add_argument("--font-family", default=None, help="font family override")
    p.add_argument("--font-file", default=None, help="explicit font file override")
    p.add_argument("--json", action="store_true", help="print full approval JSON")
    p.set_defaults(func=_cmd_approve_captions)

    p = sub.add_parser("caption-visual",
                       help="visual polish plan for captions (analysis only)")
    p.add_argument("project", help="project id with captions/caption_plan.json")
    p.add_argument("--style", default=None,
                   help="style preset (default: caption plan style)")
    p.add_argument("--force", action="store_true", help="bypass plan cache")
    p.add_argument("--dry-run", action="store_true",
                   help="show plan without writing artifacts")
    p.add_argument("--json", action="store_true", help="print full plan JSON")
    p.set_defaults(func=_cmd_caption_visual)

    p = sub.add_parser("approve-caption-visual",
                       help="explicitly approve a visual caption plan")
    p.add_argument("project", help="project id with visual caption plan")
    p.add_argument("--json", action="store_true", help="print full approval JSON")
    p.set_defaults(func=_cmd_approve_caption_visual)

    p = sub.add_parser("caption-pacing",
                       help="caption-aware scene pacing plan (analysis only)")
    p.add_argument("project", help="project id with captions/caption_plan.json")
    p.add_argument("--style", default="general",
                   help="editorial style (default: general)")
    p.add_argument("--force", action="store_true", help="bypass plan cache")
    p.add_argument("--dry-run", action="store_true",
                   help="show plan without writing artifacts")
    p.add_argument("--json", action="store_true", help="print full plan JSON")
    p.set_defaults(func=_cmd_caption_pacing)

    p = sub.add_parser("approve-caption-pacing",
                       help="explicitly approve a caption pacing plan")
    p.add_argument("project", help="project id with pacing plan")
    p.add_argument("--json", action="store_true", help="print full approval JSON")
    p.set_defaults(func=_cmd_approve_caption_pacing)

    p = sub.add_parser("approve-caption-pacing-execution",
                       help="approve specific pacing recommendations for execution "
                            "(separate from intelligence approval)")
    p.add_argument("project", help="project id with pacing approval")
    p.add_argument("--recommendation-id", action="append", default=None,
                   help="approve this recommendation id (repeatable)")
    p.add_argument("--all-safe", action="store_true",
                   help="approve all SAFE executable recommendations without conflicts")
    p.add_argument("--json", action="store_true", help="print full approval JSON")
    p.set_defaults(func=_cmd_approve_pacing_execution)

    p = sub.add_parser("execute-caption-pacing",
                       help="execute approved pacing recommendations (render)")
    p.add_argument("project", help="project id with execution approval")
    p.add_argument("--dry-run", action="store_true",
                   help="show execution preview without writing media")
    p.add_argument("--force", action="store_true", help="bypass render reuse")
    p.add_argument("--encoder", default="auto",
                   help="auto (verified HW) or explicit ffmpeg encoder name")
    p.add_argument("--output", default=None,
                   help="output filename inside renders/")
    p.add_argument("--json", action="store_true", help="print full manifest JSON")
    p.set_defaults(func=_cmd_execute_pacing)

    p = sub.add_parser("status", help="show project.json")
    p.add_argument("project", help="project id, e.g. project_20260916_003300")
    p.set_defaults(func=_cmd_status)

    p = sub.add_parser("transcribe", help="local Whisper STT into a project (no auto-download)")
    p.add_argument("input", help="input media file")
    p.add_argument("--model", default="small",
                   help="tiny|base|small|medium|large-v3 (must be cached or --allow-download)")
    p.add_argument("--language", default=None,
                   help="force ISO-639-1 language (default: auto-detect)")
    p.add_argument("--device", default="auto", help="auto|cpu|cuda")
    p.add_argument("--compute-type", default="auto",
                   help="auto|int8|int8_float32|float16|float32 (+cuda: int8_float16)")
    p.add_argument("--word-timestamps", dest="word_timestamps", action="store_true",
                   default=True, help="emit word timings (default on)")
    p.add_argument("--no-word-timestamps", dest="word_timestamps", action="store_false",
                   help="segment text only")
    p.add_argument("--spans", default="full",
                   help="full (whole timeline) or non_silent (Phase 3 spans, shifted back)")
    p.add_argument("--allow-download", action="store_true",
                   help="permit one-time Hugging Face model download")
    p.add_argument("--project", default=None,
                   help="attach transcript to an existing project id")
    p.add_argument("--template", default="youtube")
    p.add_argument("--preset", default="youtube_1080p")
    p.add_argument("--json", action="store_true", help="print full transcript JSON")
    p.set_defaults(func=_cmd_transcribe)

    p = sub.add_parser("download-model", help="explicitly fetch a Whisper model")
    p.add_argument("model", help="tiny|base|small|medium|large-v3")
    p.set_defaults(func=_cmd_download_model)

    p = sub.add_parser("scenes", help="detect scene/shot boundaries (PySceneDetect, ffmpeg fallback)")
    p.add_argument("input", help="input video file")
    p.add_argument("--method", default="content",
                   help="content|threshold|ffmpeg (default: content)")
    p.add_argument("--threshold", type=float, default=None,
                   help="detector threshold (default: 27.0 content, 12.0 threshold, 0.4 ffmpeg)")
    p.add_argument("--min-scene-length", type=float, default=0.6,
                   help="minimum scene length in seconds (default: 0.6)")
    p.add_argument("--project", default=None,
                   help="attach result to an existing project id")
    p.add_argument("--template", default="youtube")
    p.add_argument("--preset", default="youtube_1080p")
    p.add_argument("--json", action="store_true", help="print full result JSON")
    p.set_defaults(func=_cmd_scenes)

    p = sub.add_parser("doctor", help="verify installed dependencies")
    p.set_defaults(func=_cmd_doctor)
    return ap


def _cmd_transcribe(args) -> int:
    from engine.analysis.speech import SpeechError, transcribe_to_project
    try:
        result = transcribe_to_project(
            args.input, project_id=args.project, template=args.template,
            preset=args.preset, model=args.model, language=args.language,
            device=args.device, compute_type=args.compute_type,
            word_timestamps=args.word_timestamps, spans=args.spans,
            allow_download=args.allow_download)
    except SpeechError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    t = result["transcript"]
    eng, perf = t.get("engine", {}), t.get("performance", {})
    print(f"project : {result['project']}  cached: {result['cached']}")
    print(f"model   : {eng.get('model')}  device: {eng.get('device')}/"
          f"{eng.get('compute_type')}{('  [' + eng['fallback'] + ']') if eng.get('fallback') else ''}")
    print(f"language: {t.get('language')} (p={t.get('language_probability')}, "
          f"{t.get('language_mode')})")
    print(f"segments: {t.get('segment_count')}  words: {t.get('word_count')}  "
          f"fillers: {len(t.get('fillers', []))}")
    print(f"media   : {perf.get('media_duration_s')}s in "
          f"{perf.get('processing_s')}s  ({perf.get('realtime_factor')}x realtime)")
    if t.get("skipped_reason"):
        print(f"skipped : {t['skipped_reason']} (no model inference ran)")
    if t.get("timestamp_issues"):
        print(f"ts-issues: {len(t['timestamp_issues'])} (see transcript.json)")
    print("artifact: analysis/transcript.json")
    if args.json:
        print(json.dumps(t, indent=2, ensure_ascii=False))
    return 0


def _cmd_scenes(args) -> int:
    from engine.analysis.scenes import SceneError, detect_scenes_project
    try:
        result = detect_scenes_project(
            args.input, project_id=args.project, template=args.template,
            preset=args.preset, method=args.method, threshold=args.threshold,
            min_scene_len_s=args.min_scene_length)
    except SceneError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    r = result["result"]
    print(f"project : {result['project']}  cached: {result['cached']}")
    print(f"method  : {r.get('requested_method')} -> {r.get('method')}  "
          f"threshold: {r.get('threshold')}  min_len: {r.get('min_scene_len_s')}s")
    print(f"detector: {r.get('detector')} {r.get('detector_version')}"
          f"{('  [fallback from ' + r['fallback_from'] + ']') if r.get('fallback_from') else ''}")
    print(f"scenes  : {r.get('scene_count')}  "
          f"media: {r.get('duration')}s in {r.get('processing_s')}s  "
          f"({r.get('realtime_factor')}x realtime)")
    if r.get("note"):
        print(f"note    : {r['note']}")
    if r.get("timeline_issues"):
        print(f"ts-issues: {len(r['timeline_issues'])} (see scenes.json)")
    print("artifact: analysis/scenes.json")
    if args.json:
        print(json.dumps(r, indent=2, ensure_ascii=False))
    return 0


def _cmd_download_model(args) -> int:
    from engine.analysis.speech import SpeechError, download_model_explicit
    try:
        info = download_model_explicit(args.model)
    except SpeechError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(f"model   : {info['model']}  (~{info['size_mb']} MB, {info['repo']})")
    print(f"path    : {info['path']}")
    print(f"verified: {info['verified']} (model.bin present)")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
