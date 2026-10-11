import json

from engine.montier_controller import ContractError, inspect_contract, load_contract


def test_contract_requires_a_complete_production_shape(tmp_path):
    p = tmp_path / "plan.json"
    p.write_text("{}", encoding="utf-8")
    try:
        load_contract(p)
    except ContractError as exc:
        assert "production contract missing" in str(exc)
    else:
        assert False


def test_contract_inspection_is_deterministic(tmp_path):
    payload = {k: {} for k in ("project", "target", "voice", "narration", "scenes", "assets", "captions", "motion", "transitions", "audio", "qc", "review", "acceptance_criteria")}
    payload.update({"schema_version": "production-plan-1.0", "project": {"id": "p"},
                    "target": {"width": 1080, "height": 1920, "fps": 30},
                    "voice": {"status": "TEMPORARY_ARABIC_TTS"},
                    "shots": [{"start": 0, "end": 2}]})
    p = tmp_path / "plan.json"
    p.write_text(json.dumps(payload), encoding="utf-8")
    assert inspect_contract(p)["duration_s"] == 2.0
