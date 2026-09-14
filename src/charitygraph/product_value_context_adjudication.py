"""Apply Greg's fixed private adjudication decision to the locked I/P/A inventory."""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .phase6_semantic_contracts import (
    Phase6Scope,
    ReviewedEvidenceCoverage,
    ReviewedEvidenceCoverageEvidence,
    ReviewedEvidenceCoverageItem,
    ReviewedEvidenceSource,
    ReviewedEvidenceUniverse,
)
from .product_value_experiment import (
    ExperimentCandidate,
    ExperimentGovernedItem,
    PropositionAdjudication,
    create_experiment_governed_items,
    project_experiment_items,
)
from .product_value_context import BASELINE_LOCK_SHA256, SUBJECTS


INVENTORY_SHA256 = "bbeac4843bce4714b778c8ec90c678528990b906d23b5a680a1657224e5b666b"
REQUEST_MANIFEST_SHA256 = "779bdbdf74c5fd5d1ea12ef708cbd52b8d87d6f60dbd6d927194f360bd931241"
REQUEST_BODY_SHA256 = {
    "28004778081.json": "a0b8d76ce6efc5e80b6e69f8c1edab3353ca008d55ac3718de16f8f5faf5390c",
    "50169561394.json": "5b5495f9a7ff13137ad0c6ef4d9fe1235abfaeb2688ab317aec3b5c1a2f3bd55",
    "61002643852.json": "97afa4666c391c28dde7e582e7bd4dba457542f355a3503d187535edab036959",
    "65159324697.json": "cd42a757a27963ea94323d2cf2961afd3b0db921cd70102f06f63473deb5c351",
    "78053639115.json": "6cdfb623940052202b088ef5ecd7503be875f22a5c7897bacc29b46b4c40060e",
}
ADJUDICATOR_ID = "human:Greg"
ADJUDICATOR_CLASS = "HUMAN_ADJUDICATOR"
ADJUDICATOR_ROLE = "independent_human_proposition_adjudicator"
REVIEWER_ID = "ChatGPT"
REVIEWER_ROLE = "MODEL_ASSISTED_REVIEWER"
OUTCOMES_FIELDS = (
    "observed_outcome_measure", "evaluation_assessment", "evaluator_identity", "method",
    "comparator_counterfactual", "limitations",
)
COMMITMENTS_FIELDS = (
    "implementation_evidence", "independent_implementation_verification",
    "implementation_outcome", "affirmative_non_implementation_evidence",
)


