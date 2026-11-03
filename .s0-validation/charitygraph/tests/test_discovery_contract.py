import pytest

from charitygraph.contracts import (
    ProgramServiceDiscoveryOutput,
    ProgramServiceProposal,
    SemanticEvidence,
    discovery_schema,
    discovery_schema_hash,
)


def evidence(evidence_id):
    return SemanticEvidence(evidence_id=evidence_id, role="supporting")


def test_discovery_contract_allows_multiple_typed_proposals_and_zero():
    empty = ProgramServiceDiscoveryOutput(proposals=())
    assert empty.proposals == ()
    output = ProgramServiceDiscoveryOutput(proposals=(
        ProgramServiceProposal(proposal_key="p1", label="Water service", disposition="service", durable=True, evidence=(evidence("evidence:" + "a" * 32),), rationale="Direct evidence", confidence="high"),
        ProgramServiceProposal(proposal_key="p2", label="Annual appeal", disposition="campaign", durable=False, evidence=(evidence("evidence:" + "b" * 32),), rationale="Campaign evidence", confidence="medium"),
    ))
    assert [item.disposition for item in output.proposals] == ["service", "campaign"]


def test_discovery_rejects_duplicate_proposal_keys():
    item = ProgramServiceProposal(proposal_key="same", label="x", disposition="program", durable=True, evidence=(evidence("evidence:" + "a" * 32),), rationale="r")
    with pytest.raises(ValueError):
        ProgramServiceDiscoveryOutput(proposals=(item, item))


def test_discovery_schema_is_strict_and_evidence_enum_is_bound():
    ids = ("evidence:" + "a" * 32, "evidence:" + "b" * 32)
    schema = discovery_schema(ids)
    assert schema["additionalProperties"] is False
    assert schema["required"] == ["proposals"]
    proposal = schema["properties"]["proposals"]["items"]
    assert proposal["additionalProperties"] is False
    evidence_schema = proposal["properties"]["evidence"]["items"]
    assert evidence_schema["additionalProperties"] is False
    assert evidence_schema["properties"]["evidence_id"]["enum"] == list(ids)
    assert set(proposal["required"]) == set(proposal["properties"])
    assert discovery_schema_hash(ids) != discovery_schema_hash((ids[0],))
