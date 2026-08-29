import pytest
from decimal import Decimal

from charitygraph.contracts import (
    DISCOVERY_OUTPUT_SCHEMA,
    DISCOVERY_OUTPUT_SCHEMA_V2,
    DISCOVERY_OUTPUT_SCHEMA_V3,
    DiscoveryEvidenceLocatorV3,
    OperatorRelationship,
    ProgramServiceDiscoveryOutput,
    ProgramServiceDiscoveryOutputV2,
    ProgramServiceDiscoveryOutputV3,
    ProgramServiceProposalV3,
    PropositionEvidenceLocatorV3,
    discovery_schema,
    discovery_schema_v2,
    discovery_schema_v3,
    discovery_schema_hash,
    discovery_schema_v2_hash,
    discovery_schema_v3_hash,
    validate_v3_evidence_quotes,
)
from charitygraph.native_discovery_executor import (
    DISCOVERY_PROMPT_V3,
    PROMPT_TEMPLATE_VERSION_V3,
    _parse_discovery_output,
    execute_native_discovery,
)
from charitygraph.native_program_discovery import TASK_SCHEMA, TASK_SCHEMA_V2, TASK_SCHEMA_V3
from types import SimpleNamespace


def _locator(evidence_id="evidence:1", quote="Named service text", role="supporting"):
    return PropositionEvidenceLocatorV3(evidence_id=evidence_id, role=role, quote=quote)


def _proposal(
    key="p",
    parent=None,
    status="unknown",
    status_evidence=(),
    operator_relationship="operated_by_subject",
    operator_relationship_evidence=None,
    evidence=None,
):
    if operator_relationship_evidence is None:
        operator_relationship_evidence = (_locator(),) if operator_relationship != "unclear" else ()
    if evidence is None:
        evidence = (_locator(),)
    return ProgramServiceProposalV3(
        proposal_key=key,
        label="Named service",
        disposition="service",
        operator_relationship=operator_relationship,
        operator_relationship_evidence=operator_relationship_evidence,
        parent_proposal_key=parent,
        operational_status=status,
        evidence=evidence,
        operational_status_evidence=status_evidence,
        rationale="Bounded evidence supports the proposal",
        confidence="medium",
    )


def test_v3_strict_model_and_schema_identity():
    output = ProgramServiceDiscoveryOutputV3(proposals=(_proposal(),))
    assert output.proposals[0].operator_relationship == "operated_by_subject"
    assert TASK_SCHEMA_V3.schema_id.endswith("task:3.0")
    assert DISCOVERY_OUTPUT_SCHEMA_V3.schema_id.endswith("output:3.0")
    assert TASK_SCHEMA.schema_id != TASK_SCHEMA_V2.schema_id != TASK_SCHEMA_V3.schema_id
    assert DISCOVERY_OUTPUT_SCHEMA.schema_id != DISCOVERY_OUTPUT_SCHEMA_V2.schema_id != DISCOVERY_OUTPUT_SCHEMA_V3.schema_id
    assert PROMPT_TEMPLATE_VERSION_V3 == "v3"


def test_v1_v2_remain_readable_and_hash_helpers_are_versioned():
    assert ProgramServiceDiscoveryOutput.model_validate({"proposals": []}).proposals == ()
    assert ProgramServiceDiscoveryOutputV2.model_validate({"proposals": []}).proposals == ()
    ids = ("evidence:1",)
    assert discovery_schema_hash(ids) != discovery_schema_v2_hash(ids)
    assert discovery_schema_v2_hash(ids) != discovery_schema_v3_hash(ids)
    assert discovery_schema(ids)["additionalProperties"] is False
    assert discovery_schema_v2(ids)["additionalProperties"] is False


def test_v3_schema_is_strict_at_every_object_level():
    schema = discovery_schema_v3(("evidence:1",))
    proposal = schema["properties"]["proposals"]["items"]
    locator = proposal["properties"]["evidence"]["items"]
    assert schema["additionalProperties"] is False
    assert proposal["additionalProperties"] is False
    assert locator["additionalProperties"] is False
    assert set(proposal["required"]) == set(proposal["properties"])
    assert "operator_relationship_evidence" in proposal["required"]
    assert proposal["properties"]["operator_relationship_evidence"]["items"]["additionalProperties"] is False


def test_v3_unique_keys_and_parent_references():
    with pytest.raises(ValueError):
        ProgramServiceDiscoveryOutputV3(proposals=(_proposal("same"), _proposal("same")))
    with pytest.raises(ValueError):
        ProgramServiceDiscoveryOutputV3(proposals=(_proposal(parent="missing"),))
    with pytest.raises(ValueError):
        ProgramServiceDiscoveryOutputV3(proposals=(_proposal(parent="p"),))
    output = ProgramServiceDiscoveryOutputV3(proposals=(_proposal("parent"), _proposal("child", parent="parent")))
    assert output.proposals[1].parent_proposal_key == "parent"


def test_v3_parent_cycles_rejected():
    with pytest.raises(ValueError):
        ProgramServiceDiscoveryOutputV3(proposals=(_proposal("a", parent="b"), _proposal("b", parent="a")))


def test_v3_verbatim_quote_validation_is_exact_and_crlf_tolerant():
    output = ProgramServiceDiscoveryOutputV3(proposals=(_proposal(),))
    assert validate_v3_evidence_quotes(output, {"evidence:1": "Prefix\r\nNamed service text\r\nSuffix"}) is output
    with pytest.raises(ValueError):
        validate_v3_evidence_quotes(output, {"evidence:1": "Named  service text"})
    with pytest.raises(ValueError):
        validate_v3_evidence_quotes(output, {"evidence:1": "Other text"})
    with pytest.raises(ValueError):
        validate_v3_evidence_quotes(output, {"evidence:2": "Named service text"})


