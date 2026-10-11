# Production Tool Router

## Discovery (`engine/tools/registry.py`)

`discover()` probes the live environment per provider: Python import, binary on PATH, engine-internal resolver (ffmpeg), or always-on. Each provider gets `{status, reason, capabilities}` with status in AVAILABLE / MISSING / HARDWARE_BLOCKED / LICENSE_BLOCKED / UNKNOWN_PROVIDER. License blocks (pedalboard, aubio, remotion) report regardless of presence. `hardware_profile()` records CPU/RAM/ffmpeg/CUDA-likely-false. Nothing installs or downloads.

## Selection (`engine/tools/router.py`)

`resolve(capability, params, preferred, allow_fallback)` scores AVAILABLE providers on fixed weights (fit 30, code-control 15, local 10, hardware 15, determinism 10, license 10, cost 5, maintenance 5; suitability table in code) with deterministic tie-break (score desc, id asc). Recorded decisions:
- SELECTED / SELECTED_PREFERRED — executed.
- SELECTED_FALLBACK — only with explicit `allow_fallback=True`; reason names requested vs actual provider.
- TOOL_UNAVAILABLE / HARDWARE_BLOCKED / LICENSE_BLOCKED / CAPABILITY_MISSING / UNKNOWN_PROVIDER — never a silent substitution.

## Execution (`engine/tools/adapters/`)

18 adapters (see INTEGRATED_PRODUCTION_STACK). Each exposes `available()` and `run(contract) -> artifact{kind,path,provider,...}`. Missing deps raise `ToolUnavailable(provider, reason)`. Adapters delegate to engine gateways or validated libs; they never install/download (model files are explicit contract inputs with recorded provenance).

## Artifact handling / provenance / caching / reproducibility

Artifacts carry provider id + params; production manifests record routing log (`smoke build.json` includes full routing decisions). Content-hash caching remains in `engine/core/pipeline.py` for analysis stages; render artifacts are timestamped outputs (never overwrite). Determinism: sorted ids, fixed weights, pinned versions, recorded seeds where stochastic (Piper noise defaults, diffusion N/A).

## Failure handling / repair

Adapter failure → ToolUnavailable with reason → router decision recorded → repair router (`engine/review/repair.py`) maps issue→capability (e.g. AUDIO_CLIPPING_RISK→GAIN_REDUCE, MOTION_TOO_STATIC→CAMERA_PUSH) → bounded re-render (MAX 3 rounds policy; smoke used 1). No silent provider swaps at any stage.
