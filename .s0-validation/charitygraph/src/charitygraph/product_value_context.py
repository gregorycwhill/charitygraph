"""Bounded deterministic I/P/A context extraction for the approved cohort.

This module reads only exact ACNC AIS structured representations already in the
locked product-value evidence universe. It does not interpret free text, call a
provider, acquire sources, adjudicate candidates, or promote/project candidates.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .product_value_experiment import ExperimentCandidate


DERIVATION_METHOD = "DETERMINISTIC_STRUCTURED_EXTRACTION"
CANDIDATE_PRODUCER_ID = "product-value-deterministic-context-v1"
BASELINE_LOCK_SHA256 = "dd269e6837e940601e1855e3a9b38b0e96ee669362889d91ae461bf621332d56"
SUBJECTS: dict[str, tuple[str, str]] = {
    "28004778081": ("World Vision Australia", "scope:28215361e26ec51e458fff956adfa89a2d6deed65d67376bb97cc18cac358051"),
    "78053639115": ("Bush Heritage Australia", "scope:988dbcb7b533a9cb8a3103e45cc134768be52f71456d83acf44f836c6a0b8d5f"),
    "50169561394": ("Australian Red Cross Society", "scope:90fea7d1a516443d43bf268cf091155c91c10a1fddfbc67dbefe6219597a7f81"),
    "61002643852": ("Greenpeace Australia Pacific Limited", "scope:4e359a111a4c83ba8f724d0ef8dbc54c0d782fb672ccdddd9a4cb575b6603daf"),
    "65159324697": ("The Sunrise Project Australia Limited", "scope:e652a8d7151b1eb961eb13c994726cdcdbf14b783246c1cf35e05ed4aabfc55d"),
    "32565549842": ("St George Community Housing Limited", "scope:d0ade5af2fb813a3da9e59086fbbb8f7c7b0ae2792cd4c92090795cd786d07a3"),
    "80009663478": ("Royal Flying Doctor Service of Australia (Queensland Section)", "scope:25f8932bf4fb925e2bd9fc0f9accafaa08e1d8e40f5b7e0c503b0106d1b55d27"),
    "57057493017": ("The Leukaemia Foundation of Australia Limited", "scope:915428824279e7211ba9e483ae67006091d3bc5185a2b88b20c783bfb6ef3609"),
}
IDENTITY_FIELDS = ("LegalName", "Abn", "StatementYear")
PURPOSE_FIELDS = ("AdvancementOfEducation", "AdvancementOfReligion", "ReliefOfPoverty", "OtherPurposes")
ACTIVITY_FIELDS = ("ActivityOperating", "ActivityOperatingOverseas")


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _pointer(path: str) -> str:
    return "#" + path


def _add_candidate(
    rows: list[dict[str, Any]], *, metadata: dict[str, Any], value: Any,
    field_path: str, proposition_type: str, section_ids: list[str],
    epistemic_status: str, scope_id: str, scope_label: str,
    mapping_status: str = "assigned_by_source_structured_field",
) -> None:
    field_locator = f"{metadata['evidence_locator_id']}#{field_path}"
    proposition = {
        "north_star_section_ids": section_ids,
        "mapping_status": mapping_status,
        "source_field_path": _pointer(field_path),
        "source_field_value": value,
        "derivation_method": DERIVATION_METHOD,
    }
    content = {
        "subject_id": metadata["subject_id"],
        "scope_id": scope_id,
        "scope_kind": "organisation",
        "source_artifact_id": metadata["source_artifact_id"],
        "source_record_id": metadata["source_record_id"],
        "representation_sha256": metadata["representation_sha256"],
        "retention_decision_id": metadata["retention_decision_id"],
        "proposition_type": proposition_type,
        "proposition": proposition,
        "evidence_locator_ids": [field_locator],
        "source_carrier_role": metadata["source_role"],
        "epistemic_status": epistemic_status,
        "reviewed_evidence_universe_id": "product-value-baseline-2026-09-14-source-only",
        "source_date": metadata["source_date"],
        "retrieved_at": metadata["retrieved_at"],
        "effective_period": metadata["effective_period"],
        "derivation_method": DERIVATION_METHOD,
        "north_star_section_ids": section_ids,
        "mapping_status": mapping_status,
        "subject_label_for_review": scope_label,
    }
    digest = hashlib.sha256(_canonical_bytes(content)).hexdigest()
    candidate = ExperimentCandidate(
        candidate_id=f"candidate:context-v1-{digest[:32]}",
        candidate_content_sha256=digest,
        subject_id=content["subject_id"],
        scope_id=scope_id,
        scope_kind="organisation",
        source_artifact_id=content["source_artifact_id"],
        source_record_id=content["source_record_id"],
        representation_sha256=content["representation_sha256"],
        retention_decision_id=content["retention_decision_id"],
        proposition_type=proposition_type,
        proposition=proposition,
        evidence_locator_ids=(field_locator,),
        source_carrier_role=content["source_carrier_role"],
        epistemic_status=epistemic_status,
        reviewed_evidence_universe_id=content["reviewed_evidence_universe_id"],
        source_period_start=None,
        source_period_end=None,
        candidate_producer_id=CANDIDATE_PRODUCER_ID,
        provider_request_id=None,
    )
    rows.append({**candidate.model_dump(mode="json"), **content})


def derive_context_candidates(
    source_root: Path,
    *,
    generated_at: datetime,
    expected_lock_sha256: str = BASELINE_LOCK_SHA256,
) -> list[dict[str, Any]]:
    """Derive only allow-listed field/value candidates from the eight frozen AIS rows."""
    if generated_at.tzinfo is None or generated_at.utcoffset() is None:
        raise ValueError("generated_at must be timezone-aware")
    lock_path = source_root / "source-only-baseline.lock.json"
    lock_bytes = lock_path.read_bytes()
    actual_lock_hash = hashlib.sha256(lock_bytes).hexdigest()
    if actual_lock_hash != expected_lock_sha256:
        raise ValueError("locked source-only baseline changed; refusing candidate generation")
    lock = json.loads(lock_bytes)
    lock_time = datetime.fromisoformat(lock["lock_timestamp"].replace("Z", "+00:00"))
    if generated_at.astimezone(timezone.utc) <= lock_time.astimezone(timezone.utc):
        raise ValueError("candidate generation must occur after the accepted baseline lock")

    metadata_doc = json.loads((source_root / "source-metadata.json").read_text(encoding="utf-8"))
    sources = metadata_doc["sources"]
    by_abn: dict[str, list[dict[str, Any]]] = {}
    for row in sources:
        if row.get("abn") in SUBJECTS and row.get("source_family") == "acnc_ais_bundle":
            by_abn.setdefault(row["abn"], []).append(row)
    if set(by_abn) != set(SUBJECTS) or any(len(rows) != 1 for rows in by_abn.values()):
        raise ValueError("expected exactly one retained ACNC AIS representation per approved subject")

    candidates: list[dict[str, Any]] = []
    for abn, (approved_label, scope_id) in SUBJECTS.items():
        metadata = by_abn[abn][0]
        if metadata.get("legal_scope") != "organisation" or not metadata.get("subject_name"):
            raise ValueError(f"approved subject scope/identity metadata is incomplete for {abn}")
        if metadata.get("provider_transmission_status") is None:
            raise ValueError(f"source rights lineage is incomplete for {abn}")
        path = source_root / metadata["representation_path"]
        exact_bytes = path.read_bytes()
        digest = hashlib.sha256(exact_bytes).hexdigest()
        if digest != metadata["representation_sha256"]:
            raise ValueError(f"retained representation hash mismatch for {abn}")
        if lock.get("source_representation_sha256", {}).get(metadata["representation_path"]) != digest:
            raise ValueError(f"representation is not bound by the accepted baseline lock for {abn}")
        record = json.loads(exact_bytes.decode("utf-8"))
        data = record.get("data", record)
        prefix = "/data" if "data" in record else ""
        if data.get("Abn") != abn:
            raise ValueError(f"source ABN does not match approved subject {abn}")

        for field in IDENTITY_FIELDS:
            value = data.get(field)
            if field in {"LegalName", "Abn"} and not isinstance(value, str):
                raise ValueError(f"required identity field {field} is not a string for {abn}")
            if field == "StatementYear" and value is None:
                continue
            _add_candidate(
                candidates, metadata=metadata, value=value,
                field_path=f"{prefix}/{field}",
                proposition_type={"LegalName": "acnc_carried_legal_name", "Abn": "acnc_carried_identifier", "StatementYear": "acnc_source_reporting_year"}[field],
                section_ids=["1"],
                epistemic_status="regulator_carried_record_value_not_independent_finding",
                scope_id=scope_id, scope_label=approved_label,
            )

        for field in PURPOSE_FIELDS:
            if field not in data or not isinstance(data[field], bool):
                continue
            _add_candidate(
                candidates, metadata=metadata, value=data[field],
                field_path=f"{prefix}/{field}",
                proposition_type="acnc_carried_charitable_purpose_field_value",
                section_ids=["2"],
                epistemic_status="first_party_report_carried_by_regulator",
                scope_id=scope_id, scope_label=approved_label,
                mapping_status="literal_purpose_field_value_only_no_absence_inference",
            )

        for field in ACTIVITY_FIELDS:
            if field not in data or not isinstance(data[field], bool):
                continue
            _add_candidate(
                candidates, metadata=metadata, value=data[field],
                field_path=f"{prefix}/{field}",
                proposition_type="acnc_carried_activity_field_value",
                section_ids=["3"],
                epistemic_status="first_party_report_carried_by_regulator",
                scope_id=scope_id, scope_label=approved_label,
                mapping_status="literal_activity_field_value_only_no_availability_or_capacity_inference",
            )

        programs = data.get("Programs")
        if isinstance(programs, list):
            for index, program in enumerate(programs):
                if not isinstance(program, dict):
                    raise ValueError(f"malformed Programs entry {index} for {abn}")
                selected = {key: program[key] for key in ("Name", "ProgramClassification", "ProgramClassificationID") if key in program}
                if not selected:
                    continue
                _add_candidate(
                    candidates, metadata=metadata, value=selected,
                    field_path=f"{prefix}/Programs/{index}",
                    proposition_type="acnc_carried_program_record",
                    section_ids=["3"],
                    epistemic_status="first_party_report_carried_by_regulator",
                    scope_id=scope_id, scope_label=approved_label,
                    mapping_status="organization_scoped_source_program_record_not_current_service_availability",
                )

        mixed_value = data.get("ActivityPersuitPurposesDescription")
        if isinstance(mixed_value, str) and mixed_value.strip():
            _add_candidate(
                candidates, metadata=metadata, value=mixed_value,
                field_path=f"{prefix}/ActivityPersuitPurposesDescription",
                proposition_type="acnc_carried_mixed_purpose_activity_description",
                section_ids=[],
                epistemic_status="first_party_report_carried_by_regulator",
                scope_id=scope_id, scope_label=approved_label,
                mapping_status="unassigned_mixed_purpose_activity_text_requires_human_atomization",
            )

    return candidates


def create_adjudication_packet(candidates: list[dict[str, Any]], generated_at: datetime) -> str:
    """Create an unfilled human packet; no disposition is inferred or supplied."""
    dispositions = (
        "ACCEPT", "ACCEPT_MINOR_CORRECTION", "REJECT_UNSUPPORTED", "REJECT_INCORRECT",
        "REJECT_SCOPE", "REJECT_EPISTEMIC_CLASS", "REJECT_MISSINGNESS",
        "MECHANICALLY_UNRESOLVED", "CRITICAL",
    )
    lines = [
        "# Private deterministic I/P/A candidate adjudication packet",
        "",
        f"Generated: `{generated_at.astimezone(timezone.utc).isoformat()}`",
        "",
        "**Status: CANDIDATES ONLY — no candidate has been adjudicated, promoted, or projected.**",
        "Review each proposition independently. ACNC is the record carrier; AIS content may be first-party-reported information and is not automatically an independent regulator finding. `ActivityPersuitPurposesDescription` remains unassigned because it mixes purpose language, activity, and reported results.",
        "",
    ]
    for row in candidates:
        lines.extend([
            f"## {row['candidate_id']}",
            "",
            f"- Subject: `{row['subject_id']}` / {row['subject_label_for_review']}",
            f"- Legal scope: `organisation` / `{row['scope_id']}`",
            f"- North Star section candidate: `{', '.join(row['north_star_section_ids']) or 'UNASSIGNED'}`",
            f"- Candidate type: `{row['proposition_type']}`",
            f"- Derivation: `{row['derivation_method']}`",
            f"- Source role: `{row['source_carrier_role']}`; epistemic status: `{row['epistemic_status']}`",
            f"- Source record/artifact: `{row['source_record_id']}` / `{row['source_artifact_id']}`",
            f"- Representation SHA-256: `{row['representation_sha256']}`; retention decision: `{row['retention_decision_id']}`",
            f"- Effective period: `{row['effective_period']}`; source date: `{row['source_date']}`; retrieved at: `{row['retrieved_at']}`",
            f"- Exact field locator: `{row['evidence_locator_ids'][0]}`",
            f"- Candidate mapping status: `{row['mapping_status']}`",
            "- Proposed fact/value (exact retained source field value):",
            "```json",
            json.dumps(row["proposition"]["source_field_value"], ensure_ascii=False, sort_keys=True, indent=2),
            "```",
            "- Disposition (leave blank until Greg adjudicates): `" + "` / `".join(dispositions) + "`",
            "- Corrected representation (if applicable): ",
            "- Rationale: ",
            "",
        ])
    return "\n".join(lines)


def create_projection_preview(candidates: list[dict[str, Any]], generated_at: datetime) -> dict[str, Any]:
    """Report candidate support separately from governed projection state."""
    preview_subjects = []
    for abn, (label, _) in SUBJECTS.items():
        subject_candidates = [row for row in candidates if row["subject_id"] and row["subject_label_for_review"] == label]
        sections = {section for row in subject_candidates for section in row["north_star_section_ids"]}
        preview_subjects.append({
            "abn": abn,
            "subject_label": label,
            "candidate_support": {
                "identity": {"status": "candidate_support_only" if "1" in sections else "not_processed", "candidate_count": sum("1" in r["north_star_section_ids"] for r in subject_candidates)},
                "purpose": {"status": "literal_field_candidates_only_not_adjudicated" if "2" in sections else "not_processed", "candidate_count": sum("2" in r["north_star_section_ids"] for r in subject_candidates)},
                "activity": {"status": "candidate_support_only" if "3" in sections else "not_processed", "candidate_count": sum("3" in r["north_star_section_ids"] for r in subject_candidates)},
                "purpose_activity_mixed_text": {"status": "unassigned_evidence_only" if any(r["mapping_status"] == "unassigned_mixed_purpose_activity_text_requires_human_atomization" for r in subject_candidates) else "not_processed"},
            },
            "outcomes": {"status": "not_processed_in_this_context_pass", "governed_items": 0},
            "commitments": {"status": "not_processed_in_this_context_pass", "governed_items": 0},
            "explicit_coverage": {
                "status": "candidate_run_state_only",
                "retained_acnc_record": "processed_structured_fields_only",
                "retained_annual_report_representation": "not_processed",
                "purpose_atomization": "not_processed",
                "registration_status": "not_processed_no_explicit_status_field_extracted",
                "service_availability_capacity_eligibility": "not_processed",
                "outcomes_commitments": "not_processed_in_this_context_pass",
                "interpretation": "Run-specific processing state only; not source silence, not source unavailability, and not a substantive absence claim.",
            },
            "governed_projection_items": 0,
            "sufficiency_prediction": "CANDIDATE_SUPPORT_REQUIRES_GREG_ADJUDICATION_AND_COVERAGE_REVIEW",
        })
    return {
        "generated_at": generated_at.astimezone(timezone.utc).isoformat(),
        "status": "OFFLINE_CANDIDATE_ONLY_PREVIEW_NOT_A_GOVERNED_PROJECTION",
        "approved_subject_count": len(SUBJECTS),
        "candidate_count": len(candidates),
        "governed_items": 0,
        "governed_coverage_states": 0,
        "projected_items": 0,
        "sufficiency_rule": "For fixed Inspect: adjudicated legal Identity plus at least one adjudicated Purpose or Activity statement, explicit reporting scope, and explicit run/source coverage states for material questions; for the five semantic subjects, later adjudicated Outcomes or Commitments context is additionally required. Sparse controls require I/P/A plus explicit gaps. This preview is not a sufficiency decision.",
        "subjects": preview_subjects,
    }
