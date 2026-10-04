import pytest
from charitygraph.north_star_projection import NorthStarLensOutput, NorthStarLensOutputVNext

def test_assignment_allows_zero_or_multiple_sections():
    result = NorthStarLensOutput.model_validate({"assignments":[{"observation_key":"O001","section_ids":[]},{"observation_key":"O002","section_ids":[1,3],"note":None}]})
    assert result.assignments[0].section_ids == ()
    assert result.assignments[1].section_ids == (1,3)

def test_assignment_rejects_invalid_or_duplicate_sections():
    with pytest.raises(ValueError):
        NorthStarLensOutput.model_validate({"assignments":[{"observation_key":"O001","section_ids":[21],"note":None}]})
    with pytest.raises(ValueError):
        NorthStarLensOutput.model_validate({"assignments":[{"observation_key":"O001","section_ids":[1,1],"note":None}]})


@pytest.mark.parametrize("model,payload", [
    (NorthStarLensOutput, {"assignments": [
        {"observation_key": "O001", "section_ids": [1], "note": None},
        {"observation_key": "O001", "section_ids": [2], "note": None},
    ]}),
    (NorthStarLensOutputVNext, {"projection_contract_id": "north-star-v0.2", "assignments": [
        {"observation_key": "O001", "section_ids": [1], "note": None},
        {"observation_key": "O001", "section_ids": [2], "note": None},
    ]}),
])
def test_lens_rejects_duplicate_observation_assignments(model, payload):
    with pytest.raises(ValueError, match="one lens assignment"):
        model.model_validate(payload)