ATOM_SPECS: dict[str, tuple[dict[str, Any], ...]] = {
    "candidate:context-v1-062183c75bbae1c694f56f3c52bc9dfe": (
        {
            "section": "3", "type": "source_reported_activity",
            "statement": "Australian sponsors and donors provide funds for World Vision field offices to run relief and development projects, with technical support from the World Vision Australia team.",
            "source_text_segments": ("Australian sponsors and donors provide funds for World Vision field offices to run relief and development projects in their countries, with technical support from the World Vision Australia team.",),
        },
        {
            "section": "3", "type": "source_reported_activity",
            "statement": "For projects in Australia, World Vision Australia reports working directly with First Nations communities to run activities, with communities described as driving their own development.",
            "source_text_segments": ("For projects in Australia, we work directly with First Nations communities to run activities and ensure they are the ones driving their own development.",),
        },
    ),
    "candidate:context-v1-10681f39e038f1da485ed47b33410812": (
        {
            "section": "2", "type": "source_stated_purpose",
            "statement": "Bush Heritage Australia describes itself as a not-for-profit conservation organisation focused on buying and managing land to protect important and fragile Australian ecosystems.",
            "source_text_segments": ("Bush Heritage Australia is a not-for-profit conservation organisation focused on buying and managing land for the protection of some of Australia's most important and fragile ecosystems.",),
        },
        {
            "section": "3", "type": "source_reported_activity",
            "statement": "Bush Heritage Australia reports buying and managing conservation land and partnering with Traditional Custodians and other landholders.",
            "source_text_segments": (
                "Bush Heritage Australia is a not-for-profit conservation organisation focused on buying and managing land",
                "we partner with Traditional Custodians and other landholders.",
            ),
        },
    ),
    "candidate:context-v1-05c50edc247f4f68580bd6f7623cebab": (
        {
            "section": "2", "type": "source_stated_purpose",
            "statement": "Australian Red Cross Society states that it exists to reduce human suffering.",
            "source_text_segments": ("Australian Red Cross Society is a volunteer-based organisation that exists to reduce human suffering.",),
        },
        {
            "section": "3", "type": "source_reported_activity",
            "statement": "Australian Red Cross reports work across emergency and disaster services, migration, and community activities and programs.",
            "source_text_segments": (
                "Emergency services and disasters: we help build communities that are strong, resilient and able to anticipate, respond, and recover well from disasters and climate related emergencies.",
                "Migration: we help build fair, welcoming, and inclusive communities where migrants are safe and have their humanitarian needs met.",
                "Community activities and programs: we build connection and resilience through volunteering and responding to the humanitarian needs of local communities.",
            ),
        },
        {
            "section": "3", "type": "source_reported_activity",
            "statement": "Australian Red Cross reports international programs and International Humanitarian Law work, and describes Lifeblood as an operating division.",
            "source_text_segments": (
                "Australian Red Cross Society operates through two operating divisions: Australian Red Cross Humanitarian Services and Australian Red Cross Lifeblood.",
                "International programs: we help build stronger, more resilient international communities with increased capacity to prepare for, anticipate, respond to and recover from crises.",
                "International Humanitarian Law: we better humanitarian outcomes for people and communities impacted by armed conflicts.",
            ),
        },
    ),
    "candidate:context-v1-b8891b53dba54e423709931a207da0d2": (
        {
            "section": "2", "type": "source_stated_purpose",
            "statement": "Greenpeace Australia Pacific states a mission to secure the Earth's ability to nurture and sustain life in its diversity.",
            "source_text_segments": ("Greenpeace Australia Pacific's mission is to secure the ability of the earth to nurture and sustain life in all of its magnificent diversity.",),
        },
        {
            "section": "2", "type": "source_stated_aim",
            "statement": "Greenpeace Australia Pacific states aims to keep climate change below 1.5 degrees by the end of this century and secure conditions for biodiversity to flourish.",
            "source_text_segments": ("Specifically Greenpeace seeks to keep climate change below 1.5 degrees by the end of this century and to secure conditions for biodiversity to flourish.",),
        },
        {
            "section": "3", "type": "source_reported_activity",
            "statement": "Greenpeace Australia Pacific reports work concerning climate change, wildlife depletion, and threats to regions including the Pilbara coast and Pacific islands.",
            "source_text_segments": ("We work on the most urgent environmental issues of our time, with priorities including climate change, the depletion of marine and terrestrial wildlife, and threats to iconic regions including the Pilbara coast and islands across the Pacific.",),
        },
    ),
    "candidate:context-v1-60412acec0982cb52063e2a30ce7b917": (
        {
            "section": "2", "type": "source_stated_purpose",
            "statement": "The Sunrise Project states a mission to scale social movements to drive the transition from fossil fuels to renewable energy as fast as possible.",
            "source_text_segments": ("The Sunrise Project Australia's mission is to scale social movements to drive the transition from fossil fuels to renewable energy as fast as possible.",),
        },
        {
            "section": "3", "type": "source_reported_activity",
            "statement": "The Sunrise Project reports re-granting funds to a network of independent organisations for research, education, advocacy, and community capacity building.",
            "source_text_segments": (
                "This year, we pursued that mission primarily by re-granting funds to a diverse network of independent organisations, empowering them to lead research, education, advocacy and community capacity building",
            ),
        },
        {
            "section": "3", "type": "source_reported_activity",
            "statement": "The Sunrise Project reports work opposing coal and gas expansion, accelerating clean energy, supporting industry decarbonisation and renewable energy, engaging the public, and building civil-society connections.",
            "source_text_segments": (
                "We worked to prevent the expansion of coal and gas mining",
                "and to accelerate the transition to clean energy in line with the goals of the Paris Climate Agreement.",
                "We also supported efforts  for Australian industry to decarbonise and scale renewable energy, educated and engaged Australians in positive climate action, and built civil society connections to support the energy transition across the Asia-Pacific.",
            ),
        },
    ),
    "candidate:context-v1-cf0fcac82680e7cb7b8f48b896372719": (
        {
            "section": "2", "type": "source_stated_purpose",
            "statement": "St George Community Housing reports a public charitable object including relief of poverty, distress, or helplessness through sustainable, safe, affordable housing for people in housing need.",
            "source_text_segments": ("We pursue our public charitable object of providing relief against poverty, distress and helplessness by providing sustainable, safe, affordable and sensitively managed housing for people in housing need and experiencing difficulties securing and maintaining appropriate housing.",),
        },
        {
            "section": "2", "type": "source_stated_purpose",
            "statement": "St George Community Housing states a purpose to collaboratively shape and provide great places and connect people to opportunity to improve quality of life.",
            "source_text_segments": ("we are guided by our purpose to collaboratively shape and provide great places and connect people to opportunity to improve quality of life.",),
        },
        {
            "section": "3", "type": "source_reported_activity",
            "statement": "St George Community Housing reports providing social and affordable housing and tenant initiatives concerning training, education, employment, and community engagement.",
            "source_text_segments": (
                "Our core activity is to provide social housing and affordable housing.",
                "we provide a range of initiatives to improve the lives of tenants such as training, education, employment and community engagement opportunities",
            ),
        },
    ),
    "candidate:context-v1-73450b62d5567e764485cba4688b596c": (
        {
            "section": "2", "type": "source_stated_purpose",
            "statement": "The Royal Flying Doctor Service of Australia (Queensland Section) states it is dedicated to providing healthcare to people living, travelling, or working in rural, regional, and remote Queensland.",
            "source_text_segments": ("The Royal Flying Doctor Service of Australia (Queensland Section) is dedicated to providing vital health care to everyone living, travelling, or working in rural, regional and remote Queensland.",),
        },
        {
            "section": "3", "type": "source_reported_activity_and_development_aim",
            "statement": "RFDS Queensland reports a key aim to diversify and expand its primary healthcare and aeromedical services; this aim does not establish current availability.",
            "source_text_segments": ("The key aim is delivering excellence in health care, whilst also working to diversify and expand its range of primary health care and aeromedical services.",),
        },
    ),
    "candidate:context-v1-7ca929c348a36e96cc11edd092c6cca2": (
        {
            "section": "2", "type": "source_stated_purpose",
            "statement": "The Leukaemia Foundation of Australia states a mission to support people affected by blood and other cancers.",
            "source_text_segments": ("The Leukaemia Foundation of Australia advances its mission to support people affected by blood and other cancers",),
        },
        {
            "section": "3", "type": "source_reported_activity",
            "statement": "The Leukaemia Foundation reports practical, emotional, and financial support, accommodation, transport, research funding, education and support programs, advocacy, and community awareness activities.",
            "source_text_segments": (
                "by providing practical, emotional, and financial assistance to patients and their families.",
                "The Foundation helped achieve this mission by offering free accommodation and transport services for patients undergoing treatment, funding research into new therapies, and delivering education and support programs",
                "The Foundation s advocacy and community awareness initiatives aim to strengthen improved access to care and promote an understanding of blood and related cancers across Australia.",
            ),
        },
    ),
}


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _stable_id(prefix: str, value: Any) -> str:
    return prefix + hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _candidate_from_row(row: dict[str, Any]) -> ExperimentCandidate:
    fields = ExperimentCandidate.model_fields
    return ExperimentCandidate(**{key: row[key] for key in fields if key in row})


