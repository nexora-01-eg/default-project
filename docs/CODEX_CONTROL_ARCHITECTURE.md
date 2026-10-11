# CODEX control architecture

CODEX is the controller; Al-Montier is the local execution system. The public control boundary is `engine.montier_controller`, its JSON production contract, and existing `python -m engine.cli` commands. Controller phases are `analyze → plan → storyboard → assets → voice → captions → motion → audio → render → review → repair → final_report`.

`production_plan.json` is validated before an execution decision. `inspect_contract()` exposes deterministic fields only. `checkpoint()` writes `controller_state.json` after an attempted phase; it is the resume checkpoint. Existing project artifacts remain the source of truth: `timeline/`, `renders/`, `qc/`, `production_manifest.json`, `repair_history.json`, and review JSON.

The controller does not call undocumented renderer internals. Existing execution is exposed through the documented CLI: `analyze`, `transcribe`, `scenes`, `edit`, `editor-plan`, approval commands, `render-plan`, and caption commands. The new controller deliberately does **not** claim an end-to-end `produce` command: the renderer cannot consume a voice-first production contract, asset matching is not semantic, and a current FFprobe configuration failure prevents a fresh verified render.

Failure routing: invalid contract → planner; absent/blocked voice → voice subsystem; missing/rejected asset → asset/shot planner; unreadable render or A/V drift → render; caption overload → captions; audio level issue → audio; failed review → the responsible subsystem, with a bounded recorded repair attempt. A final status is only emitted after independent review; human listening remains a required external review where automated intelligibility is insufficient.