def test_v3_context_quote_may_be_null_but_claim_roles_require_quote():
    assert DiscoveryEvidenceLocatorV3(evidence_id="evidence:1", role="context", quote=None)
    with pytest.raises(ValueError):
        PropositionEvidenceLocatorV3(evidence_id="evidence:1", role="supporting", quote=None)
    with pytest.raises(ValueError):
        PropositionEvidenceLocatorV3(evidence_id="evidence:1", role="competing", quote="   ")


def test_v3_status_evidence_rules():
    assert _proposal(status="unknown").operational_status == "unknown"
    with pytest.raises(ValueError):
        _proposal(status="current")
    with pytest.raises(ValueError):
        _proposal(status="current", status_evidence=(_locator(role="context", quote=None),))
    current = _proposal(status="current", status_evidence=(_locator(quote="Current service"),))
    assert current.operational_status_evidence[0].role == "supporting"


def test_v3_operator_relationship_is_strict():
    for relationship in ("operated_by_subject", "jointly_operated_or_partnered", "supported_or_hosted_by_subject", "externally_operated", "unclear"):
        value = _proposal().model_dump(mode="python")
        value["operator_relationship"] = relationship
        assert ProgramServiceProposalV3.model_validate(value).operator_relationship == relationship
    with pytest.raises(ValueError):
        value = _proposal().model_dump(mode="python")
        value["operator_relationship"] = "authoritative"
        ProgramServiceProposalV3.model_validate(value)


def test_v3_subject_evidence_requires_supporting_locator():
    assert _proposal().evidence[0].role == "supporting"
    with pytest.raises(ValueError, match="supporting subject evidence"):
        _proposal(evidence=(_locator(role="context", quote=None),))
    with pytest.raises(ValueError, match="supporting subject evidence"):
        _proposal(evidence=(_locator(role="competing"),))


def test_v3_non_unclear_operator_relationships_require_supporting_evidence():
    relationships = (
        "operated_by_subject",
        "jointly_operated_or_partnered",
        "supported_or_hosted_by_subject",
        "externally_operated",
    )
    for relationship in relationships:
        with pytest.raises(ValueError, match="supporting relationship evidence"):
            _proposal(operator_relationship=relationship, operator_relationship_evidence=())
    unclear = _proposal(operator_relationship="unclear", operator_relationship_evidence=())
    assert unclear.operator_relationship_evidence == ()


def test_v3_operator_relationship_quote_is_bound_and_exact():
    locator = _locator(evidence_id="evidence:operator", quote="Operated by the subject")
    proposal = _proposal(operator_relationship_evidence=(locator,))
    output = ProgramServiceDiscoveryOutputV3(proposals=(proposal,))
    assert validate_v3_evidence_quotes(
        output,
        {"evidence:1": "Named service text", "evidence:operator": "Operated by the subject."},
    ) is output
    with pytest.raises(ValueError, match="verbatim contiguous"):
        validate_v3_evidence_quotes(output, {"evidence:1": "Named service text", "evidence:operator": "Different text"})
    wrong_id = _proposal(operator_relationship_evidence=(_locator(evidence_id="evidence:wrong", quote="Operated by the subject"),))
    with pytest.raises(ValueError, match="not supplied"):
        validate_v3_evidence_quotes(ProgramServiceDiscoveryOutputV3(proposals=(wrong_id,)), {"evidence:operator": "Operated by the subject."})


def test_v3_prompt_contains_contract_principles_and_no_case_examples():
    for phrase in (
        "operator relationship",
        "linked partner's program is not automatically",
        "generic donation or payment machinery",
        "parent_proposal_key",
        "verbatim contiguous excerpts",
        "Current availability is separate",
        "Do not use lexical heuristics",
        "Non-unclear operator relationships require supporting evidence for the operator/relationship proposition.",
    ):
        assert phrase in DISCOVERY_PROMPT_V3
    assert "Fred Hollows" not in DISCOVERY_PROMPT_V3


def test_quote_validation_does_not_infer_semantics():
    output = ProgramServiceDiscoveryOutputV3(proposals=(_proposal(),))
    # A lexical hit is accepted only as an exact locator; absence is rejected.
    validate_v3_evidence_quotes(output, {"evidence:1": "Named service text"})


def test_v3_is_not_dispatchable_and_cannot_trigger_a_provider_call():
    task = SimpleNamespace(task_schema=TASK_SCHEMA_V3, output_schema=DISCOVERY_OUTPUT_SCHEMA_V3)
    with pytest.raises(ValueError, match="not enabled"):
        _parse_discovery_output(task, "{}")


def test_v3_executor_rejects_before_provider_or_durable_side_effect():
    task = SimpleNamespace(task_schema=TASK_SCHEMA_V3, output_schema=DISCOVERY_OUTPUT_SCHEMA_V3)

    class NoSideEffects:
        def __getattr__(self, name):
            raise AssertionError(f"unexpected catalog side effect: {name}")

    with pytest.raises(ValueError, match="not enabled"):
        execute_native_discovery(
            NoSideEffects(),
            task=task,
            evidence_content={},
            cohort_id="cohort",
            run_id="run",
            reservation_id="reservation",
            authorization_scope_hash="scope",
            reservation_aud=Decimal("1"),
            pricing_snapshot_id="pricing",
            fx_snapshot_id="fx",
            fx_usd_aud=Decimal("1"),
            runtime_root=".",
        )