def _corrected_representation(candidate: ExperimentCandidate, row: dict[str, Any], spec: dict[str, Any], atom_index: int) -> dict[str, Any]:
    source_value = row["proposition"]["source_field_value"]
    if not isinstance(source_value, str):
        raise ValueError("mixed-description source candidate must retain its exact text")
    if any(segment not in source_value for segment in spec["source_text_segments"]):
        raise ValueError(f"approved human atomization is unsupported by the exact source field for {candidate.candidate_id}")
    locator = candidate.evidence_locator_ids[0]
    return {
        "proposition_type": spec["type"],
        "north_star_section_id": spec["section"],
        "statement": spec["statement"],
        "source_text_segments": list(spec["source_text_segments"]),
        "source_field_path": row["proposition"]["source_field_path"],
        "source_locator_id": locator,
        "source_carrier_role": candidate.source_carrier_role,
        "epistemic_status": "first_party_report_carried_by_regulator",
        "scope": {"scope_id": candidate.scope_id, "scope_kind": candidate.scope_kind},
        "candidate_lineage": {
            "source_candidate_id": candidate.candidate_id,
            "original_candidate_content_sha256": candidate.candidate_content_sha256,
            "corrected_atom_index": atom_index,
        },
        "time_boundary": "Historical/source-reported; no current status or period beyond the exact source fields is asserted.",
        "human_atomization": True,
        "canonical_public": False,
    }


