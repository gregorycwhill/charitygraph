import json


from charitygraph.native_discovery_executor import DISCOVERY_PROMPT, _parse_discovery_output, build_prompt
from charitygraph.contracts import ProgramServiceDiscoveryOutput, ProgramServiceDiscoveryOutputV2, discovery_output_schema_ref_v2
from charitygraph.native_program_discovery import TASK_SCHEMA_V2

from tests.contracts._helpers import task


def test_prompt_is_explicit_and_evidence_bound():
    assert "Do not infer effectiveness" in DISCOVERY_PROMPT
    assert "Every proposal must cite" in DISCOVERY_PROMPT


def test_build_prompt_preserves_task_evidence_order():
    model_task = task()
    first = model_task.evidence_inputs[0].evidence_id
    rendered = build_prompt(model_task, {first: "bounded evidence"})
    assert rendered.index(f"[{first}]") < rendered.index("bounded evidence")



def test_v2_prompt_dispatch_uses_v2_identity_and_guidance():
    model_task = task()
    rendered = build_prompt(model_task, {model_task.evidence_inputs[0].evidence_id: "bounded evidence"}, v2=True)
    assert "Current availability is not subject identity" in rendered
    assert "Current availability is not subject identity" not in DISCOVERY_PROMPT

def _v2_task():
    base = task()
    evidence_id = base.evidence_inputs[0].evidence_id
    return base.model_copy(update={
        "task_schema": TASK_SCHEMA_V2,
        "output_schema": discovery_output_schema_ref_v2((evidence_id,)),
    })


def test_parser_uses_v1_model_for_v1_task():
    output, errors = _parse_discovery_output(task(), '{"proposals": []}')
    assert isinstance(output, ProgramServiceDiscoveryOutput)
    assert errors == ()


def test_parser_uses_v2_model_and_preserves_operational_status():
    payload = {"proposals": [{
        "proposal_key": "historical",
        "label": "Historical service",
        "disposition": "service",
        "operational_status": "historical",
        "evidence": [{"evidence_id": "evidence:2" + "0" * 31, "role": "supporting", "note": None}],
        "rationale": "Direct evidence",
        "confidence": "high",
        "competing_interpretation": None,
    }]}
    output, errors = _parse_discovery_output(_v2_task(), json.dumps(payload))
    assert isinstance(output, ProgramServiceDiscoveryOutputV2)
    assert output.proposals[0].operational_status == "historical"
    assert errors == ()


def test_parser_invalid_response_returns_typed_v2_empty_output_without_name_error():
    output, errors = _parse_discovery_output(_v2_task(), '{"proposals": [{"invalid": true}]}')
    assert isinstance(output, ProgramServiceDiscoveryOutputV2)
    assert output.proposals == ()
    assert errors
