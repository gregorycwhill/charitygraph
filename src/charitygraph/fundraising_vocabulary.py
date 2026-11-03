"""Candidate, faceted fundraising vocabulary; it is not an assignment engine.

The values here name stable CharityGraph facets.  Source-native labels and
external schemes remain separately represented in ``SOURCE_SCHEMES`` and
``CROSSWALK``.  This module deliberately contains no prose matching rules.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


FacetName = Literal[
    "strategy_program", "solicitation_mechanism", "communication_channel",
    "setting_placement", "resource_sought", "commitment_pattern",
    "payment_transfer_instrument", "donor_relationship_stage",
    "delivery_party", "compensation", "destination_restriction", "digital_distribution",
    "donor_funder_class",
]
MappingPredicate = Literal[
    "exact_match", "close_match", "broader_match", "narrower_match",
    "related_match", "no_match",
]
SchemeDisposition = Literal["incorporated", "mapped", "reference_only", "unresolved"]


class FacetTerm(_Strict):
    term_id: str = Field(pattern=r"^fundraising\.[a-z0-9_]+$")
    facet: FacetName
    label: str
    definition: str
    exclusions: tuple[str, ...] = ()


class SourceScheme(_Strict):
    scheme_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]*$")
    name: str
    owner: str
    version_or_date: str
    role: str
    disposition: SchemeDisposition
    rationale: str


class CrosswalkEntry(_Strict):
    scheme_id: str
    source_term: str
    native_term_id: str | None = None
    predicate: MappingPredicate
    rationale: str
    unresolved_note: str | None = None

    @model_validator(mode="after")
    def mapping_has_consistent_target(self):
        if self.predicate == "no_match":
            if self.native_term_id is not None:
                raise ValueError("no_match must not name a native term")
            if not self.unresolved_note:
                raise ValueError("no_match requires an unresolved note")
        elif self.native_term_id is None:
            raise ValueError("a non-no_match mapping requires a native term")
        return self


class FundraisingVocabularyV1(_Strict):
    vocabulary_id: Literal["charitygraph-fundraising-v1-candidate"]
    status: Literal["candidate"]
    terms: tuple[FacetTerm, ...]
    source_schemes: tuple[SourceScheme, ...]
    crosswalk: tuple[CrosswalkEntry, ...]

    @model_validator(mode="after")
    def check_integrity(self):
        ids = [term.term_id for term in self.terms]
        if len(ids) != len(set(ids)):
            raise ValueError("term IDs must be unique")
        scheme_ids = [scheme.scheme_id for scheme in self.source_schemes]
        if len(scheme_ids) != len(set(scheme_ids)):
            raise ValueError("scheme IDs must be unique")
        unknown_schemes = {entry.scheme_id for entry in self.crosswalk} - set(scheme_ids)
        unknown_terms = {entry.native_term_id for entry in self.crosswalk if entry.native_term_id} - set(ids)
        if unknown_schemes or unknown_terms:
            raise ValueError(f"unknown crosswalk references: schemes={unknown_schemes}, terms={unknown_terms}")
        return self


TERMS = (
    FacetTerm(term_id="fundraising.regular_giving", facet="strategy_program", label="Regular giving", definition="An organised giving program or practice framed as recurring giving.", exclusions=("Does not itself establish payment instrument or acquisition channel.",)),
    FacetTerm(term_id="fundraising.bequests", facet="strategy_program", label="Bequests", definition="A gifts-in-wills or bequest fundraising program or practice.", exclusions=("Not a donation-revenue classification.",)),
    FacetTerm(term_id="fundraising.major_gifts", facet="strategy_program", label="Major gifts", definition="A major-gifts fundraising program or practice.", exclusions=("Does not set a monetary threshold.",)),
    FacetTerm(term_id="fundraising.workplace_giving", facet="strategy_program", label="Workplace giving", definition="A workplace-giving program or practice.", exclusions=("Does not imply a corporate partnership.",)),
    FacetTerm(term_id="fundraising.grantseeking", facet="strategy_program", label="Grant seeking", definition="Seeking grants or philanthropic funding through a grant process.", exclusions=("A grant award is a funding-source observation, not proof of continuing practice.",)),
    FacetTerm(term_id="fundraising.face_to_face", facet="solicitation_mechanism", label="Face-to-face solicitation", definition="Solicitation conducted through in-person interaction.", exclusions=("Does not establish street, door-to-door, private-site, agency delivery, compensation, regular giving or current use.",)),
    FacetTerm(term_id="fundraising.telephone", facet="solicitation_mechanism", label="Telephone solicitation", definition="Solicitation conducted by telephone.", exclusions=("Does not establish inbound/outbound direction or delivery party.",)),
    FacetTerm(term_id="fundraising.direct_mail", facet="communication_channel", label="Direct mail", definition="Physical addressed or unaddressed mail used for fundraising communication.", exclusions=("Does not establish the response or payment instrument.",)),
    FacetTerm(term_id="fundraising.digital", facet="communication_channel", label="Digital", definition="A digital communication channel used for fundraising.", exclusions=("Does not distinguish paid advertising, email, web or social media without additional evidence.",)),
    FacetTerm(term_id="fundraising.sms", facet="communication_channel", label="SMS", definition="SMS or text-message communication used for fundraising.", exclusions=("Does not establish telephone solicitation, consent, payment instrument or recurring giving.",)),
    FacetTerm(term_id="fundraising.email", facet="communication_channel", label="Email", definition="Email communication used for fundraising.", exclusions=("Does not establish a current campaign, acquisition, paid placement or website donation capability.",)),
    FacetTerm(term_id="fundraising.website_donation", facet="communication_channel", label="Website donation or appeal", definition="A website page expressly asking for or accepting a donation.", exclusions=("A donation page alone does not establish a current campaign, paid digital media, organic distribution, acquisition or organisation-wide fundraising practice.",)),
    FacetTerm(term_id="fundraising.social_media", facet="communication_channel", label="Social media", definition="A social-media communication channel used for fundraising.", exclusions=("Does not establish whether distribution is paid or organic, or whether it is acquisition.",)),
    FacetTerm(term_id="fundraising.search", facet="communication_channel", label="Search", definition="A search-engine communication channel used for fundraising.", exclusions=("Does not establish paid search, organic search, acquisition or a donation transaction.",)),
    FacetTerm(term_id="fundraising.paid_digital", facet="digital_distribution", label="Paid digital distribution", definition="Paid placement or advertising used to distribute fundraising communication.", exclusions=("Does not establish a channel, acquisition, campaign, amount spent or effectiveness.",)),
    FacetTerm(term_id="fundraising.organic_digital", facet="digital_distribution", label="Organic digital distribution", definition="Non-paid distribution of fundraising communication through a digital channel.", exclusions=("Does not establish a channel, acquisition, campaign, reach or effectiveness.",)),
    FacetTerm(term_id="fundraising.peer_to_peer", facet="solicitation_mechanism", label="Peer-to-peer fundraising", definition="Supporters solicit or collect support from their own networks for the beneficiary organisation or campaign.", exclusions=("Not every community event is peer-to-peer.",)),
    FacetTerm(term_id="fundraising.community", facet="strategy_program", label="Community fundraising", definition="A program or practice enabling community-led fundraising.", exclusions=("Does not imply peer-to-peer mechanics.",)),
    FacetTerm(term_id="fundraising.events", facet="solicitation_mechanism", label="Fundraising event", definition="A fundraising activity organised around an event.", exclusions=("Does not state whether proceeds are donations, ticket sales, sponsorship or goods revenue.",)),
    FacetTerm(term_id="fundraising.corporate_partnerships", facet="strategy_program", label="Corporate partnerships", definition="A fundraising practice involving corporate partnership arrangements.", exclusions=("Does not prove workplace giving or sponsorship income.",)),
    FacetTerm(term_id="fundraising.raffles_lotteries", facet="solicitation_mechanism", label="Raffles or lotteries", definition="A raffle, lottery or comparable chance-based fundraising activity.", exclusions=("Accounting treatment and regulatory status are separate matters.",)),
    FacetTerm(term_id="fundraising.retail_goods_collections", facet="solicitation_mechanism", label="Retail or goods collection", definition="A fundraising activity involving retail sales, donated goods or goods collection.", exclusions=("Does not state whether the activity is a shop, collection bin or goods donation.",)),
    FacetTerm(term_id="fundraising.emergency_appeal", facet="strategy_program", label="Emergency appeal", definition="A time-bounded appeal responding to an emergency or crisis.", exclusions=("Does not establish channel, restriction or amount raised.",)),
    FacetTerm(term_id="fundraising.private_site", facet="setting_placement", label="Private site", definition="In-person fundraising placed on privately controlled premises.", exclusions=("Does not establish the type of premises or a delivery party.",)),
    FacetTerm(term_id="fundraising.recurring", facet="commitment_pattern", label="Recurring commitment", definition="A supporter commitment intended to recur.", exclusions=("Does not establish regular-giving program or payment instrument.",)),
    FacetTerm(term_id="fundraising.direct_debit", facet="payment_transfer_instrument", label="Direct debit", definition="A direct-debit payment or transfer instrument.", exclusions=("Does not establish a recurring commitment.",)),
    FacetTerm(term_id="fundraising.acquisition", facet="donor_relationship_stage", label="Acquisition", definition="Solicitation directed to acquiring a donor or supporter relationship.", exclusions=("Does not establish retention, value or effectiveness.",)),
    FacetTerm(term_id="fundraising.external_agency", facet="delivery_party", label="External agency", definition="Delivery by an external fundraising agency or provider.", exclusions=("Does not establish compensation or an ongoing relationship.",)),
)

SOURCE_SCHEMES = (
    SourceScheme(scheme_id="pfra_f2f", name="PFRA face-to-face vocabulary", owner="Public Fundraising Regulatory Association", version_or_date="undated public materials; research recorded 2026-10", role="Domain evidence and source-native face-to-face terminology", disposition="mapped", rationale="Strong domain evidence for PFRA-scoped F2F claims, not a complete fundraising taxonomy."),
    SourceScheme(scheme_id="fia_awards", name="FIA awards categories", owner="Fundraising Institute Australia / Fundraising & Philanthropy Australia", version_or_date="award-year specific", role="Source-native award and campaign categories", disposition="reference_only", rationale="Award categories describe recognition records; they are not CharityGraph performance ratings or a general taxonomy."),
    SourceScheme(scheme_id="uk_fundraising_regulator", name="UK Fundraising Regulator guidance", owner="Fundraising Regulator", version_or_date="guidance version varies", role="Completeness and practice-reference vocabulary", disposition="reference_only", rationale="Useful comparative guidance, but Australian scope and terminology are not assumed equivalent."),
    SourceScheme(scheme_id="acnc_ais", name="ACNC Annual Information Statement finance terms", owner="Australian Charities and Not-for-profits Commission", version_or_date="AIS reporting year/profile specific", role="Source-reported regulatory finance vocabulary", disposition="reference_only", rationale="Finance labels remain source-native and are not method or campaign assignments."),
    SourceScheme(scheme_id="nscoa", name="National Standard Chart of Accounts", owner="Australian not-for-profit sector standard", version_or_date="release/profile specific", role="Financial concept normalisation reference", disposition="reference_only", rationale="Normalises accounting concepts, not fundraising channels or causality."),
    SourceScheme(scheme_id="donor_republic_funraisin", name="Donor Republic / Funraisin P2P benchmark terms", owner="Donor Republic and Funraisin", version_or_date="benchmark-year specific", role="Source-native P2P/event benchmark vocabulary", disposition="mapped", rationale="Useful campaign and P2P terms; reported amounts retain source metric definitions."),
)

CROSSWALK = (
    CrosswalkEntry(scheme_id="pfra_f2f", source_term="face-to-face fundraising", native_term_id="fundraising.face_to_face", predicate="close_match", rationale="Both name in-person solicitation; native facets deliberately leave setting, party and commitment unasserted."),
    CrosswalkEntry(scheme_id="pfra_f2f", source_term="donor recruited", native_term_id="fundraising.acquisition", predicate="related_match", rationale="Recruitment supports an acquisition-stage reading when the source asserts it; it is not itself a channel or payment term."),
    CrosswalkEntry(scheme_id="fia_awards", source_term="award winner/finalist", predicate="no_match", rationale="Recognition is source-native contextual evidence, not a fundraising-method concept.", unresolved_note="May be represented as award/recognition evidence under a separately governed context model."),
    CrosswalkEntry(scheme_id="uk_fundraising_regulator", source_term="fundraising method", predicate="no_match", rationale="The generic label combines different semantic axes in guidance.", unresolved_note="Map only individual, definition-supported source terms in a future version."),
    CrosswalkEntry(scheme_id="acnc_ais", source_term="donations and bequests", predicate="no_match", rationale="This is a reported finance/income term, not evidence of a fundraising practice or generated revenue.", unresolved_note="Preserve as source-native finance evidence."),
    CrosswalkEntry(scheme_id="nscoa", source_term="fundraising expense", predicate="no_match", rationale="Expense is a financial measurement concept, not an allocation to method or campaign.", unresolved_note="Use the governed financial measurement model with scope and attribution bounds."),
    CrosswalkEntry(scheme_id="donor_republic_funraisin", source_term="peer-to-peer event", native_term_id="fundraising.peer_to_peer", predicate="broader_match", rationale="The source compound includes event context; native P2P and event facets can be independently asserted when evidence supports each."),
)

FUNDRAISING_VOCABULARY_V1 = FundraisingVocabularyV1(
    vocabulary_id="charitygraph-fundraising-v1-candidate", status="candidate",
    terms=TERMS, source_schemes=SOURCE_SCHEMES, crosswalk=CROSSWALK,
)


def machine_representation() -> dict[str, object]:
    """Return a JSON-safe candidate artifact for controlled review, never publication."""
    return FUNDRAISING_VOCABULARY_V1.model_dump(mode="json")