def _source_candidate_decisions(rows: list[dict[str, Any]], adjudicated_at: datetime) -> tuple[list[dict[str, Any]], list[ExperimentGovernedItem], Counter[str]]:
    if len(rows) != 118 or len({row["candidate_id"] for row in rows}) != 118:
        raise ValueError("the locked original candidate inventory must contain exactly 118 unique candidates")
    mixed_rows = {row["candidate_id"]: row for row in rows if row["proposition_type"] == "acnc_carried_mixed_purpose_activity_description"}
    if set(mixed_rows) != set(ATOM_SPECS):
        raise ValueError("the eight approved mixed-candidate identities do not match the frozen inventory")
    dispositions: list[dict[str, Any]] = []
    items: list[ExperimentGovernedItem] = []
    counts: Counter[str] = Counter()
    for row in rows:
        candidate = _candidate_from_row(row)
        if candidate.proposition_type in {
            "acnc_carried_legal_name", "acnc_carried_identifier", "acnc_source_reporting_year",
            "acnc_carried_activity_field_value", "acnc_carried_program_record",
        }:
            disposition = "ACCEPT"
            corrections: tuple[dict[str, Any], ...] = ()
            rationale = "Greg approved exact source-carried deterministic propositions in the specified category. Preserve historical scope, source role, epistemic status, and source value; no current service, capacity, effectiveness, outcome, or causation inference is accepted."
        elif candidate.proposition_type == "acnc_carried_charitable_purpose_field_value":
            if candidate.proposition.get("source_field_value") is not False:
                raise ValueError("approved REJECT_MISSINGNESS mapping applies only to exact false purpose values")
            disposition = "REJECT_MISSINGNESS"
            corrections = ()
            rationale = "Greg rejected this literal false AIS field because it does not establish the substantive North Star proposition that the organisation lacks that charitable purpose. Preserve only in immutable source/candidate lineage; do not project it as a negative Purpose claim or coverage absence."
        elif candidate.proposition_type == "acnc_carried_mixed_purpose_activity_description":
            disposition = "ACCEPT_MINOR_CORRECTION"
            corrections = tuple(
                _corrected_representation(candidate, row, spec, index)
                for index, spec in enumerate(ATOM_SPECS[candidate.candidate_id], start=1)
            )
            rationale = "Greg approved this human atomization of the exact mixed AIS description. Corrected atoms preserve the immutable candidate ID/hash, exact field locator, original source wording segments, organization scope, regulator carrier role, and first-party-report epistemic status. ChatGPT is only the model-assisted reviewer."
        else:
            raise ValueError(f"unmapped source candidate type: {candidate.proposition_type}")

        adjudication_id = _stable_id("adjudication:pvctx:", {"candidate_id": candidate.candidate_id, "hash": candidate.candidate_content_sha256, "decision": disposition})
        adjudication = PropositionAdjudication(
            adjudication_id=adjudication_id,
            candidate_id=candidate.candidate_id,
            candidate_content_sha256=candidate.candidate_content_sha256,
            disposition=disposition,
            adjudicator_id=ADJUDICATOR_ID,
            adjudicator_role=ADJUDICATOR_ROLE,
            adjudicated_at=adjudicated_at,
            adjudication_version="greg-approved-context-adjudication-v1",
            rationale=rationale,
            corrected_governed_representations=corrections,
            independent_of_candidate_producer=True,
            reviewer_id=REVIEWER_ID,
            reviewer_role=REVIEWER_ROLE,
        )
        generated = create_experiment_governed_items(candidate, adjudication)
        if disposition == "ACCEPT" and len(generated) != 1:
            raise ValueError("each approved ACCEPT candidate must yield exactly one governed item")
        if disposition == "REJECT_MISSINGNESS" and generated:
            raise ValueError("rejected purpose flags must not enter the governed namespace")
        if disposition == "ACCEPT_MINOR_CORRECTION" and len(generated) != len(corrections):
            raise ValueError("every approved correction atom must yield one governed item")
        items.extend(generated)
        counts[disposition] += 1
        dispositions.append({
            **adjudication.model_dump(mode="json"),
            "adjudicator_class": ADJUDICATOR_CLASS,
            "reviewer_id": REVIEWER_ID,
            "reviewer_role": REVIEWER_ROLE,
            "generated_item_ids": [item.item_id for item in generated],
            "corrected_atom_count": len(generated) if disposition == "ACCEPT_MINOR_CORRECTION" else 0,
        })
    return dispositions, items, counts


