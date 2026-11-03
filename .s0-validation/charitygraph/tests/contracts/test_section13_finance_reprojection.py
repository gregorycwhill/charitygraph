from datetime import datetime, timezone
from decimal import Decimal

import pytest

from charitygraph.contracts.common import ArtifactRef, ProducerRef, SchemaRef
from charitygraph.contracts.ids import deterministic_id
from charitygraph.contracts.knowledge import ObservationTime, ScopeRecord, SubjectRecord
from charitygraph.integrated_card import IntegratedGraph, NORTH_STAR_PROJECTION_V0_1, NORTH_STAR_PROJECTION_VNEXT, project_subject
from charitygraph.models import MoneyObservation
from charitygraph.section13_finance_reprojection import (
    Section13FinanceInput, project_section13_finance_observation, section13_finance_card_evidence,
    section13_finance_missingness,
)

NOW = datetime(2026, 9, 16, tzinfo=timezone.utc)
PRODUCER = ProducerRef(kind="code", producer_id="section13-fixture", version="1")
SUBJECT = "subject:" + "1" * 32
SOURCE = "srcrec:" + "2" * 64
SCOPE = "scope:" + "3" * 32


def money(amount="835006", scale="1000", currency="AUD"):
    return MoneyObservation(source_amount=Decimal(amount), source_currency=currency, source_unit_scale=Decimal(scale),
        normalised_amount=Decimal(amount) * Decimal(scale), normalised_currency=currency, source_unit_label="$'000")


def item(predicate="statement_row_observed", **updates):
    values = dict(predicate=predicate, subject_id=SUBJECT, scope_id=SCOPE, scope_kind="organisation", reporting_scope="subject",
        attribution_method="direct_subject_report", financial_record_id="financial:EJA-FY25", coverage_state="supported",
        claim_basis="source_fact", source_role="supporting", evidence_locator_ids=("locator:page-12",), source_record_ids=(SOURCE,),
        lineage_ids=("artifact:row",), observation_time=ObservationTime(observed_at=NOW), statement_type="profit_and_loss",
        statement_identity="Statement of profit or loss", source_row_label="Government grants", money=money())
    values.update(updates)
    return Section13FinanceInput(**values)


def observation(value, suffix="4"):
    return project_section13_finance_observation(value, record_id="observation:" + suffix * 64, created_at=NOW, producer=PRODUCER)


def subject():
    return SubjectRecord(record_id=deterministic_id("subjectrecord:", {"subject": SUBJECT}), subject_id=SUBJECT,
        subject_kind="organisation", lifecycle_status="active", display_name="Synthetic C4 architecture fixture",
        external_identifiers=({"scheme": "ABN", "value": "12345678901"},),
        identity_authority_refs=(ArtifactRef(artifact_id=SOURCE, content_hash="a" * 64,
            schema=SchemaRef(schema_id="urn:charitygraph:builder:schema:source-record:1.0", schema_version="1.0")),),
        identity_policy_id="test", created_at=NOW, producer=PRODUCER)


def graph(value):
    observed = observation(value)
    scope_kind = "other" if value.scope_kind == "operating_division" else value.scope_kind
    scope = ScopeRecord(record_id=value.scope_id, subject_id=SUBJECT, scope_kind=scope_kind, created_at=NOW, producer=PRODUCER)
    return observed, IntegratedGraph(subjects=(subject(),), scopes=(scope,), observations=(observed,),
        evidence=(section13_finance_card_evidence(value, observed),))


def sections(graph_value, contract):
    return {row["section_id"]: row for row in project_subject(graph_value, SUBJECT, projection_contract=contract)["sections"]}


def test_source_native_row_is_v02_section13_only_and_preserves_scope_currency_scale_and_comparative():
    value = item(comparative_money=money("852577"))
    observed, graph_value = graph(value)
    active, historical = sections(graph_value, NORTH_STAR_PROJECTION_VNEXT), sections(graph_value, NORTH_STAR_PROJECTION_V0_1)
    assert active[13]["observation_ids"] == [observed.record_id]
    assert all(observed.record_id not in row["observation_ids"] for row in historical.values())
    assert observed.value["money"]["source_unit_scale"] == "1000"
    assert observed.value["comparative_money"]["source_amount"] == "852577"
    assert observed.value["reporting_scope"] == "subject"
    assert section13_finance_card_evidence(value, observed).section_ids == (13,)


