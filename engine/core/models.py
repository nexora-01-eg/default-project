"""Typed internal representation of a project (Phase 3: still stdlib dataclasses).

Decision (see docs/DECISIONS.md 2026-09-17): stay on dataclasses instead of
migrating to pydantic — zero-migration risk, asdict() JSON is clean, and no
validation gap has been observed. Revisit only if a real schema bug appears.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Word:
    w: str
    start: float
    end: float
    conf: float = 0.0


@dataclass
class TranscriptSegment:
    text: str
    start: float
    end: float
    words: list[Word] = field(default_factory=list)


@dataclass
class TranscriptWord:
    """Phase 5/6 Whisper word timing. (Generic Word/TranscriptSegment above are
    future-phase placeholders; unified in Phase 8/10. See docs/DECISIONS.md.)"""
    word: str
    start: float
    end: float
    probability: float = 0.0


@dataclass
class WhisperSegment:
    id: int
    text: str
    start: float
    end: float
    duration: float = 0.0
    words: list[TranscriptWord] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.duration:
            self.duration = round(self.end - self.start, 3)


@dataclass
class Transcript:
    """Phase 5/6 structured transcription (JSON-serializable via asdict)."""
    path: str = ""
    language: str = ""
    language_probability: float = 0.0
    language_mode: str = "auto"  # auto | forced
    duration: float = 0.0  # source audio timeline seconds
    segments: list[WhisperSegment] = field(default_factory=list)
    segment_count: int = 0
    word_count: int = 0
    fillers: list[dict] = field(default_factory=list)  # [{word,start,end,segment_id}]
    non_silent_spans: list[dict] = field(default_factory=list)  # Phase 3 spans reused
    non_silent_coverage: float = 0.0
    timestamp_issues: list[str] = field(default_factory=list)
    skipped_reason: str = ""  # no_audio | fully_silent | "" when transcribed
    engine: dict = field(default_factory=dict)  # {model,device,compute_type,...}
    performance: dict = field(default_factory=dict)  # {media_duration_s,processing_s,realtime_factor}
    config_used: dict = field(default_factory=dict)


@dataclass
class Segment:
    start: float
    end: float
    label: str = ""
    score: float = 0.0


@dataclass
class Scene:
    """Phase 7 scene boundary. Timestamps are full-precision seconds on the
    source timeline (never rounded); frames are the detector's frame numbers."""
    scene_id: int
    start: float
    end: float
    duration: float = 0.0
    start_frame: int = 0
    end_frame: int = 0

    def __post_init__(self) -> None:
        if not self.duration:
            self.duration = self.end - self.start


@dataclass
class SceneDetectionResult:
    """Phase 7 result (JSON-serializable via asdict)."""
    source: str = ""
    duration: float = 0.0
    fps: float = 0.0
    frame_count: int = 0
    method: str = "content"          # content | threshold | ffmpeg (as executed)
    requested_method: str = "content"
    threshold: float = 27.0          # resolved (method defaults when None given)
    min_scene_len_s: float = 0.6
    detector: str = "pyscenedetect"
    detector_version: str = ""
    fallback_from: str = ""          # primary method that failed, if auto-fallback ran
    note: str = ""                   # e.g. "no cuts detected"
    scenes: list[Scene] = field(default_factory=list)
    scene_count: int = 0
    timeline_issues: list[str] = field(default_factory=list)
    processing_s: float = 0.0
    realtime_factor: float = 0.0
    cached: bool = False
    config: dict = field(default_factory=dict)


@dataclass
class SilenceInterval:
    """Structured silence (or non-silent) span. Required schema: start/end/duration."""
    start: float
    end: float
    duration: float = 0.0

    def __post_init__(self) -> None:
        if not self.duration:
            self.duration = round(self.end - self.start, 3)


@dataclass
class AudioAnalysis:
    """Result of the Phase 3 audio analysis stage (JSON-serializable via asdict)."""
    path: str = ""
    audio_present: bool = False
    audio_duration: float = 0.0
    num_audio_streams: int = 0
    channels: int = 0
    sample_rate: int = 0
    codec: str = ""
    bitrate: int = 0
    mean_volume_db: float | None = None
    max_volume_db: float | None = None
    loudness: dict = field(default_factory=dict)  # loudnorm JSON: input_i/tp/lra/thresh…
    silence: list[SilenceInterval] = field(default_factory=list)
    non_silent: list[SilenceInterval] = field(default_factory=list)
    silence_total_s: float = 0.0
    config_used: dict = field(default_factory=dict)


