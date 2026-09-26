"""Narrow, non-executing implementation of decision CG-S0-PO-2026-09-22.

These predicates deliberately make no network or provider calls.  They are the
shared policy seam used by the S0 bridge; callers still need the existing
durable rights, reservation, packet and exactly-once gates.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from urllib.parse import urlsplit

from charitygraph.scale_s0 import ScalePreflightError


DECISION_ID = "CG-S0-PO-2026-09-22"
ATTESTATION_WINDOW = timedelta(minutes=60)
MAX_LOCATOR_PROBES_PER_SUBJECT = 5


def concrete_first_party_source_definition_id(*, subject_ref: str, canonical_locator: str,
                                              source_family: str = "official_first_party_web") -> str:
    """Return the immutable S0 concrete-source identity for a first-party URL."""
    if not subject_ref or not canonical_locator or not source_family:
        raise ScalePreflightError("first-party source identity requires subject ABN and canonical locator")
    material = f"{source_family}\0{subject_ref}\0{canonical_locator}".encode("utf-8")
    return "srcdef:" + sha256(material).hexdigest()


def acnc_ais_local_use_permitted(*, publisher: str, exact_resource_id: str,
                                 content_hash: str, licence: str | None) -> bool:
    """A2's local-only boundary.  It never grants provider transmission."""
    official = publisher.strip().lower() in {"acnc", "acnc/data.gov.au", "data.gov.au/acnc"}
    licence_ok = licence is None or licence.strip() == "" or licence.strip().upper() == "NOTSPECIFIED" or licence.strip().lower().startswith(("cc-by", "creative commons"))
    return official and bool(exact_resource_id) and len(content_hash) == 64 and licence_ok


def acnc_ais_provider_transmission_permitted(*, separate_explicit_authority: bool) -> bool:
    """A2 does not turn a local-use grant into a provider-send grant."""
    return bool(separate_explicit_authority)


@dataclass(frozen=True)
class ProviderAttestationWindow:
    attested_by: str
    observed_at: datetime
    account_project: str
    execution_authority: str
    setting_disabled: bool
    setting_changed_or_suspected: bool = False

    def valid_for(self, *, now: datetime, account_project: str, execution_authority: str,
                  setting_changed_or_suspected: bool = False) -> bool:
        if now.tzinfo is None or self.observed_at.tzinfo is None:
            raise ScalePreflightError("attestation timestamps must be timezone-aware")
        return (self.attested_by == "Greg" and self.setting_disabled and
                not self.setting_changed_or_suspected and not setting_changed_or_suspected and
                self.account_project == account_project and self.execution_authority == execution_authority and
                now.astimezone(timezone.utc) < self.observed_at.astimezone(timezone.utc) + ATTESTATION_WINDOW)


def provider_attestation_valid(attestation: ProviderAttestationWindow | None, **context: object) -> bool:
    return attestation is not None and attestation.valid_for(**context)  # type: ignore[arg-type]


def discovery_signals_coverage(*, mapper_present: bool) -> str:
    """A4: missing implementation is coverage missingness, never semantic absence."""
    return "READY" if mapper_present else "IMPLEMENTATION_COVERAGE_MISSING_NONBLOCKING"


def alternate_locator_permitted(*, subject_ref: str, locator: str, authoritative_relationship: str,
                                probes_used: int, authentication_bypass: bool = False,
                                paywall_bypass: bool = False, tls_validation_bypass: bool = False,
                                anti_bot_circumvention: bool = False) -> bool:
    """A5's bounded resolver decision; technical barriers remain fail-closed."""
    if not subject_ref or probes_used < 0 or probes_used >= MAX_LOCATOR_PROBES_PER_SUBJECT:
        return False
    parsed = urlsplit(locator)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return False
    if authoritative_relationship not in {"acnc_register", "official_navigation", "officially_linked_document_or_subdomain", "s0_permitted_authoritative_registry"}:
        return False
    return not any((authentication_bypass, paywall_bypass, tls_validation_bypass, anti_bot_circumvention))