def _coverage_candidate(
    *, abn: str, label: str, scope_id: str, metadata: dict[str, Any], state: str,
    proposition_type: str, section_id: str, question_id: str, rationale: str,
    universe_id: str, source_lineage: list[dict[str, Any]], adjudicated_at: datetime,
) -> tuple[ExperimentCandidate, PropositionAdjudication, ExperimentGovernedItem]:
    proposition = {
        "proposition_type": proposition_type,
        "north_star_section_id": section_id,
        "question_id": question_id,
        "coverage_state": state,
        "rationale": rationale,
        "scope": {"scope_id": scope_id, "scope_kind": "organisation"},
        "reviewed_evidence_universe_id": universe_id,
        "source_lineage": source_lineage,
        "state_semantics": "Run-specific processing status; not source silence, not source unavailability, and not substantive absence.",
        "adjudicator_decision_basis": "Greg's explicit instruction to materialize mechanically justified not_processed states for this fixed universe.",
    }
    identity = {
        "subject_id": metadata["subject_id"], "scope_id": scope_id,
        "source_record_id": metadata["source_record_id"], "representation_sha256": metadata["representation_sha256"],
        "retention_decision_id": metadata["retention_decision_id"], "proposition": proposition,
        "coverage_state": state, "reviewed_evidence_universe_id": universe_id,
    }
    digest = hashlib.sha256(_canonical_bytes(identity)).hexdigest()
    candidate = ExperimentCandidate(
        candidate_id=f"candidate:pvctxcov-{digest[:32]}", candidate_content_sha256=digest,
        subject_id=metadata["subject_id"], scope_id=scope_id, scope_kind="organisation",
        source_artifact_id=metadata["source_artifact_id"], source_record_id=metadata["source_record_id"],
        representation_sha256=metadata["representation_sha256"], retention_decision_id=metadata["retention_decision_id"],
        proposition_type=proposition_type, proposition=proposition,
        evidence_locator_ids=(), source_carrier_role=metadata["source_role"],
        epistemic_status="run_processing_state_not_source_claim",
        reviewed_evidence_universe_id=universe_id, coverage_state=state,
        candidate_producer_id="product-value-deterministic-context-coverage-v1",
    )
    adjudication = PropositionAdjudication(
        adjudication_id=_stable_id("adjudication:pvctxcov:", {"candidate": candidate.candidate_id, "hash": digest}),
        candidate_id=candidate.candidate_id, candidate_content_sha256=digest,
        disposition="ACCEPT", adjudicator_id=ADJUDICATOR_ID, adjudicator_role=ADJUDICATOR_ROLE,
        adjudicated_at=adjudicated_at, adjudication_version="greg-approved-context-coverage-v1",
        rationale=rationale, independent_of_candidate_producer=True,
        reviewer_id=REVIEWER_ID, reviewer_role=REVIEWER_ROLE,
    )
    generated = create_experiment_governed_items(candidate, adjudication)
    if len(generated) != 1 or generated[0].item_kind != "coverage_state":
        raise ValueError("each approved coverage state must yield exactly one governed coverage item")
    item = generated[0]
    return candidate, adjudication, item