@dataclass
class MediaInfo:
    path: str
    duration: float = 0.0
    width: int = 0
    height: int = 0
    fps: float = 0.0
    video_codec: str = ""
    video_start_time: float = 0.0   # Phase 9: A/V sync validation
    video_duration: float = 0.0
    audio_codec: str = ""
    audio_channels: int = 0
    sample_rate: int = 0
    bitrate: int = 0
    # Phase 3: per-stream detail (additive; convenience fields above = first audio stream).
    audio_streams: list[dict] = field(default_factory=list)  # [{index,codec,channels,sample_rate,bitrate,duration,start_time}]
    fps_nominal: float = 0.0  # r_frame_rate (container default; often bogus like 90000/1)
    fps_rational: str = ""  # avg_frame_rate raw "num/den" (measured)
    video_time_base: str = ""  # video stream time_base for timestamp diagnosis


@dataclass
class EditDecision:
    """Phase 8: ONE decision on the ORIGINAL source timeline (never renumbered).

    action is KEEP or REMOVE. Coordinates are source seconds; rendering
    transforms the timeline later. (The Phase 1 keep/remove-list placeholder
    was unused anywhere and is superseded by this schema + EditDecisionList.)
    """
    decision_id: str = ""
    start: float = 0.0
    end: float = 0.0
    action: str = "KEEP"  # KEEP | REMOVE
    reason: str = "default"
    confidence: float = 1.0
    scene_id: int = -1
    word_refs: list = field(default_factory=list)  # [{word,start,end,segment_id}]
    metadata: dict = field(default_factory=dict)


@dataclass
class EditDecisionList:
    """Phase 8 deterministic EDL (JSON-serializable via asdict)."""
    source: str = ""
    duration: float = 0.0
    decisions: list[EditDecision] = field(default_factory=list)
    decision_count: int = 0
    kept_duration: float = 0.0
    removed_duration: float = 0.0
    removal_ratio: float = 0.0
    policy: dict = field(default_factory=dict)
    analysis_refs: dict = field(default_factory=dict)  # {audio,transcript,scenes} sha256
    warnings: list[str] = field(default_factory=list)
    generated_at: str = field(default_factory=_utcnow)
    cached: bool = False


@dataclass
class RenderConfig:
    """Phase 9 render configuration. Small on purpose (policies, not flags)."""
    container: str = "mp4"
    video_encoder: str = "auto"  # auto (verified HW -> CPU fallback) | explicit name
    preset: str = "veryfast"
    audio_codec: str = "aac"
    fps_policy: str = "source"  # source only in Phase 9
    resolution_policy: str = "source"  # source only in Phase 9
    accurate: bool = True  # False = fast stream-copy trims (approximate)
    duration_tol: float = 0.4
    av_sync_tol: float = 0.5
    overwrite: bool = True
    timeout: int = 600


KEEP = "KEEP"
REMOVE = "REMOVE"


@dataclass
class RenderPlan:
    encoder: str = "libx264"
    encoder_reason: str = "default CPU fallback"
    width: int = 1920
    height: int = 1080
    fps: float = 30.0
    video_args: list[str] = field(default_factory=list)
    audio_args: list[str] = field(default_factory=list)
    output: str = ""


@dataclass
class QCCheck:
    name: str
    passed: bool
    detail: str = ""


@dataclass
class QCReport:
    verdict: str = "not_run"  # pass | fail | not_run
    checks: list[QCCheck] = field(default_factory=list)
    suggested_fix: str = ""


@dataclass
class Project:
    id: str
    input_path: str
    template: str = "youtube"
    preset: str = "youtube_1080p"
    created_at: str = field(default_factory=_utcnow)
    engine_version: str = "0.1.0"
    stages: dict = field(default_factory=dict)  # stage -> {"status": ..., "artifact": ...}

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Project":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class Evidence:
    """Phase 10: one explainable measurement behind a decision. All fields
    required — vague reasons without evidence are a design violation."""
    evidence_type: str = ""
    source: str = ""          # silence | transcript | scenes | edl | policy
    start: float = 0.0
    end: float = 0.0
    metric: str = ""
    value: float | str = 0.0
    threshold: float | str = 0.0
    explanation: str = ""


@dataclass
class SceneSpeechMetrics:
    scene_id: int = -1
    start: float = 0.0
    end: float = 0.0
    duration: float = 0.0
    speech_duration: float = 0.0
    speech_density: float = 0.0  # speech_duration / scene_duration
    word_count: int = 0
    duration_outlier: str = ""   # "" | long | short (flag only, never deletion)