@pytest.mark.parametrize("stage", ["award", "commitment", "payment", "receipt", "revenue_recognition", "expenditure_or_use", "refund_or_return"])
def test_resource_flow_stages_are_explicit_and_separate(stage):
    value = item("resource_flow_stage_observed", statement_type=None, statement_identity=None, source_row_label=None, money=None,
        stage=stage, detail="source text explicitly labels this accounting or cash-flow stage")
    assert observation(value).value["stage"] == stage


def test_commitment_receipt_expenditure_and_return_cannot_be_other_stages_or_liability_revenue_shortcuts():
    for stage in ("commitment", "receipt", "expenditure_or_use", "refund_or_return"):
        value = item("resource_flow_stage_observed", statement_type=None, statement_identity=None, source_row_label=None, money=None,
            stage=stage, detail="retained counterexample")
        assert observation(value).predicate.endswith("resource_flow_stage_observed")
    with pytest.raises(ValueError, match="stage is limited"):
        item(stage="receipt")
    with pytest.raises(Exception):
        item("liability_observed")


def test_restriction_and_grant_category_cannot_create_dependency_or_named_funder():
    restriction = item("restriction_or_reserve_observed", statement_type=None, statement_identity=None, source_row_label=None, money=None,
        detail="Specific purpose fund transfer reported in equity")
    assert observation(restriction).value["section13_predicate"] == "restriction_or_reserve_observed"
    with pytest.raises(Exception):
        item("dependency_observed")
    with pytest.raises(Exception):
        item(named_funder="National Blood Authority")


def test_operating_division_scope_cannot_become_organisation_scope():
    division = item(scope_kind="operating_division", reporting_scope="organisation_group", attribution_method="division_reported")
    assert observation(division).value["scope_kind"] == "operating_division"
    with pytest.raises(ValueError, match="operating-division finance"):
        item(scope_kind="operating_division", attribution_method="direct_subject_report")
    with pytest.raises(ValueError, match="requires an operating-division"):
        item(attribution_method="division_reported")


def test_deterministic_calculation_is_not_source_native_and_reconciliation_statuses_remain_distinct():
    derived = item("derived_financial_calculation", statement_type=None, statement_identity=None, source_row_label=None, money=None,
        claim_basis="deterministic_calculation", value=Decimal("0.787897"), calculation_method="reported_category_divided_by_reported_total",
        numerator_observation_id="observation:" + "5" * 64, denominator_observation_id="observation:" + "6" * 64)
    assert observation(derived).value["claim_basis"] == "deterministic_calculation"
    for status in ("non_comparable", "precision_consistent"):
        reconciled = item("reconciliation_outcome_observed", statement_type=None, statement_identity=None, source_row_label=None, money=None,
            detail="retained reconciliation finding", reconciliation_status=status, related_observation_ids=("observation:" + "7" * 64, "observation:" + "8" * 64))
        assert observation(reconciled).value["reconciliation_status"] == status


def test_currency_translated_comparative_is_not_an_ordinary_comparative_or_correction():
    transformed = item("comparative_transformation_observed", statement_type=None, statement_identity=None, source_row_label=None, money=None,
        detail="2024 AUD comparative translated to USD using source-described basis", comparative_transformation="currency_translated_comparative")
    assert observation(transformed).value["comparative_transformation"] == "currency_translated_comparative"
    with pytest.raises(Exception):
        item("correction_observed")


def test_assurance_is_explicit_and_annual_report_presence_cannot_supply_it():
    assurance = item("assurance_observed", statement_type=None, statement_identity=None, source_row_label=None, money=None,
        assurance_kind="independent_auditor_opinion", detail="Independent auditor report states its opinion")
    assert observation(assurance).value["assurance_kind"] == "independent_auditor_opinion"
    with pytest.raises(ValueError, match="assurance requires"):
        item("assurance_observed", statement_type=None, statement_identity=None, source_row_label=None, money=None)


def test_honest_missingness_never_becomes_zero_or_absence():
    for state, expected in (("not_processed", "NOT_PROCESSED"), ("processing_failed", "PROCESSING_FAILED"), ("not_attempted", "NOT_ATTEMPTED")):
        assert section13_finance_missingness(subject_id=SUBJECT, coverage_state=state).state == expected
    for state in ("asserted_none", "observed_absent"):
        with pytest.raises(ValueError):
            section13_finance_missingness(subject_id=SUBJECT, coverage_state=state)
        with pytest.raises(ValueError, match="absence claims"):
            item(coverage_state=state)