def _make_coverage(
    all_sources: dict[str, dict[str, dict[str, Any]]], adjudicated_at: datetime,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[ExperimentGovernedItem]]:
    contracts: list[dict[str, Any]] = []
    adjudications: list[dict[str, Any]] = []
    items: list[ExperimentGovernedItem] = []
    for abn, (label, scope_id) in SUBJECTS.items():
        sources = all_sources[abn]
        aisle = sources["acnc_ais_bundle"]
        report = sources["annual_report"]
        source_ids = (aisle["source_record_id"], report["source_record_id"])
        scope = Phase6Scope(scope_id=scope_id, scope_kind="organisation", scope_label=label)
        family_contracts = []
        for family, fields in (("outcomes", OUTCOMES_FIELDS), ("commitments", COMMITMENTS_FIELDS)):
            universe_id = f"pvctx-{abn}-{family}-not-processed-v1"
            universe = ReviewedEvidenceUniverse(
                universe_id=universe_id, subject_id=aisle["subject_id"], scope=scope,
                sources=tuple(ReviewedEvidenceSource(source_record_id=sid, status="not_processed") for sid in source_ids),
            )
            rationale = (
                f"Both exact retained source records in this {family}-field coverage universe were not processed for {family} semantics in the deterministic I/P/A context pass. "
                "The five future semantic requests remain PREPARED_NOT_SENT. This state is limited to those records and fields; it does not assert absence elsewhere."
            )
            coverage = ReviewedEvidenceCoverage(
                family=family, universe=universe,
                items=tuple(ReviewedEvidenceCoverageItem(
                    universe_id=universe_id, field=field, state="not_processed",
                    applicable_source_record_ids=source_ids, rationale=rationale,
                ) for field in fields),
            )
            family_contracts.append(coverage.model_dump(mode="json"))
            lineage = [{
                "source_record_id": source["source_record_id"],
                "source_artifact_id": source["source_artifact_id"],
                "representation_sha256": source["representation_sha256"],
                "source_carrier_role": source["source_role"],
                "processing_status_for_this_family": "not_processed",
            } for source in (aisle, report)]
            for coverage_item in coverage.items:
                question_id = f"{family}.{coverage_item.field}"
                candidate, decision, item = _coverage_candidate(
                    abn=abn, label=label, scope_id=scope_id, metadata=aisle,
                    state="not_processed", proposition_type=f"{family}_coverage_state",
                    section_id="18" if family == "outcomes" else "15", question_id=question_id,
                    rationale=rationale, universe_id=universe_id, source_lineage=lineage,
                    adjudicated_at=adjudicated_at,
                )
                items.append(item)
                adjudications.append({
                    **decision.model_dump(mode="json"), "adjudicator_class": ADJUDICATOR_CLASS,
                    "reviewer_id": REVIEWER_ID, "reviewer_role": REVIEWER_ROLE,
                    "coverage_candidate_id": candidate.candidate_id, "generated_item_ids": [item.item_id],
                })
        contracts.extend(family_contracts)

        # These three specific context gaps are explicit processing states only.
        generic_gaps = [
            ("source_representation_processing_coverage", "20", "annual_report_not_processed", report,
             "The retained annual/financial report representation was available in the fixed universe but was not processed by this deterministic I/P/A pass."),
            ("identity_registration_status_coverage", "1", "current_registration_status", aisle,
             "No current registration-status proposition was extracted in this pass. This is not a not-found or non-registration claim."),
            ("service_availability_capacity_coverage", "11", "current_availability_capacity_eligibility", aisle,
             "Current service availability, capacity, and eligibility were not processed by this I/P/A pass; no Capacity experiment was executed or reopened."),
        ]
        if abn == "28004778081":
            generic_gaps.append((
                "purpose_coverage_state", "2", "purpose_statement", report,
                "No Purpose proposition was admitted for World Vision from the mixed AIS field; the annual/financial report representation was not processed for this pass. Do not infer Purpose absence.",
            ))
        for prop_type, section_id, question_id, primary, rationale in generic_gaps:
            universe_id = f"pvctx-{abn}-{question_id.replace('.', '-')}-not-processed-v1"
            lineage = [{
                "source_record_id": source["source_record_id"],
                "source_artifact_id": source["source_artifact_id"],
                "representation_sha256": source["representation_sha256"],
                "source_carrier_role": source["source_role"],
                "processing_status_for_question": "not_processed",
            } for source in ((report,) if question_id == "annual_report_not_processed" or primary is report else (aisle, report))]
            candidate, decision, item = _coverage_candidate(
                abn=abn, label=label, scope_id=scope_id, metadata=primary,
                state="not_processed", proposition_type=prop_type, section_id=section_id,
                question_id=question_id, rationale=rationale, universe_id=universe_id,
                source_lineage=lineage, adjudicated_at=adjudicated_at,
            )
            items.append(item)
            adjudications.append({
                **decision.model_dump(mode="json"), "adjudicator_class": ADJUDICATOR_CLASS,
                "reviewer_id": REVIEWER_ID, "reviewer_role": REVIEWER_ROLE,
                "coverage_candidate_id": candidate.candidate_id, "generated_item_ids": [item.item_id],
            })
    return contracts, adjudications, items