@dataclass
class PacingMetrics:
    scene_count: int = 0
    avg_shot_duration: float = 0.0
    median_shot_duration: float = 0.0
    scene_changes_per_min: float = 0.0
    words_per_min: float = 0.0
    pauses_per_min: float = 0.0
    avg_pause_duration: float = 0.0


@dataclass
class RepetitionCandidate:
    text: str = ""
    spans: list = field(default_factory=list)  # [{start,end,segment_id}]
    similarity: float = 1.0  # exact lexical match only in Phase 10
    confidence: float = 0.6  # rule confidence, labeled as such (not a probability)
    evidence: list[Evidence] = field(default_factory=list)


@dataclass
class JumpCutCandidate:
    gap_start: float = 0.0
    gap_end: float = 0.0
    gap_duration: float = 0.0
    before_scene_id: int = -1
    after_scene_id: int = -1
    same_scene: bool = False
    potential_jump_cut: bool = False
    evidence: list[Evidence] = field(default_factory=list)


@dataclass
class CutSafety:
    decision_id: str = ""
    start: float = 0.0
    end: float = 0.0
    status: str = "SAFE"  # SAFE | CAUTION | UNSAFE (technical states only)
    evidence: list[Evidence] = field(default_factory=list)


@dataclass
class IntelligenceReport:
    """Phase 10 report (JSON-serializable via asdict). Measurements only;
    the only EDL changes allowed are documented refinements."""
    source: str = ""
    input_edl_hash: str = ""
    duration: float = 0.0
    policy: dict = field(default_factory=dict)
    scene_metrics: list[SceneSpeechMetrics] = field(default_factory=list)
    median_scene_duration: float = 0.0
    pacing: PacingMetrics = field(default_factory=PacingMetrics)
    continuity: list[dict] = field(default_factory=list)
    repetitions: list[RepetitionCandidate] = field(default_factory=list)
    jump_cuts: list[JumpCutCandidate] = field(default_factory=list)
    cut_safety: list[CutSafety] = field(default_factory=list)
    preferred_points: list[dict] = field(default_factory=list)
    sentence_signals: dict = field(default_factory=dict)
    refined_edl_hash: str = ""
    refined_changes: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    engine_version: str = "phase10-1.0"
    processing_s: float = 0.0
    cached: bool = False


@dataclass
class VisualFrame:
    """Phase 11: one sampled frame. Detection lists stay empty when the
    capability is unavailable — absence is data, never an error."""
    timestamp: float = 0.0
    frame_index: int = 0
    scene_id: int = -1
    kind: str = "middle"  # begin | middle | end | fps | fixed
    width: int = 0
    height: int = 0
    brightness: float = 0.0
    brightness_p5: float = 0.0
    brightness_p95: float = 0.0
    contrast: float = 0.0
    sharpness: float = 0.0  # Laplacian variance (scale-dependent; see docs)
    motion_score: float = 0.0  # mean absdiff vs previous sample, 0..1
    flow_score: float = 0.0  # Farneback mean magnitude, px/frame
    dhash: str = ""
    quality_flags: list[str] = field(default_factory=list)
    faces: list = field(default_factory=list)  # FaceDetection dicts
    objects: list = field(default_factory=list)  # ObjectDetection dicts


@dataclass
class FaceDetection:
    """DETECTION ONLY. No identity, no attributes — bbox geometry alone."""
    bbox: list = field(default_factory=list)  # [x, y, w, h] pixels
    confidence: float = 0.0
    timestamp: float = 0.0
    scene_id: int = -1
    size_ratio: float = 0.0  # bbox area / frame area
    backend: str = ""


@dataclass
class ObjectDetection:
    label: str = ""
    confidence: float = 0.0
    bbox: list = field(default_factory=list)
    timestamp: float = 0.0
    scene_id: int = -1
    size_ratio: float = 0.0
    backend: str = ""


@dataclass
class SceneVisualSummary:
    scene_id: int = -1
    start: float = 0.0
    end: float = 0.0
    duration: float = 0.0
    sampled_frame_count: int = 0
    brightness_mean: float = 0.0
    brightness_std: float = 0.0
    contrast_mean: float = 0.0
    sharpness_mean: float = 0.0
    motion_mean: float = 0.0
    motion_max: float = 0.0
    face_count_mean: float = 0.0
    face_presence_ratio: float = 0.0
    object_labels: dict = field(default_factory=dict)  # label -> count
    duplicate_ratio: float = 0.0
    quality_warnings: dict = field(default_factory=dict)  # flag -> count
    framing: dict = field(default_factory=dict)
    representative_frame: dict = field(default_factory=dict)


