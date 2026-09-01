import pytest
from pydantic import ValidationError

from charitygraph.compact_knowledge import CompactKnowledgeOutput, CompactAtom


def test_compact_atom_is_card_blind_and_evidence_grounded():
    atom = CompactAtom(
        proposition="A service is described.", scope_kind="subject", scope_label=None,
        temporal_kind="current", temporal_value=None, epistemic_status="supported",
        evidence=({"source": "S001", "locator": "L0001", "role": "supporting"},),
    )
    assert atom.proposition
    assert not hasattr(atom, "section_id")


def test_compact_atom_requires_supporting_evidence():
    with pytest.raises(ValidationError):
        CompactAtom(
            proposition="Unanchored", scope_kind="uncertain", temporal_kind="undated",
            epistemic_status="supported", evidence=({"source": "S001", "locator": "L0001", "role": "context"},),
        )


def test_output_contains_only_atoms():
    result = CompactKnowledgeOutput(atoms=())
    assert result.atoms == ()
