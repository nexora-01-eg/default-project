# What Al-Montier is missing

| Gap | Current state / why it matters | Severity | Difficulty / dependencies | Recommended action | Can CODEX implement it? |
|---|---|---|---|---|---|
| Egyptian, natural local narration | VoiceTut is blocked; Kareem is not Egyptian and measured too slow for a real 60–90s script | Critical | External legal voice/model or human recording | Obtain an approved local Egyptian voice; never retry blocked Space automatically | No |
| Contract-to-render executor | The one real production uses a hard-coded script | Critical | Engineering only | implement a renderer for validated `production_plan.json` | Yes |
| Semantic asset intelligence | No local embeddings/classifier; filenames are not evidence | High | Curated local model/index and visual review | build offline index and candidate contact sheets | Partly |
| Motion compositor | ASS effects/static crop are not general animation | High | FFmpeg filter/keyframe design or local compositor | declarative position/scale/opacity/easing, then masks/shapes | Yes, staged |
| Captions with true word timing | Existing target captions approximate timing | High | reliable STT/alignment, Arabic shaping QA | alignment + per-word render tests | Partly |
| Audio mastering/ducking | Basic gain and mix only | High | FFmpeg filters plus calibration fixtures | side-chain ducking, LUFS/true-peak verification | Yes |
| Independent visual review | Rules inspect metadata, not semantic output | High | local vision model or human review | frame contact sheet plus human gate first | Partly |
| SFX/ambience system | absent | Medium | licensed local catalog + metadata | index assets and support timed attenuated layers | Yes |
| Transition library | hard cuts dominate, no purpose-aware executor | Medium | FFmpeg filter implementations | add fade/dip/slide/push with acceptance tests | Yes |
| Tool-path health | FFprobe environment points to a non-existent executable | Critical for current run | local configuration | repair configuration, doctor, smoke render | Yes |