@dataclass
class VisualAnalysisResult:
    """Phase 11 report (JSON-serializable via asdict)."""
    schema_version: str = "visual-1.0"
    source: dict = field(default_factory=dict)  # {path, media_hash}
    configuration: dict = field(default_factory=dict)
    capabilities: dict = field(default_factory=dict)
    scenes_analyzed: int = 0
    frame_samples: list[VisualFrame] = field(default_factory=list)
    scene_summaries: list[SceneVisualSummary] = field(default_factory=list)
    continuity: list[dict] = field(default_factory=list)
    static_spans: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    processing_s: float = 0.0
    cached: bool = False


@dataclass
class StyleProfile:
    """Phase 12: explicit editing objective. No hidden behavior — every
    downstream choice traces to these fields."""
    name: str = "general"
    pacing: str = "normal"  # relaxed | normal | brisk
    target_duration: float | None = None
    visual_density: str = "medium"  # low | medium | high (desired variety)
    broll_intensity: str = "low"  # off | low | medium | high
    silence_tolerance_s: float = 1.5
    jump_cut_tolerance: str = "medium"  # low | medium | high
    repetition_policy: str = "investigate"  # keep | investigate | trim_candidate
    subtitle_importance: str = "normal"  # low | normal | high
    hook_importance: str = "normal"  # low | normal | high
    max_cuts_per_min: float = 12.0


@dataclass
class HookAssessment:
    start: float = 0.0
    end: float = 0.0
    hook_strength_signals: list = field(default_factory=list)
    removable_preamble: list = field(default_factory=list)  # [{start,end,reason}]
    recommended_opening_strategy: str = "unknown"  # keep_as_is | trim_preamble | investigate
    confidence: float = 0.0
    limitation: str = ""


@dataclass
class StorySegment:
    segment_id: int = 0
    start: float = 0.0
    end: float = 0.0
    classification: str = "unknown"
    confidence: float = 0.0
    evidence: list = field(default_factory=list)  # Evidence dicts
    scene_ids: list = field(default_factory=list)


@dataclass
class DensityWindow:
    start: float = 0.0
    end: float = 0.0
    words_per_sec: float = 0.0
    unique_ratio: float = 0.0
    sentence_count: int = 0
    pause_s: float = 0.0
    repetition_hits: int = 0
    scene_changes: int = 0
    density: str = "unknown"  # high | normal | low (relative to median)
    components: dict = field(default_factory=dict)


@dataclass
class CutCandidate:
    decision_id: str = ""
    start: float = 0.0
    end: float = 0.0
    verdict: str = "investigate"  # approve | approve_with_mitigation | downgrade_keep | reject | candidate_for_trim
    base_action: str = ""
    priority: str = "informational"  # critical | high | medium | low | informational
    confidence: float = 0.0  # evidence strength, NOT importance
    factors: list = field(default_factory=list)  # 10-factor evidence entries
    alternatives: list = field(default_factory=list)


@dataclass
class BrollOpportunity:
    start: float = 0.0
    end: float = 0.0
    duration: float = 0.0
    reason: str = ""
    desired_visual_type: str = "supporting_footage"
    semantic_topic: str = ""
    transcript_ref: dict = field(default_factory=dict)
    priority: str = "low"  # + recommended flag below (optional vs recommended)
    recommended: bool = False
    confidence: float = 0.0
    evidence: list = field(default_factory=list)


@dataclass
class VisualChange:
    start: float = 0.0
    end: float = 0.0
    action: str = "unknown"  # keep_current_shot | cut_to_next_scene | broll | cutaway | reframe | zoom | graphic | unknown
    reason: str = ""
    priority: str = "informational"
    confidence: float = 0.0
    evidence: list = field(default_factory=list)


@dataclass
class AudioRecommendation:
    kind: str = ""  # silence_reduction | filler_removal | dialogue_leveling | preserve_pause | later_phase
    start: float | None = None
    end: float | None = None
    detail: str = ""
    priority: str = "informational"
    confidence: float = 0.0
    evidence: list = field(default_factory=list)


@dataclass
class EditorialRepetition:
    text: str = ""
    spans: list = field(default_factory=list)
    similarity: float = 1.0
    confidence: float = 0.0
    editorial_reason: str = ""
    recommended_action: str = "keep"  # keep | investigate | candidate_for_trim
    evidence: list = field(default_factory=list)