def _check_integrity(work_root: Path) -> dict[str, Any]:
    lock_path = work_root / "model-assisted-baseline" / "source-only" / "source-only-baseline.lock.json"
    lock_hash = hashlib.sha256(lock_path.read_bytes()).hexdigest()
    if lock_hash != BASELINE_LOCK_SHA256:
        raise ValueError("source-only baseline lock changed")
    manifest_path = work_root / "campaign-preflight" / "execution-manifest.json"
    manifest_hash = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    if manifest_hash != REQUEST_MANIFEST_SHA256:
        raise ValueError("prepared semantic request manifest changed")
    request_hashes = {}
    for name, expected in REQUEST_BODY_SHA256.items():
        path = work_root / "campaign-preflight" / "requests" / name
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError(f"prepared semantic request body changed: {name}")
        request_hashes[name] = actual
    return {"baseline_lock_sha256": lock_hash, "request_manifest_sha256": manifest_hash, "request_body_sha256": request_hashes}


def adjudicate_context_inventory(
    work_root: Path, *, adjudicated_at: datetime,
) -> dict[str, Any]:
    if adjudicated_at.tzinfo is None or adjudicated_at.utcoffset() is None:
        raise ValueError("adjudication timestamp must be timezone-aware")
    integrity = _check_integrity(work_root)
    inventory_path = work_root / "deterministic-context" / "candidates.json"
    inventory_bytes = inventory_path.read_bytes()
    inventory_hash = hashlib.sha256(inventory_bytes).hexdigest()
    if inventory_hash != INVENTORY_SHA256:
        raise ValueError("original deterministic candidate inventory changed")
    inventory = json.loads(inventory_bytes.decode("utf-8"))
    rows = inventory["candidates"]
    if len(rows) != 118:
        raise ValueError("original candidate inventory does not reconcile to 118")
    decisions, proposition_items, disposition_counts = _source_candidate_decisions(rows, adjudicated_at)

    metadata_doc = json.loads((work_root / "model-assisted-baseline" / "source-only" / "source-metadata.json").read_text(encoding="utf-8"))
    all_sources: dict[str, dict[str, dict[str, Any]]] = {abn: {} for abn in SUBJECTS}
    for source in metadata_doc["sources"]:
        abn = source.get("abn")
        if abn in all_sources:
            all_sources[abn][source["source_family"]] = source
    if any(set(source_map) != {"acnc_ais_bundle", "annual_report"} for source_map in all_sources.values()):
        raise ValueError("the fixed reviewed source universe is incomplete")
    coverage_contracts, coverage_decisions, coverage_items = _make_coverage(all_sources, adjudicated_at)

    if disposition_counts != Counter({"ACCEPT": 86, "REJECT_MISSINGNESS": 24, "ACCEPT_MINOR_CORRECTION": 8}):
        raise ValueError(f"approved dispositions do not reconcile: {dict(disposition_counts)}")
    corrected_atom_count = sum(len(ATOM_SPECS[key]) for key in ATOM_SPECS)
    if len(proposition_items) != 86 + corrected_atom_count:
        raise ValueError("governed proposition count does not match accepted candidates and corrected atoms")
    if len(coverage_items) != 105:
        raise ValueError(f"mechanically justified coverage-state count changed: {len(coverage_items)}")
    if any(item.candidate_id in {row["candidate_id"] for row in rows if row["proposition_type"] == "acnc_carried_charitable_purpose_field_value"} for item in proposition_items):
        raise ValueError("rejected Purpose candidates leaked into governed propositions")

    governed_items = tuple([*proposition_items, *coverage_items])
    projection = project_experiment_items(governed_items)
    per_subject = []
    for abn, (label, _) in SUBJECTS.items():
        scoped = [item for item in projection.items if item.scope_id == SUBJECTS[abn][1]]
        propositions = [item for item in scoped if item.item_kind == "proposition"]
        coverage = [item for item in scoped if item.item_kind == "coverage_state"]
        section_counts: Counter[str] = Counter()
        for item in propositions:
            rep = item.governed_representation
            sections = rep.get("north_star_section_ids") or ([rep["north_star_section_id"]] if rep.get("north_star_section_id") else [])
            for section in sections:
                section_counts[str(section)] += 1
        per_subject.append({
            "abn": abn, "subject_label": label, "scope_id": SUBJECTS[abn][1],
            "governed_propositions": len(propositions), "governed_coverage_states": len(coverage),
            "propositions_by_north_star_section": dict(sorted(section_counts.items())),
            "coverage_state_counts": dict(Counter(item.coverage_state for item in coverage)),
            "readiness": "DETERMINISTIC_CONTEXT_READY_FOR_SEMANTIC_EXECUTION",
        })
    if len(per_subject) != 8 or any(
        subject["propositions_by_north_star_section"].get("1", 0) < 3
        or subject["propositions_by_north_star_section"].get("3", 0) < 1
        or subject["coverage_state_counts"].get("not_processed", 0) < 13
        for subject in per_subject
    ):
        raise ValueError("at least one fixed subject lacks governed identity, activity, or explicit processing coverage")
    if any(subject["governed_coverage_states"] == 0 for subject in per_subject):
        raise ValueError("every fixed subject requires explicit governed material-gap states")

    # Candidate bytes are checked again after all work; this run never writes them.
    if hashlib.sha256(inventory_path.read_bytes()).hexdigest() != inventory_hash:
        raise ValueError("original candidate inventory mutated during adjudication")
    adjudication_rows = decisions + coverage_decisions
    return {
        "generated_at": adjudicated_at.astimezone(timezone.utc).isoformat(),
        "adjudicator": {"id": ADJUDICATOR_ID, "class": ADJUDICATOR_CLASS, "role": ADJUDICATOR_ROLE},
        "reviewer": {"id": REVIEWER_ID, "role": REVIEWER_ROLE},
        "candidate_inventory_sha256": inventory_hash,
        "integrity": integrity,
        "dispositions": dict(disposition_counts),
        "original_candidates": 118,
        "corrected_governed_atoms": corrected_atom_count,
        "rejected_candidate_count": disposition_counts["REJECT_MISSINGNESS"],
        "unresolved_candidate_count": 0,
        "source_candidate_adjudications": decisions,
        "coverage_adjudications": coverage_decisions,
        "all_adjudications": adjudication_rows,
        "coverage_contracts": coverage_contracts,
        "proposition_items": [item.model_dump(mode="json") for item in proposition_items],
        "coverage_items": [item.model_dump(mode="json") for item in coverage_items],
        "private_projection": projection.model_dump(mode="json"),
        "per_subject": per_subject,
        "governed_counts": {
            "proposition_items": len(proposition_items),
            "coverage_state_items": len(coverage_items),
            "total_experiment_governed_items": len(governed_items),
            "adjudication_records": len(adjudication_rows),
            "canonical_public_items": 0,
        },
        "readiness": "DETERMINISTIC_CONTEXT_READY_FOR_SEMANTIC_EXECUTION",
        "readiness_reason": "All eight fixed subjects have human-adjudicated legal name, ABN, explicit AIS reporting year, and at least one human-adjudicated Activity proposition. The three sparse controls also have I/P/A propositions plus honest run-scoped gaps. O/C coverage contracts expose each material semantic field as not_processed within the exact retained-source universe, so the five fixed semantic requests may proceed only after the separate live execution gates. This is not final integrated-context sufficiency.",
        "provider_gate": "AWAITING_FRESH_OWNER_ATTESTATION",
        "provider_calls": 0,
        "source_acquisitions": 0,
        "human_adjudications": len(adjudication_rows),
        "candidate_promotions": 0,
        "canonical_public_promotions": 0,
        "viewer_changes": 0,
        "public_v0_5_changes": 0,
        "capacity_execution": 0,
    }
