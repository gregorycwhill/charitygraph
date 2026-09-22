from datetime import datetime, timedelta, timezone

from charitygraph.s0_product_owner_policy import (
    ProviderAttestationWindow, acnc_ais_local_use_permitted, acnc_ais_provider_transmission_permitted,
    alternate_locator_permitted, concrete_first_party_source_definition_id,
    discovery_signals_coverage, provider_attestation_valid,
)

NOW = datetime(2026, 9, 22, 1, tzinfo=timezone.utc)


def test_first_party_concrete_id_is_subject_and_locator_specific_and_repeatable():
    one = concrete_first_party_source_definition_id(subject_abn="28004778081", canonical_locator="https://one.example/a")
    assert one == concrete_first_party_source_definition_id(subject_abn="28004778081", canonical_locator="https://one.example/a")
    assert one != concrete_first_party_source_definition_id(subject_abn="28000030179", canonical_locator="https://one.example/a")
    assert one != concrete_first_party_source_definition_id(subject_abn="28004778081", canonical_locator="https://one.example/b")
    assert one != concrete_first_party_source_definition_id(subject_abn="28004778081", canonical_locator="https://one.example/a", source_family="official_website")


def test_ais_local_use_is_distinct_from_provider_rights():
    for licence in ("CC-BY-4.0", "", "NOTSPECIFIED"):
        assert acnc_ais_local_use_permitted(publisher="ACNC/data.gov.au", exact_resource_id="resource-v1", content_hash="a" * 64, licence=licence)
    assert not acnc_ais_local_use_permitted(publisher="other", exact_resource_id="resource-v1", content_hash="a" * 64, licence="")
    assert not acnc_ais_local_use_permitted(publisher="ACNC", exact_resource_id="", content_hash="a" * 64, licence="")
    assert not acnc_ais_provider_transmission_permitted(separate_explicit_authority=False)
    assert acnc_ais_provider_transmission_permitted(separate_explicit_authority=True)


def test_attestation_window_has_exact_expiry_and_invalidators():
    attestation = ProviderAttestationWindow("Greg", NOW, "account/project", "authority", True)
    assert attestation.valid_for(now=NOW + timedelta(minutes=59, seconds=59), account_project="account/project", execution_authority="authority")
    assert not attestation.valid_for(now=NOW + timedelta(minutes=60), account_project="account/project", execution_authority="authority")
    assert not attestation.valid_for(now=NOW, account_project="other", execution_authority="authority")
    assert not attestation.valid_for(now=NOW, account_project="account/project", execution_authority="other")
    assert not attestation.valid_for(now=NOW, account_project="account/project", execution_authority="authority", setting_changed_or_suspected=True)
    assert not provider_attestation_valid(None, now=NOW, account_project="account/project", execution_authority="authority")


def test_missing_mapper_is_nonblocking_implementation_coverage_missingness():
    assert discovery_signals_coverage(mapper_present=False) == "IMPLEMENTATION_COVERAGE_MISSING_NONBLOCKING"


def test_alternate_locator_is_bounded_and_no_bypass_is_allowed():
    assert alternate_locator_permitted(subject_abn="28004778081", locator="https://sub.example.org/about", authoritative_relationship="official_navigation", probes_used=4)
    assert not alternate_locator_permitted(subject_abn="28004778081", locator="https://other.example.org", authoritative_relationship="", probes_used=0)
    assert not alternate_locator_permitted(subject_abn="28004778081", locator="https://sub.example.org", authoritative_relationship="acnc_register", probes_used=5)
    assert not alternate_locator_permitted(subject_abn="28004778081", locator="https://sub.example.org", authoritative_relationship="acnc_register", probes_used=0, tls_validation_bypass=True)