@dataclass
class QualityRisk:
    kind: str = ""  # attention_risk | pacing_risk | visual_stagnation | repetition_risk
    start: float = 0.0
    end: float = 0.0
    priority: str = "informational"
    confidence: float = 0.0
    evidence: list = field(default_factory=list)


@dataclass
class ConflictResolution:
    topic: str = ""
    pro_signals: list = field(default_factory=list)
    con_signals: list = field(default_factory=list)
    winner: str = ""  # keep | cut | broll | investigate
    principle: str = ""  # ordered principle that decided
    explanation: str = ""


@dataclass
class ProfessionalEditPlan:
    """Phase 12 master plan (JSON-serializable via asdict). Planning only."""
    schema_version: str = "editor-plan-1.0"
    project: str = ""
    source: str = ""
    duration: float = 0.0
    editing_style: StyleProfile = field(default_factory=StyleProfile)
    hook: HookAssessment = field(default_factory=HookAssessment)
    story_structure: list[StorySegment] = field(default_factory=list)
    density_windows: list[DensityWindow] = field(default_factory=list)
    pacing_analysis: list = field(default_factory=list)  # [{scope, verdict, evidence}]
    cut_plan: list[CutCandidate] = field(default_factory=list)
    jump_strategy: list = field(default_factory=list)
    broll_plan: list[BrollOpportunity] = field(default_factory=list)
    visual_change_plan: list[VisualChange] = field(default_factory=list)
    audio_plan: list[AudioRecommendation] = field(default_factory=list)
    repetition_candidates: list[EditorialRepetition] = field(default_factory=list)
    quality_risks: list[QualityRisk] = field(default_factory=list)
    conflicts: list[ConflictResolution] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    evidence_index: list = field(default_factory=list)
    engine_version: str = "phase12-1.0"
    processing_s: float = 0.0
    cached: bool = False


@dataclass
class BrollAsset:
    """Phase 13: a LOCAL user-provided B-roll asset. source_type is always
    local in this phase (no stock APIs, no downloads — by architecture)."""
    asset_id: str = ""
    path: str = ""
    media_hash: str = ""  # size + mtime_ns + sha256(first 4 MB)
    duration: float = 0.0
    width: int = 0
    height: int = 0
    fps: float = 0.0
    has_audio: bool = False
    source_type: str = "local"  # local only in Phase 13
    aspect_ratio: str = ""
    codec: str = ""
    pixel_format: str = ""
    created_at: str = field(default_factory=_utcnow)
    validation_status: str = "unknown"  # valid | invalid
    validation_errors: list = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


@dataclass
class PlanApproval:
    """Phase 13: immutable explicit approval snapshot. RECOMMENDED (brain)
    becomes APPROVED here; EXECUTED is recorded later in the manifest.
    Timestamps are informational only (never part of hashes)."""
    schema_version: str = "approval-1.0"
    plan_hash: str = ""
    source_fingerprint: dict = field(default_factory=dict)
    analysis_hashes: dict = field(default_factory=dict)
    approved_cuts: list = field(default_factory=list)  # [{decision_id, verdict}]
    broll_assignments: list = field(default_factory=list)
    jump_approvals: list = field(default_factory=list)
    status: str = "approved"
    warnings: list[str] = field(default_factory=list)
    approved_at: str = field(default_factory=_utcnow)
    approver: str = "operator"


@dataclass
class ExecutionOp:
    """Phase 13: one concrete renderer operation. Source and output
    coordinates are explicitly separate fields."""
    operation_id: str = ""
    action: str = "keep"  # keep | remove | broll_replace | broll_overlay
    source_start: float = 0.0
    source_end: float = 0.0
    output_start: float = 0.0
    output_end: float = 0.0
    source: str = ""
    asset_id: str = ""
    layer: str = "base"  # base | overlay
    priority: str = "medium"
    reason: str = ""
    evidence_refs: list = field(default_factory=list)
    approval_state: str = "approved"  # approved | rejected | executed
    confidence: float = 0.0
    scene_id: int = -1
    fit_strategy: str = "cover"
    audio_mode: str = "mute"  # mute | original (mix/duck unsupported in Phase 13)
    fallback_action: str = ""
    metadata: dict = field(default_factory=dict)


@dataclass
class ExecutionPlanModel:
    """Phase 13: the complete executable timeline. Everything the renderer
    needs is reconstructible from this object alone."""
    schema_version: str = "execution-plan-1.0"
    execution_version: str = "1.0.0"
    source: str = ""
    source_fingerprint: dict = field(default_factory=dict)
    approved_plan_hash: str = ""
    approval_hash: str = ""
    operations: list[ExecutionOp] = field(default_factory=list)
    assignments: list = field(default_factory=list)  # broll assignments (opportunity spans)
    expected_duration: float = 0.0
    assets: dict = field(default_factory=dict)  # asset_id -> BrollAsset dict
    render_config: dict = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


