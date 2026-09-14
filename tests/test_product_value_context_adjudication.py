from datetime import datetime, timezone

from charitygraph.product_value_context import SUBJECTS
from charitygraph.product_value_context_adjudication import (
    ADJUDICATOR_ID,
    ATOM_SPECS,
    REVIEWER_ID,
    REVIEWER_ROLE,
    _make_coverage,
    _source_candidate_decisions,
)
from charitygraph.product_value_experiment import ExperimentCandidate


def _row(candidate_id, proposition_type, proposition, index):
    candidate = ExperimentCandidate(
        candidate_id=candidate_id,
        candidate_content_sha256=f"{index:064x}",
        subject_id=f"subject:{index}",
        scope_id=f"scope:{index}",
        scope_kind="organisation",
        source_artifact_id=f"srcblob:{index}",
        source_record_id=f"srcrec:{index}",
        representation_sha256="a" * 64,
        retention_decision_id=f"retention:{index}",
        proposition_type=proposition_type,
        proposition=proposition,
        evidence_locator_ids=(f"locator:{index}#/field",),
        source_carrier_role="historical_frozen_regulator_material",
        epistemic_status="first_party_report_carried_by_regulator",
        reviewed_evidence_universe_id="universe:fixture",
        candidate_producer_id="product-value-deterministic-context-v1",
    )
    return {
        **candidate.model_dump(mode="json"),
        "derivation_method": "DETERMINISTIC_STRUCTURED_EXTRACTION",
        "north_star_section_ids": proposition.get("north_star_section_ids", []),
        "mapping_status": "fixture",
        "source_date": "unknown",
        "retrieved_at": "unknown",
        "effective_period": None,
        "subject_label_for_review": "Fixture Charity",
    }


def _approved_inventory_fixture():
    rows = []
    index = 1
    for category, count, typename, section in (
        ("name", 8, "acnc_carried_legal_name", "1"),
        ("abn", 8, "acnc_carried_identifier", "1"),
        ("year", 8, "acnc_source_reporting_year", "1"),
        ("activity", 16, "acnc_carried_activity_field_value", "3"),
        ("program", 46, "acnc_carried_program_record", "3"),
        ("purpose", 24, "acnc_carried_charitable_purpose_field_value", "2"),
    ):
        for ordinal in range(count):
            value = False if category == "purpose" else ("Historical field value" if category != "program" else {"Name": "Program", "ProgramClassification": "Source label", "ProgramClassificationID": "1"})
            rows.append(_row(f"candidate:fixture-{index}", typename, {
                "north_star_section_ids": [section], "source_field_path": f"#/field/{category}/{ordinal}",
                "source_field_value": value,
            }, index))
            index += 1
    for candidate_id, atom_specs in ATOM_SPECS.items():
        source_text = " ".join(segment for spec in atom_specs for segment in spec["source_text_segments"])
        rows.append(_row(candidate_id, "acnc_carried_mixed_purpose_activity_description", {
            "north_star_section_ids": [], "source_field_path": "#/ActivityPersuitPurposesDescription",
            "source_field_value": source_text,
        }, index))
        index += 1
    return rows


def test_approved_118_decisions_reconcile_and_rejected_purpose_values_never_govern():
    rows = _approved_inventory_fixture()
    originals = [(row["candidate_id"], row["candidate_content_sha256"], row["proposition"].copy()) for row in rows]
    decisions, governed, counts = _source_candidate_decisions(rows, datetime(2026, 9, 14, 4, tzinfo=timezone.utc))

    assert counts == {"ACCEPT": 86, "REJECT_MISSINGNESS": 24, "ACCEPT_MINOR_CORRECTION": 8}
    assert len(decisions) == 118
    assert len(governed) == 106
    rejected_ids = {row["candidate_id"] for row in decisions if row["disposition"] == "REJECT_MISSINGNESS"}
    assert len(rejected_ids) == 24
    assert not rejected_ids.intersection(item.candidate_id for item in governed)
    assert sum(len(ATOM_SPECS[candidate_id]) for candidate_id in ATOM_SPECS) == 20
    corrected = [item for item in governed if item.corrected_atom_index is not None]
    assert len(corrected) == 20
    assert all(item.adjudicator_id == ADJUDICATOR_ID and item.reviewer_id == REVIEWER_ID for item in corrected)
    assert all(item.reviewer_role == REVIEWER_ROLE for item in corrected)
    assert len({item.item_id for item in corrected}) == 20
    assert all(item.evidence_locator_ids for item in corrected)
    assert all(item.governed_representation["candidate_lineage"]["source_candidate_id"] == item.candidate_id for item in corrected)
    assert [(row["candidate_id"], row["candidate_content_sha256"], row["proposition"]) for row in rows] == originals


def test_only_literal_false_purpose_flags_match_bulk_reject_mapping():
    rows = _approved_inventory_fixture()
    purpose = next(row for row in rows if row["proposition_type"] == "acnc_carried_charitable_purpose_field_value")
    purpose["proposition"]["source_field_value"] = True
    try:
        _source_candidate_decisions(rows, datetime(2026, 9, 14, 4, tzinfo=timezone.utc))
    except ValueError as error:
        assert "exact false purpose values" in str(error)
    else:
        raise AssertionError("a true purpose value must not be bulk-rejected as missingness")


def test_coverage_contracts_are_field_complete_and_explicitly_run_scoped():
    source_rows = {}
    for index, (abn, (label, _scope_id)) in enumerate(SUBJECTS.items(), start=1):
        subject_id = f"subject:{abn}"
        source_rows[abn] = {
            "acnc_ais_bundle": {
                "subject_id": subject_id,
                "source_record_id": f"srcrec:acnc:{abn}",
                "source_artifact_id": f"srcblob:acnc:{abn}",
                "representation_sha256": "a" * 64,
                "retention_decision_id": f"retention:acnc:{abn}",
                "source_role": "historical_frozen_regulator_material",
            },
            "annual_report": {
                "subject_id": subject_id,
                "source_record_id": f"srcrec:report:{abn}",
                "source_artifact_id": f"srcblob:report:{abn}",
                "representation_sha256": "b" * 64,
                "retention_decision_id": f"retention:report:{abn}",
                "source_role": "financial_report",
            },
        }

    contracts, decisions, items = _make_coverage(source_rows, datetime(2026, 9, 14, 4, tzinfo=timezone.utc))
    assert len(contracts) == 16
    assert len(items) == 105
    assert len(decisions) == 105
    assert all(item.coverage_state == "not_processed" for item in items)
    assert all(item.adjudicator_id == ADJUDICATOR_ID and item.reviewer_role == REVIEWER_ROLE for item in items)
    assert all("not source silence" in item.governed_representation["state_semantics"] for item in items)
    assert all("source_record_id" in source for contract in contracts for source in contract["universe"]["sources"])
    assert not any("not_found_in_reviewed_sources" in item.coverage_state for item in items)
