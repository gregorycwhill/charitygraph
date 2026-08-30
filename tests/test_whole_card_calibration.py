import pytest

from charitygraph.whole_card_calibration import (
    EvidenceRef,
    WholeCardExtractionOutput,
    packet_sha,
    locator_resolves,
    validate_output,
)


def assessment_rows():
    return [{"section_id": i, "status": "insufficient_evidence", "note": None} for i in range(1, 21)]


def test_output_requires_exactly_twenty_section_assessments():
    with pytest.raises(ValueError):
        WholeCardExtractionOutput.model_validate({"section_assessments": assessment_rows()[:-1], "observations": []})


def test_supported_observation_requires_supporting_evidence():
    payload = {"section_id": 1, "scope": {"kind": "subject", "label": None}, "proposition": "A bounded proposition", "epistemic_status": "supported", "temporal_scope": {"kind": "current", "value": None}, "evidence": [{"source_record_id": "srcrec:x", "packet_locator": "[S001:L0001]", "role": "context", "excerpt": "context"}], "qualifications": []}
    with pytest.raises(ValueError):
        WholeCardExtractionOutput.model_validate({"section_assessments": assessment_rows(), "observations": [payload]})


def test_packet_hash_ignores_optional_embedded_hash_field():
    packet = {"packet_version": "v0.1", "sources": []}
    assert packet_sha(packet) == packet_sha({**packet, "packet_sha256": "stale"})


def test_evidence_locator_must_resolve_to_packet_source():
    payload = {"section_id": 1, "scope": {"kind": "subject", "label": None}, "proposition": "A bounded proposition", "epistemic_status": "supported", "temporal_scope": {"kind": "current", "value": None}, "evidence": [{"source_record_id": "srcrec:x", "packet_locator": "[S001:L0001]", "role": "supporting", "excerpt": "exact"}], "qualifications": []}
    with pytest.raises(ValueError):
        validate_output({"section_assessments": assessment_rows(), "observations": [payload]}, {"sources": []})


def test_packet_locator_ranges_resolve_within_source_namespace():
    valid = {f"[S001:L{i:04d}]" for i in range(1, 4)}
    assert locator_resolves("[S001:L0001]-[S001:L0003]", valid)
    assert not locator_resolves("[S001:L0001]-[S002:L0003]", valid)


def test_model_cost_preflight_uses_model_specific_rates():
    import importlib.util
    from pathlib import Path
    script = Path(__file__).parents[1] / "scripts" / "run_whole_card_calibration_v01.py"
    spec = importlib.util.spec_from_file_location("whole_card_runner", script)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    _, projected = module._estimate(b"x" * 4000, "prompt")
    assert projected["gpt-5.6-terra"] > projected["gpt-5.6-luna"]