@dataclass
class CaptionWord:
    """Phase 14: frozen copy of a transcript word (plan is self-contained and
    deterministic even if the transcript artifact later changes)."""
    word_id: str = ""
    text: str = ""
    start: float = 0.0
    end: float = 0.0
    probability: float = 0.0
    segment_id: int = 0


@dataclass
class CaptionCue:
    """Phase 14: one subtitle event on the SOURCE timeline (mapped later)."""
    cue_id: str = ""
    start: float = 0.0
    end: float = 0.0
    text: str = ""  # display text, lines joined by \n
    lines: list = field(default_factory=list)
    word_refs: list = field(default_factory=list)  # CaptionWord dicts
    language: str = ""
    confidence: float = 0.0  # mean word probability (labeled, not precise)
    style: str = "default"
    scene_id: int = -1
    line_count: int = 0
    character_count: int = 0
    reading_cps: float = 0.0
    reading_wpm: float = 0.0
    split_reason: str = ""
    warnings: list = field(default_factory=list)


@dataclass
class CaptionPlan:
    """Phase 14 deterministic plan (JSON source of truth; SRT/VTT/ASS derived)."""
    schema_version: str = "caption-plan-1.0"
    source: str = ""
    transcript_hash: str = ""
    caption_version: str = "1.0.0"
    cues: list[CaptionCue] = field(default_factory=list)
    cue_count: int = 0
    style: str = "default"
    language: str = ""
    warnings: list = field(default_factory=list)
    expected_duration: float = 0.0
    config: dict = field(default_factory=dict)
    cached: bool = False


@dataclass
class CaptionVisualContext:
    """Phase 15: measured visual facts behind one cue (never guessed)."""
    cue_id: str = ""
    scene_id: int = -1
    brightness: float = 0.0
    contrast: float = 0.0
    motion: float = 0.0
    static_score: float = 0.0
    visual_change: str = "unknown"  # stable | changed | large_change | unknown
    face_available: bool = False
    face_regions: list = field(default_factory=list)
    safe_regions: list = field(default_factory=list)  # band names usable
    band_stats: dict = field(default_factory=dict)  # band -> {mean, std}
    frame_timestamp: float = 0.0


@dataclass
class CaptionPlacement:
    """Phase 15: deterministic placement with reason + confidence."""
    cue_id: str = ""
    position: str = "bottom"  # top | center | bottom
    x: float = 0.5  # normalized anchor 0..1
    y: float = 0.92  # normalized anchor 0..1
    anchor: str = "bottom-center"
    safe_area: dict = field(default_factory=dict)  # margins + bounds used
    reason: str = "style_default"
    confidence: float = 0.5

    def __post_init__(self) -> None:
        self.anchor = {"bottom": "bottom-center", "center": "middle-center",
                       "top": "top-center"}.get(self.position, "bottom-center")
        self.y = {"bottom": 0.92, "center": 0.5, "top": 0.08}.get(
            self.position, 0.92)


@dataclass
class CaptionEmphasis:
    """Phase 15: optional word emphasis. Timing always from transcript."""
    cue_id: str = ""
    word_refs: list = field(default_factory=list)  # [{word,start,end,...}]
    emphasis_type: str = "none"  # none | keyword | important_words
    reason: str = ""
    confidence: float = 0.0


@dataclass
class VisualCaptionPlan:
    """Phase 15 deterministic plan (JSON source of truth for polish)."""
    schema_version: str = "visual-caption-plan-1.0"
    source_hash: str = ""
    caption_plan_hash: str = ""
    visual_analysis_hash: str = ""
    style: str = "default"
    placements: list[CaptionPlacement] = field(default_factory=list)
    emphasis: list[CaptionEmphasis] = field(default_factory=list)
    contexts: list[CaptionVisualContext] = field(default_factory=list)
    adaptations: dict = field(default_factory=dict)  # cue_id -> style patch
    conflicts: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    version: str = "1.0.0"
    cached: bool = False


