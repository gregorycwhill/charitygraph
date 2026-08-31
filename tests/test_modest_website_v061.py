"""Mechanical v0.6.1 projection and blind-view invariants (no providers)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
from scripts.run_modest_website_luna_classie_v061 import project_external_taxonomy, projected_packet


def test_external_taxonomy_projection_preserves_semantic_program_content() -> None:
    value = {"Programs": [{"Name": "Funding", "ProgramClassification": "x", "ProgramClassie": [{"classie_id": "c1"}], "ProgramLocations": [{"Name": "WA"}]}], "ActivityOperating": True}
    clean, removed = project_external_taxonomy(value)
    assert clean["Programs"][0]["Name"] == "Funding"
    assert clean["Programs"][0]["ProgramLocations"][0]["Name"] == "WA"
    assert clean["ActivityOperating"] is True
    assert "ProgramClassification" not in clean["Programs"][0]
    assert "ProgramClassie" not in clean["Programs"][0]
    assert len(removed) == 2


def test_projected_packet_rebuilds_structured_locators_and_collects_reference_ids() -> None:
    packet = {"sources": [{"source_key": "S001", "source_family": "acnc_register", "locators": [{"locator": "L0001", "text": '{'}, {"locator": "L0002", "text": '  "data": {"Programs": [{"ProgramClassie": [{"classie_id": "c1", "selected": true}], "Name": "P"}]}'}, {"locator": "L0003", "text": "}"}]}]}
    projected, removed, ids = projected_packet(packet)
    text = "\n".join(item["text"] for item in projected["sources"][0]["locators"])
    assert "ProgramClassie" not in text
    assert ids == {"c1"}
    assert removed
    assert projected["sources"][0]["locators"][0]["locator"] == "L0001"