@dataclass
class CaptionPacingContext:
    """Phase 16: measured evidence roll-up for one scene (references, not
    copies, of large artifacts)."""
    scene_id: int = -1
    scene_start: float = 0.0
    scene_end: float = 0.0
    scene_duration: float = 0.0
    caption_cue_ids: list = field(default_factory=list)
    caption_duration: float = 0.0
    words_per_cue: float = 0.0
    cps: float = 0.0
    wpm: float = 0.0
    caption_density: float = 0.0  # captioned seconds / scene seconds
    pause_gaps: list = field(default_factory=list)
    visual_stagnation: float = 0.0  # 0..1 (static-span coverage)
    visual_change: str = "unknown"  # stable | changed | large_change | unknown
    edit_safety: str = "unknown"  # best (least safe) CutSafety over scene REMOVEs
    editor_candidate: str = ""  # brain cut verdict touching this scene, if any
    caption_placement: str = "unknown"
    caption_contrast: str = "unknown"  # GOOD/CAUTION/POOR/unknown
    visual_conflicts: int = 0
    confidence: float = 0.5
    warnings: list = field(default_factory=list)


@dataclass
class PacingSignal:
    """Phase 16: measured evidence. Signals are NOT edit decisions."""
    signal_id: str = ""
    signal_type: str = ""  # one of the 15 SIGNAL_TYPES
    start: float = 0.0
    end: float = 0.0
    scene_id: int = -1
    severity: str = "info"  # info | low | medium | high
    confidence: float = 0.0
    evidence: list = field(default_factory=list)
    metrics: dict = field(default_factory=dict)
    source_refs: list = field(default_factory=list)


@dataclass
class PacingRecommendation:
    """Phase 16: conservative editorial suggestion (never auto-executed)."""
    recommendation_id: str = ""
    action: str = "KEEP"  # KEEP|TRIM|SPLIT|ACCELERATE_VISUAL|HOLD_LONGER|CHANGE_VISUAL|ADD_CUTAWAY_OPPORTUNITY|REVIEW
    start: float = 0.0
    end: float = 0.0
    scene_id: int = -1
    priority: str = "informational"  # critical|high|medium|low|informational
    confidence: float = 0.0  # evidence strength, NOT importance
    reason: str = ""
    evidence: list = field(default_factory=list)
    supporting_signals: list = field(default_factory=list)
    safety_status: str = "unknown"  # SAFE|CAUTION|UNSAFE|unknown
    affected_caption_ids: list = field(default_factory=list)
    affected_visual_context: str = ""
    source_refs: list = field(default_factory=list)
    warnings: list = field(default_factory=list)


@dataclass
class PacingExecutionApproval:
    """Phase 17: immutable approval snapshot for executing approved pacing
    recommendations. RECOMMENDED/APPROVED/EXECUTED/INVALID states keep
    intelligence approval and execution approval distinct."""
    schema_version: str = "pacing-execution-approval-1.0"
    project_id: str = ""
    source_hash: str = ""
    edit_plan_hash: str = ""  # base EDL hash (edit/edit_decision.json)
    base_approval_hash: str = ""  # approved_edit_plan hash, or "none"
    caption_plan_hash: str = ""
    caption_approval_hash: str = ""
    visual_caption_plan_hash: str = ""
    visual_caption_approval_hash: str = ""
    pacing_plan_hash: str = ""
    pacing_approval_hash: str = ""
    style: str = "general"
    config_hash: str = ""
    code_version: str = "phase17-1.0"
    approved_recommendation_ids: list = field(default_factory=list)
    rejected_recommendation_ids: list = field(default_factory=list)
    generated_execution_policy: dict = field(default_factory=dict)
    approval_state: str = "APPROVED"  # RECOMMENDED|APPROVED|EXECUTED|INVALID
    derived_edl_hash: str = ""
    execution_plan_hash: str = ""
    approved_at: str = ""
    approver: str = "operator"
    warnings: list = field(default_factory=list)


@dataclass
class PacingExecutionOp:
    """Phase 17: one concrete operation derived from an approved pacing
    recommendation. Only TRIM/SPLIT modes may reach rendering."""
    op_id: str = ""
    recommendation_id: str = ""
    action: str = "KEEP"  # Phase 16 action verb (TRIM|SPLIT|...)
    source_start: float = 0.0
    source_end: float = 0.0
    output_start: float = 0.0
    output_end: float = 0.0
    scene_id: int = -1
    caption_ids: list = field(default_factory=list)
    safety_status: str = "unknown"  # SAFE|CAUTION|UNSAFE|unknown
    confidence: float = 0.0
    reason: str = ""
    evidence_refs: list = field(default_factory=list)
    execution_mode: str = "NOOP"  # TRIM|SPLIT|VISUAL_CHANGE|CUTAWAY_OPPORTUNITY|HOLD|NOOP
    warnings: list = field(default_factory=list)


@dataclass
class PacingExecutionPlan:
    """Phase 17 deterministic derived execution artifact (canonical part
    carries no wall-clock; runtime metadata lives in the manifest)."""
    schema_version: str = "caption-pacing-execution-plan-1.0"
    project_id: str = ""
    source_hash: str = ""
    base_execution_plan_hash: str = ""  # edl_hash of the derived EDL
    pacing_plan_hash: str = ""
    pacing_approval_hash: str = ""
    caption_plan_hash: str = ""
    visual_caption_plan_hash: str = ""
    execution_ops: list[PacingExecutionOp] = field(default_factory=list)
    source_to_output_mapping: list = field(default_factory=list)
    removed_ranges: list = field(default_factory=list)
    preserved_ranges: list = field(default_factory=list)
    caption_mapping_preview: dict = field(default_factory=dict)
    visual_caption_mapping_preview: dict = field(default_factory=dict)
    safety_summary: dict = field(default_factory=dict)
    rejected_ops: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    execution_hash: str = ""
    cached: bool = False


@dataclass
class CaptionPacingPlan:
    """Phase 16 deterministic artifact (no wall-clock inside the hash)."""
    schema_version: str = "caption-pacing-plan-1.0"
    project_id: str = ""
    source_hash: str = ""
    edit_plan_hash: str = ""
    caption_plan_hash: str = ""
    visual_caption_plan_hash: str = ""
    style: str = "general"
    context_summary: list[CaptionPacingContext] = field(default_factory=list)
    signals: list[PacingSignal] = field(default_factory=list)
    recommendations: list[PacingRecommendation] = field(default_factory=list)
    conflicts: list = field(default_factory=list)
    rejected: list = field(default_factory=list)
    safety_summary: dict = field(default_factory=dict)
    statistics: dict = field(default_factory=dict)
    warnings: list = field(default_factory=list)
    engine_version: str = "phase16-1.0"
    cached: bool = False


@dataclass
class VisualOp:
    """Phase 24: one visual operation derived from an approved pacing
    recommendation plus an explicitly bound asset candidate."""
    op_id: str = ""
    recommendation_id: str = ""
    action: str = "CHANGE_VISUAL"  # CHANGE_VISUAL|ADD_CUTAWAY_OPPORTUNITY
    source_start: float = 0.0
    source_end: float = 0.0
    asset_id: str = ""
    asset_path: str = ""
    mode: str = "CUTAWAY_OVERLAY"  # VISUAL_REPLACE|CUTAWAY_OVERLAY
    safety_status: str = "unknown"  # SAFE|CAUTION|UNSAFE|unknown
    confidence: float = 0.0
    reason: str = ""
    evidence: list = field(default_factory=list)


@dataclass
class VisualPlan:
    """Phase 24 deterministic derived visual plan (no wall-clock in hash)."""
    schema_version: str = "visual-execution-plan-1.0"
    project_id: str = ""
    pacing_plan_hash: str = ""
    pacing_approval_hash: str = ""
    execution_ops: list[VisualOp] = field(default_factory=list)
    unfulfilled: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    execution_hash: str = ""


@dataclass
class VisualApproval:
    """Phase 24 explicit approval of visual ops (separate from all priors)."""
    schema_version: str = "visual-execution-approval-1.0"
    project_id: str = ""
    pacing_plan_hash: str = ""
    pacing_approval_hash: str = ""
    approved_op_ids: list = field(default_factory=list)
    execution_hash: str = ""
    approval_state: str = "APPROVED"  # APPROVED|EXECUTED|INVALID
    approved_at: str = ""
    approver: str = "operator"


@dataclass
class PunchRange:
    """Talking-head punch-in: reframed span with reason (never random)."""
    start: float = 0.0
    end: float = 0.0
    scale: float = 1.08
    reason: str = ""
    confidence: float = 0.0


@dataclass
class PunchPlan:
    """Deterministic punch-in plan (focus recorded for audit)."""
    schema_version: str = "punch-plan-1.0"
    focus_x: float = 0.5
    focus_y: float = 0.5
    ranges: list[PunchRange] = field(default_factory=list)


@dataclass
class PunchApproval:
    """Explicit approval binding plan + transcript + focus."""
    schema_version: str = "punch-approval-1.0"
    project_id: str = ""
    plan_hash: str = ""
    transcript_hash: str = ""
    focus_x: float = 0.5
    focus_y: float = 0.5
    approval_state: str = "APPROVED"
    approved_at: str = ""
    approver: str = "operator"
