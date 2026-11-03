"""Provider-free Factory replay for the preserved Gate 4 five-charity slice.

This is an intake/replay adapter only.  It validates the already retained
publicdata.au representations, delegates binding to the existing T3 binder,
delegates eligibility to the governed preflight, and delegates execution to
the existing ReferenceFactory.  It never acquires, discovers, interprets, or
sends source material.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from .contracts import (
    AcquisitionReceipt,
    ArtifactRef,
    PropositionAuthorityRole,
    ProducerRef,
    SchemaRef,
    ScopeRecord,
    SourceDefinition,
    SourceRecord,
    StructuredFieldLocator,
    SubjectRecord,
)
from .contracts.canonical import canonical_json_bytes, canonical_sha256
from .contracts.ids import deterministic_id
from .phase5_factory import FactoryPlan, ReferenceFactory, RehearsalFakeProvider
from .phase5_governed_factory_integration import GovernedReference, GovernedFactoryPreflight, preflight_governed_references
from .phase5_run_diagnostics import project_run_diagnostics
from .phase5_t3_source_evidence_binding import SourceEvidenceBindingResult, bind_acnc_source_evidence
from .source_rights import ArtifactRightsDecision
from .runtime import SQLiteCatalog


SCHEMA = "charitygraph.gate4.o1c.real-five-charity-factory-replay/v1"
AS_OF = date(2026, 11, 3)
NOW = datetime(2026, 11, 3, tzinfo=timezone.utc)
EVIDENCE_DIR = Path("evidence/gate4-t3-five-subject-v1")
RUNTIME_ROOT = Path(r"C:\CharityGraph-runtime")
SELECTED_MANIFEST_ID = "41b4ce5f1c39afd31a28b1f819d2a9759c89880eb0ddb2d2b143662cf4dda7a9"
SELECTED_MANIFEST_FILE_SHA256 = "06d406393d5ee738e7bad2c8113a06302836e72d53bd06dd77a945bd4f7276d4"
PRESERVED_INPUT_SHA256 = {
    "publicdata-20261026-four-charity-acquisition-receipts.json": "2947d5735438419a2afd602970815938e7e10aa8c15b2054e10be5ce86864cd1",
    "publicdata-20261026-four-charity-rights-decisions.json": "ed3cc78df651932da123cda0122fe4e71ea42f06ca0f4ef842a9abcc56c0bd24",
    "publicdata-20261026-four-charity-bindings.json": "19fc0fd23bd5b0e085c7f2b7c879a1cd3407a73f30be4560ef18a35fa91f931e",
}
BOUND_ORDINALS = (1, 3, 5, 7, 9)
MISSING_AIS_ORDINALS = (2, 4, 6, 8, 10)
SOURCE_SILENT_SECTION = 20
_PRODUCER = ProducerRef(kind="code", producer_id="g4-o1c-real-five-charity-factory", version="1")
_SCHEMA = SchemaRef(schema_id="urn:charitygraph:builder:schema:source-artefact:1.0", schema_version="1.0")


class RealFiveCharityInputError(ValueError):
    """The preserved evidence cannot be safely composed for replay."""


@dataclass(frozen=True)
class RealFiveCharityEvidence:
    binding: SourceEvidenceBindingResult
    references: tuple[GovernedReference, ...]
    materials: tuple[dict[str, Any], ...]
    retained_bytes: Mapping[str, bytes]
    selected_manifest_sha256: str
    input_hashes: Mapping[str, str]
    north_star_coverage: tuple[dict[str, Any], ...]
    source_silence_records: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class RealFiveCharityFactoryPlan:
    evidence: RealFiveCharityEvidence
    preflight: GovernedFactoryPreflight
    factory_plan: FactoryPlan
    cohort_id: str
    plan_sha256: str

    @property
    def task_ids(self) -> tuple[str, ...]:
        return tuple(item["logical_task_id"] for item in self.factory_plan.logical_tasks)


@dataclass(frozen=True)
class RealFiveCharityFactoryExecution:
    cohort_id: str
    run_id: str
    task_count: int
    completed_tasks: int
    attempt_count: int
    provider_calls: int
    aud_actual: str
    aud_released: str
    diagnostic_sha256: str


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RealFiveCharityInputError(f"cannot read preserved JSON: {path}") from exc
    if not isinstance(value, dict):
        raise RealFiveCharityInputError(f"preserved JSON root is not an object: {path}")
    return value


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _assert_hash(path: Path, expected: str) -> str:
    try:
        actual = _sha256_bytes(path.read_bytes())
    except OSError as exc:
        raise RealFiveCharityInputError(f"preserved input is unavailable: {path}") from exc
    if actual != expected:
        raise RealFiveCharityInputError(f"preserved input hash mismatch: {path}")
    return actual


def _runtime_bytes(path: Path, expected: str) -> bytes:
    try:
        value = path.read_bytes()
    except OSError as exc:
        raise RealFiveCharityInputError(f"retained runtime representation is unavailable: {path}") from exc
    if _sha256_bytes(value) != expected:
        raise RealFiveCharityInputError(f"retained runtime bytes hash mismatch: {path}")
    return value


def _row_map(rows: Iterable[Mapping[str, Any]]) -> dict[int, dict[str, Any]]:
    result = {int(row["ordinal"]): dict(row) for row in rows}
    if len(result) != 10 or tuple(sorted(result)) != tuple(range(1, 11)):
        raise RealFiveCharityInputError("the preserved cohort must contain ordinals 1 through 10")
    return result


def _clean_source_record(raw: Mapping[str, Any], *, source_record_id: str, acquired_at: str) -> SourceRecord:
    allowed = {
        "record_id", "created_at", "producer", "about_subject_ids", "lineage", "content_hash",
        "source_family", "source_role", "source_version", "source_locator", "retrieved_at",
        "observed_at", "media_type", "payload_ref", "payload_hash", "rights_policy_id", "attribution",
    }
    data = {key: raw[key] for key in raw.keys() & allowed}
    data.update(record_id=source_record_id, created_at=acquired_at, producer=_PRODUCER, observed_at=acquired_at)
    return SourceRecord.model_validate(data)


def _clean_receipt(raw: Mapping[str, Any], *, receipt_id: str, acquired_at: str) -> AcquisitionReceipt:
    data = {
        "record_id": receipt_id,
        "created_at": acquired_at,
        "producer": _PRODUCER,
        "source_definition_id": raw["source_definition_id"],
        "requested_locator": raw.get("requested_locator", raw.get("source_url")),
        "resolved_locator": raw.get("resolved_locator", raw.get("source_url")),
        "retrieved_at": raw.get("retrieved_at", raw.get("received_at_utc", acquired_at)),
        "outcome": raw["outcome"],
        "response_status": raw.get("response_status"),
        "media_type": raw.get("media_type"),
        "content_hash": raw.get("content_hash"),
        "byte_size": raw.get("byte_size"),
        "artifact_id": raw.get("artifact_id"),
        "material_parameters": {},
    }
    return AcquisitionReceipt.model_validate(data)


def _provider_decision(axis: Mapping[str, Any], *, source_url: str, source_sha256: str, source_role: str, receipt_id: str) -> ArtifactRightsDecision:
    return ArtifactRightsDecision.model_validate({
        "decision_id": axis["decision_id"],
        "source_artifact_id": axis["source_artifact_id"],
        "source_record_id": axis["source_record_id"],
        "source_origin_url": source_url,
        "source_role": source_role,
        "acquisition_lineage_ids": tuple(axis.get("acquisition_lineage_ids") or (receipt_id,)),
        "transmitted_representation_sha256": axis["representation_sha256"],
        "rights_policy_id": axis["policy_id"],
        "provider_processing_policy_id": axis["provider_policy_id"],
        "rights_basis": axis["rights_basis"],
        "evidence_locator": source_url,
        "evidence_sha256": source_sha256,
        "assessed_on": axis["assessed_on"],
        "assessment_scope": "preserved Gate 4 private provider-processing decision",
        "attribution": axis.get("attribution"),
        "licence_identifier": axis.get("licence_identifier"),
        "licence_or_terms_url": axis.get("licence_or_terms_url"),
        "local_retention_allowed": False,
        "provider_transmission_allowed": bool(axis.get("provider_call_authorized", False)),
        "public_redistribution_allowed": bool(axis.get("public_redistribution_allowed", False)),
        "factual_representation_only": True,
        "representation_class": "structured_factual",
        "publicly_accessible_without_circumvention": True,
        "access_controls_bypassed": False,
        "lawfully_acquired": True,
        "analytical_purpose": "evidence_grounded_knowledge_construction",
        "explicit_prohibition_found": False,
        "provider_no_training_default": bool(axis.get("provider_no_training_default", True)),
        "provider_data_sharing_opt_in": axis.get("provider_data_sharing_opt_in", False),
        "decision_version": axis.get("decision_version", "1"),
        "representation_artifact_id": axis["representation_artifact_id"],
        "rights_policy_version": axis.get("policy_version"),
        "provider_processing_policy_version": axis.get("provider_policy_version"),
        "assessment_authority": "preserved-private-rights-decision",
        "expires_on": axis.get("review_deadline"),
        "status": axis.get("status", "authorized"),
    })


def _subject(subject_id: str, scope_id: str, abn: str, name: str, source_artifact_id: str, source_sha256: str) -> SubjectRecord:
    return SubjectRecord(
        record_id=deterministic_id("subjectrecord:", {"subject_id": subject_id, "source_artifact_id": source_artifact_id}),
        created_at=NOW,
        producer=_PRODUCER,
        subject_id=subject_id,
        subject_kind="legal_entity",
        lifecycle_status="active",
        display_name=name,
        external_identifiers=(
            {"scheme": "ABN", "value": abn, "issuing_authority": "Australian Business Register"},
        ),
        identity_authority_refs=(ArtifactRef(artifact_id=source_artifact_id, content_hash=source_sha256, schema=_SCHEMA),),
        identity_policy_id="acnc-registered-charity-bootstrap-v1",
    )


def _source_definition(source_definition_id: str, source_url: str, source_family: str) -> SourceDefinition:
    return SourceDefinition(
        record_id=source_definition_id,
        created_at=NOW,
        producer=_PRODUCER,
        publisher="Australian Charities and Not-for-profits Commission",
        source_class=source_family,
        authority_roles=(PropositionAuthorityRole(proposition="registered entity", role="register identity"),),
        acquisition_locator=source_url,
        temporal_semantics="versioned publicdata.au API representation",
        publication_eligibility="private review only",
        steward="CharityGraph source governance",
        rights_policy_id="CG_PUBLIC_SOURCE_PRIVATE_PROVIDER_TRANSMISSION_V1",
    )


def _coverage(subject_ids: tuple[str, ...]) -> tuple[dict[str, Any], ...]:
    titles = {
        1: "Identity / regulatory", 2: "Purpose / cause", 3: "Programs / services", 4: "Activities / SDGs",
        5: "Geography / beneficiaries", 6: "Participation", 7: "Direct service / capacity", 8: "Fundraising",
        9: "Governance / leadership", 10: "People / workforce", 11: "Scale / capability", 12: "Relationships",
        13: "Finances", 14: "Funding / dependencies", 15: "Ethos / values", 16: "Conduct / adverse",
        17: "Notable history", 18: "Evaluation / outcomes", 19: "Classification / search / AI discovery",
        20: "Evidence / coverage / freshness / corrections",
    }
    result = []
    for section_id in range(1, 21):
        code, status, basis = ("P", "partial", "observed_present") if section_id == 1 else (("S", "supported", "observed_present") if section_id == 20 else ("M", "unassessed", "not_reviewed"))
        result.append({"section_id": section_id, "title": titles[section_id], "code": code, "status": status, "basis": basis})
    return tuple(result)


def _source_silence(subject_ids: tuple[str, ...], scope_by_subject: Mapping[str, str]) -> tuple[dict[str, Any], ...]:
    return tuple({
        "subject_id": subject_id,
        "scope_id": scope_by_subject[subject_id],
        "section_id": SOURCE_SILENT_SECTION,
        "status": "source_silent",
        "assessment_basis": {"contract": "north-star-v0.3", "kind": "reviewed_source_silence"},
        "source_silence_is_not_absence": True,
    } for subject_id in sorted(subject_ids))


def load_real_five_charity_evidence(*, evidence_root: str | Path = EVIDENCE_DIR, runtime_root: str | Path = RUNTIME_ROOT) -> RealFiveCharityEvidence:
    """Validate the preserved inputs and lower them through the existing T3 binder."""
    root = Path(evidence_root)
    for name, expected in PRESERVED_INPUT_SHA256.items():
        _assert_hash(root / name, expected)
    manifest_path = root / "selected-binding-manifest.json"
    _assert_hash(manifest_path, SELECTED_MANIFEST_FILE_SHA256)
    manifest = _read_json(manifest_path)
    if manifest.get("selected_manifest_sha256") != SELECTED_MANIFEST_ID or len(manifest.get("rows", ())) != 10:
        raise RealFiveCharityInputError("selected-binding manifest identity or denominator is invalid")
    selected_rows = _row_map(manifest["rows"])
    if len({row["subject_id"] for row in selected_rows.values()}) != 5:
        raise RealFiveCharityInputError("selected-binding manifest does not preserve five subjects")

    first_binding = _read_json(root / "first-charity-publicdata-api-binding-20261026.json")
    first_rights = _read_json(root / "first-charity-publicdata-provider-rights-20261103.json")
    first_retention = _read_json(root / "first-charity-official-acnc-source-retention-v1.json")
    four_bindings = _read_json(root / "publicdata-20261026-four-charity-bindings.json")
    four_receipts = _read_json(root / "publicdata-20261026-four-charity-acquisition-receipts.json")
    four_rights = _read_json(root / "publicdata-20261026-four-charity-rights-decisions.json")
    if four_bindings.get("cohort") != {
        "denominator": 10, "bound_count": 5, "bound_register_ordinals": list(BOUND_ORDINALS),
        "missing_count": 5, "missing_ais_ordinals": list(MISSING_AIS_ORDINALS), "blocked_count": 0,
        "provider_calls": 0, "publications": 0, "spend_aud": "0.00",
    }:
        raise RealFiveCharityInputError("preserved four-charity artifact does not carry the five-bound/five-missing result")

    four_receipt_rows = {int(row["ordinal"]): dict(row) for row in four_receipts["rows"]}
    four_right_rows = {int(row["ordinal"]): dict(row) for row in four_rights["rows"]}
    four_binding_rows = {int(row["ordinal"]): dict(row) for row in four_bindings["binding_result"]["rows"]}
    first_binding_rows = _row_map(first_binding["binding_result"]["rows"])
    materials: list[dict[str, Any]] = []
    retained: dict[str, bytes] = {}
    input_hashes = {**PRESERVED_INPUT_SHA256, "selected-binding-manifest.json": SELECTED_MANIFEST_FILE_SHA256}
    runtime = Path(runtime_root)

    for ordinal in BOUND_ORDINALS:
        if ordinal == 1:
            retention_record = first_retention["retention"]
            source = retention_record["source_record"]
            acquisition = retention_record["acquisition_receipt"]
            representation = retention_record["representation"]
            rights_axis = first_rights["rights_decision"]
            binding_row = first_binding_rows[1]
            abn, name = first_rights["target"]["abn"], first_rights["target"]["name"]
            raw_path = runtime / "g4-o1c-publicdata-acnc-register-20261103" / "raw-response.json"
            rep_path = runtime / "g4-o1c-publicdata-acnc-register-20261103" / "normalized-representation.json"
            source_definition_id = first_rights["source"]["definition_id"]
            acquired_at = acquisition["received_at_utc"]
        else:
            receipt_row = four_receipt_rows[ordinal]
            source = receipt_row["source_record"]
            acquisition = receipt_row["acquisition_receipt"]
            representation = receipt_row["representation"]
            rights_axis = four_right_rows[ordinal]["private_provider_processing"]
            binding_row = four_binding_rows[ordinal]
            abn, name = receipt_row["abn"], receipt_row["name"]
            raw_path = Path(receipt_row["raw_runtime_path"])
            rep_path = Path(receipt_row["representation_runtime_path"])
            source_definition_id = receipt_row["source_definition_id"]
            acquired_at = receipt_row["acquired_at_utc"]
        subject_id = selected_rows[ordinal]["subject_id"]
        scope_id = selected_rows[ordinal]["scope_id"]
        if binding_row["subject_id"] != subject_id or binding_row["scope_id"] != scope_id:
            raise RealFiveCharityInputError(f"ordinal {ordinal} moved subject or scope")
        source_sha = str(source["payload_hash"] if "payload_hash" in source else source["sha256"])
        representation_sha = str(representation["content_hash"] if "content_hash" in representation else representation["sha256"])
        raw = _runtime_bytes(raw_path, source_sha)
        rep = _runtime_bytes(rep_path, representation_sha)
        if source["id"] != binding_row["source_record_id"] or representation["artifact_id"] != binding_row["representation_artifact_id"]:
            raise RealFiveCharityInputError(f"ordinal {ordinal} source/representation identity mismatch")
        if representation.get("source_artifact_id") != source["payload_ref"] or representation.get("source_record_id") != source["id"]:
            raise RealFiveCharityInputError(f"ordinal {ordinal} representation lineage mismatch")
        if rights_axis["source_record_id"] != source["id"] or rights_axis["representation_artifact_id"] != representation["artifact_id"]:
            raise RealFiveCharityInputError(f"ordinal {ordinal} rights lineage mismatch")
        if rights_axis["representation_sha256"] != representation_sha or rights_axis.get("provider_call_authorized") is not False:
            raise RealFiveCharityInputError(f"ordinal {ordinal} rights hash or provider authority mismatch")
        receipt_id = acquisition.get("id", acquisition.get("acquisition_receipt_id"))
        if receipt_id != binding_row["acquisition_receipt_id"] or acquisition.get("content_hash") != source_sha or acquisition.get("artifact_id") != source["payload_ref"] or acquisition.get("outcome") != "available":
            raise RealFiveCharityInputError(f"ordinal {ordinal} acquisition receipt mismatch")
        if representation.get("representation_origin") and "not ACNC publisher original bytes" not in representation["representation_origin"] and representation.get("origin") and "not ACNC publisher original bytes" not in representation["origin"]:
            raise RealFiveCharityInputError(f"ordinal {ordinal} publisher-original representation claim was not excluded")
        retained[source["payload_ref"]] = raw
        retained[representation["artifact_id"]] = rep
        materials.append({
            "ordinal": ordinal, "abn": abn, "name": name, "subject_id": subject_id, "scope_id": scope_id,
            "source_definition_id": source_definition_id, "source_record": dict(source),
            "acquisition_receipt": dict(acquisition), "representation": dict(representation),
            "local_retention_decision": dict(retention_record["local_retention_decision"] if ordinal == 1 else four_receipt_rows[ordinal]["local_retention_decision"]),
            "provider_rights_decision": dict(rights_axis), "source_url": source["source_locator"],
            "source_sha256": source_sha, "representation_sha256": representation_sha,
            "source_artifact_id": source["payload_ref"], "representation_artifact_id": representation["artifact_id"],
            "receipt_id": receipt_id, "evidence_locator_id": binding_row.get("evidence_locator_id") or representation.get("evidence_locator_ids", [None])[0],
            "raw_path": str(raw_path), "representation_path": str(rep_path),
        })

    binder_rows = [first_binding_rows[1], first_binding_rows[2]] + [four_binding_rows[ordinal] for ordinal in range(3, 11)]
    # The selected manifest retains the five-subject/two-source denominator;
    # the preserved evidence rows supply the independently observed register
    # bindings and explicit AIS missingness for that denominator.
    binder_input = {
        "schema": manifest["schema"],
        "source_universe_version": "v1",
        "selected_manifest_sha256": SELECTED_MANIFEST_ID,
        "rows": binder_rows,
    }
    existing: dict[str, Any] = {key: [] for key in ("subjects", "scopes", "source_definitions", "source_records", "acquisition_receipts", "representations", "rights_decisions")}
    subjects_seen: set[str] = set()
    scopes_seen: set[str] = set()
    definitions_seen: set[str] = set()
    for material in materials:
        if material["subject_id"] not in subjects_seen:
            subject_record = _subject(material["subject_id"], material["scope_id"], material["abn"], material["name"], material["source_artifact_id"], material["source_sha256"]).model_dump(mode="json")
            subject_record["id"] = material["subject_id"]
            existing["subjects"].append(subject_record)
            subjects_seen.add(material["subject_id"])
        if material["scope_id"] not in scopes_seen:
            scope_record = ScopeRecord(record_id=material["scope_id"], created_at=NOW, producer=_PRODUCER, subject_id=material["subject_id"], scope_kind="organisation", label="registered entity").model_dump(mode="json")
            scope_record["id"] = material["scope_id"]
            existing["scopes"].append(scope_record)
            scopes_seen.add(material["scope_id"])
        if material["source_definition_id"] not in definitions_seen:
            existing["source_definitions"].append({"id": material["source_definition_id"], "source_definition_id": material["source_definition_id"], "source_family": "acnc_register", "source_role": "register_identity"})
            definitions_seen.add(material["source_definition_id"])
        existing["source_records"].append(material["source_record"])
        existing["acquisition_receipts"].append(material["acquisition_receipt"])
        existing["representations"].append(material["representation"])
        existing["rights_decisions"].append(material["local_retention_decision"])
        existing["rights_decisions"].append(material["provider_rights_decision"])
    silence = _source_silence(tuple(sorted(subjects_seen)), {item["subject_id"]: item["scope_id"] for item in materials})
    binding = bind_acnc_source_evidence(
        binder_input,
        existing=existing,
        retained_bytes=retained,
        as_of=AS_OF,
        require_five_subject_ten_rows=True,
    )
    if binding.bound_count != 5 or binding.missing_count != 5 or [row.ordinal for row in binding.rows if row.status == "BOUND"] != list(BOUND_ORDINALS):
        raise RealFiveCharityInputError("T3 binder did not reproduce five BOUND and five MISSING rows")
    references = tuple(row.governed_reference.model_copy(update={"provider_processing_policy_id": None, "provider_processing_policy_version": None}) for row in binding.rows if row.governed_reference is not None)
    if len(references) != 5:
        raise RealFiveCharityInputError("T3 binder did not lower all five bound rows")
    subjects = tuple(sorted({row.subject_id for row in binding.rows}))
    coverage = _coverage(subjects)
    return RealFiveCharityEvidence(
        binding=binding, references=references, materials=tuple(materials), retained_bytes=retained,
        selected_manifest_sha256=SELECTED_MANIFEST_ID, input_hashes=input_hashes,
        north_star_coverage=coverage, source_silence_records=silence,
    )


def _metadata_catalog(evidence: RealFiveCharityEvidence) -> dict[str, Any]:
    """Build the read-only metadata view consumed by governed preflight."""
    catalog: dict[str, Any] = {"subjects": {}, "scopes": {}, "source_definitions": {}, "receipts": {}, "sources": {}, "artifacts": {}, "lineage": {}, "locators": {}, "rights": {}}
    for material in evidence.materials:
        subject = _subject(material["subject_id"], material["scope_id"], material["abn"], material["name"], material["source_artifact_id"], material["source_sha256"]).model_dump(mode="json")
        catalog["subjects"][material["subject_id"]] = subject
        catalog["scopes"][material["scope_id"]] = {"scope_id": material["scope_id"], "subject_id": material["subject_id"]}
        catalog["source_definitions"][material["source_definition_id"]] = {"source_definition_id": material["source_definition_id"]}
        receipt = material["acquisition_receipt"]
        catalog["receipts"][material["receipt_id"]] = {"id": material["receipt_id"], "source_definition_id": material["source_definition_id"], "artifact_id": material["source_artifact_id"], "content_hash": material["source_sha256"], "outcome": "available"}
        source = material["source_record"]
        catalog["sources"][source["id"]] = {**source, "material": source}
        catalog["artifacts"][material["source_artifact_id"]] = {"artifact_id": material["source_artifact_id"], "content_hash": material["source_sha256"], "availability": "available"}
        catalog["artifacts"][material["representation_artifact_id"]] = {"artifact_id": material["representation_artifact_id"], "content_hash": material["representation_sha256"], "availability": "available"}
        catalog["lineage"][material["representation_artifact_id"]] = [{"input_artifact_id": material["source_artifact_id"]}]
        locator_id = material["evidence_locator_id"]
        catalog["locators"][locator_id] = {"artifact_id": material["representation_artifact_id"], "material_hash": material["representation_sha256"]}
        decision = _provider_decision(material["provider_rights_decision"], source_url=material["source_url"], source_sha256=material["source_sha256"], source_role="register_identity", receipt_id=material["receipt_id"])
        catalog["rights"][material["representation_artifact_id"]] = [{
            "decision_id": decision.decision_id, "rights_policy_id": decision.rights_policy_id,
            "rights_policy_version": decision.rights_policy_version,
            "material_json": json.dumps({"decision": decision.model_dump(mode="json")}, sort_keys=True),
        }]
    return catalog


class _PreflightMetadataCatalog:
    def __init__(self, values: Mapping[str, Any]):
        self.values = values
        self.diagnostics: list[dict[str, Any]] = []

    def get_subject(self, key: str): return self.values["subjects"].get(key)
    def get_scope(self, key: str): return self.values["scopes"].get(key)
    def get_source_definition(self, key: str): return self.values["source_definitions"].get(key)
    def get_acquisition_receipt(self, key: str): return self.values["receipts"].get(key)
    def get_source_record(self, key: str): return self.values["sources"].get(key)
    def get_artifact(self, key: str): return self.values["artifacts"].get(key)
    def get_artifact_lineage(self, key: str): return self.values["lineage"].get(key, [])
    def get_evidence_locator(self, key: str): return self.values["locators"].get(key)
    def get_artifact_rights_decisions(self, keys):
        wanted = set(keys)
        return [row for rows in self.values["rights"].values() for row in rows if row["decision_id"] in wanted]
    def list_artifact_rights_decisions(self, *, representation_artifact_id: str): return self.values["rights"].get(representation_artifact_id, [])
    def record_provider_rights_diagnostic(self, **kwargs): self.diagnostics.append(kwargs)


def build_real_five_charity_factory_plan(evidence: RealFiveCharityEvidence) -> RealFiveCharityFactoryPlan:
    metadata_catalog = _PreflightMetadataCatalog(_metadata_catalog(evidence))
    preflight = preflight_governed_references(
        evidence.references,
        catalog=metadata_catalog,
        retained_bytes=lambda artifact_id: evidence.retained_bytes[artifact_id],
        build_id="g4-o1c-real-five-charity-factory-v1",
        route_policy_version="g4-o1c-real-five-charity-factory-route-v1",
        planned_processing_at=NOW,
    )
    if preflight.diagnostics or preflight.accepted_count != 5:
        raise RealFiveCharityInputError("governed preflight did not accept exactly five deterministic local tasks")
    factory_plan = preflight.factory_plan
    plan_payload = {
        "schema": SCHEMA, "selected_manifest_sha256": evidence.selected_manifest_sha256,
        "task_ids": [item["logical_task_id"] for item in factory_plan.logical_tasks],
        "task_identities": [{key: item.get(key) for key in ("logical_task_id", "subject_id", "scope_id", "difficulty", "source_record_ids", "representation_artifact_ids", "representation_hashes", "rights_policy_ids", "rights_roles", "governed_reference_hash")} for item in factory_plan.logical_tasks],
        "coverage": list(evidence.north_star_coverage), "source_silence_records": list(evidence.source_silence_records),
    }
    plan_sha = canonical_sha256(plan_payload)
    return RealFiveCharityFactoryPlan(evidence=evidence, preflight=preflight, factory_plan=factory_plan, cohort_id=deterministic_id("cohort:", {"plan_sha256": plan_sha}), plan_sha256=plan_sha)


def preflight_real_five_charity_references(evidence: RealFiveCharityEvidence, references: Iterable[GovernedReference] | None = None) -> GovernedFactoryPreflight:
    catalog = _PreflightMetadataCatalog(_metadata_catalog(evidence))
    return preflight_governed_references(
        tuple(evidence.references if references is None else references), catalog=catalog,
        retained_bytes=lambda artifact_id: evidence.retained_bytes[artifact_id], build_id="g4-o1c-real-five-charity-factory-v1",
        route_policy_version="g4-o1c-real-five-charity-factory-route-v1", planned_processing_at=NOW,
    )


def _diagnostic(catalog: SQLiteCatalog, run_id: str):
    with catalog._connection() as conn:
        run = dict(conn.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone())
        tasks = [dict(row) for row in conn.execute("SELECT * FROM tasks WHERE run_id=? ORDER BY model_task_id", (run_id,))]
        attempts = [dict(row) for row in conn.execute("SELECT * FROM task_attempts WHERE model_task_id IN (SELECT model_task_id FROM tasks WHERE run_id=?) ORDER BY task_run_id", (run_id,))]
        reservations = [dict(row) for row in conn.execute("SELECT * FROM budget_reservations WHERE run_id=? ORDER BY reservation_id", (run_id,))]
        costs = [dict(row) for row in conn.execute("SELECT * FROM cost_entries WHERE run_id=? ORDER BY entry_key", (run_id,))]
        receipts = [dict(row) for row in conn.execute("SELECT pr.* FROM provider_receipts pr JOIN physical_attempts pa ON pa.physical_attempt_id=pr.physical_attempt_id WHERE pa.run_id=? ORDER BY provider_receipt_id", (run_id,))]
    ledger = {"tasks": [{"task_id": row["model_task_id"], "status": row["status"]} for row in tasks], "attempts": [{"attempt_id": row["task_run_id"], "task_id": row["model_task_id"], "status": row["status"]} for row in attempts], "receipts": [{"receipt_id": row["provider_receipt_id"]} for row in receipts], "reservations": [{"reservation_id": row["reservation_id"], "status": row["status"]} for row in reservations], "cost_entries": [{"entry_key": row["entry_key"], "entry_type": row["entry_type"], "accounting_amount": row["accounting_amount"]} for row in costs]}
    return project_run_diagnostics({"run_id": run_id, "provenance": {"run_record_ref": f"run:{run_id}", "ledger_snapshot_ref": f"ledger:{run_id}"}, "results": [{"item_id": row["model_task_id"], "subject_id": row["subject_id"], "scope_id": row["scope_id"] or "scope:not-applicable", "status": "completed" if row["status"] == "succeeded" else row["status"], "provider_posts": 0, "stop_campaign": False} for row in tasks], "planned_item_count": len(tasks), "provider_posts": 0, "stop": {"campaign_stopped": False, "classification": "none"}}, ledger)


def execute_real_five_charity_factory(plan: RealFiveCharityFactoryPlan, *, work_root: str | Path, now: datetime = NOW) -> RealFiveCharityFactoryExecution:
    root = Path(work_root)
    catalog = SQLiteCatalog(root / "catalog.sqlite3").open(initialize=True)
    try:
        run_id = deterministic_id("run:", {"cohort_id": plan.cohort_id, "plan_sha256": plan.plan_sha256})
        seen_subjects: set[str] = set()
        seen_scopes: set[str] = set()
        for material in plan.evidence.materials:
            if material["subject_id"] not in seen_subjects:
                catalog.register_subject(_subject(material["subject_id"], material["scope_id"], material["abn"], material["name"], material["source_artifact_id"], material["source_sha256"]))
                seen_subjects.add(material["subject_id"])
            if material["scope_id"] not in seen_scopes:
                catalog.register_scope(ScopeRecord(record_id=material["scope_id"], created_at=NOW, producer=_PRODUCER, subject_id=material["subject_id"], scope_kind="organisation", label="registered entity"))
                seen_scopes.add(material["scope_id"])
        catalog.register_cohort({"record_id": plan.cohort_id, "cohort_code": "G4-O1C-REAL-FIVE", "definition_version": "1", "membership_hash": plan.plan_sha256, "budget_cap": {"amount": "0", "currency": "AUD"}, "created_at": now})
        catalog.register_run({"record_id": run_id, "cohort_id": plan.cohort_id, "run_kind": "g4_o1c_real_five_charity_provider_free_replay", "status": "planned", "configuration_hash": plan.plan_sha256, "created_at": now})
        provider = RehearsalFakeProvider()
        runner = ReferenceFactory(catalog, plan.factory_plan, cohort_id=plan.cohort_id, run_id=run_id, provider=provider, delivery_mode="standard")
        tasks = runner.seed(now)
        completed = runner.run(now)
        diagnostic = _diagnostic(catalog, run_id)
        with catalog._connection() as conn:
            attempts = int(conn.execute("SELECT COUNT(*) FROM task_attempts WHERE model_task_id IN (SELECT model_task_id FROM tasks WHERE run_id=?)", (run_id,)).fetchone()[0])
            actual = str(conn.execute("SELECT COALESCE(SUM(accounting_amount), '0') FROM cost_entries WHERE run_id=? AND entry_type='actual'", (run_id,)).fetchone()[0])
            released = str(conn.execute("SELECT COALESCE(SUM(accounting_amount), '0') FROM cost_entries WHERE run_id=? AND entry_type='reservation_release'", (run_id,)).fetchone()[0])
        return RealFiveCharityFactoryExecution(plan.cohort_id, run_id, len(tasks), completed, attempts, 0, actual, released, diagnostic.sha256)
    finally:
        catalog.close()


def replay_real_five_charity_factory(*, work_root: str | Path, evidence_root: str | Path = EVIDENCE_DIR, runtime_root: str | Path = RUNTIME_ROOT) -> dict[str, Any]:
    evidence = load_real_five_charity_evidence(evidence_root=evidence_root, runtime_root=runtime_root)
    plan = build_real_five_charity_factory_plan(evidence)
    first = execute_real_five_charity_factory(plan, work_root=work_root)
    second = execute_real_five_charity_factory(plan, work_root=work_root)
    stable = {
        "cohort_id": first.cohort_id, "run_id": first.run_id, "plan_sha256": plan.plan_sha256,
        "task_ids": list(plan.task_ids), "first_diagnostic_sha256": first.diagnostic_sha256,
        "second_diagnostic_sha256": second.diagnostic_sha256,
        "identities_and_diagnostics_stable": first.diagnostic_sha256 == second.diagnostic_sha256 and first.cohort_id == second.cohort_id and first.run_id == second.run_id,
    }
    return {
        "schema": SCHEMA, "created_on": "2026-11-03", "selected_manifest_sha256": evidence.selected_manifest_sha256,
        "preserved_input_sha256": dict(sorted(evidence.input_hashes.items())),
        "cohort": {"denominator": 10, "bound_count": evidence.binding.bound_count, "bound_register_ordinals": list(BOUND_ORDINALS), "missing_count": evidence.binding.missing_count, "missing_ais_ordinals": list(MISSING_AIS_ORDINALS), "blocked_count": 0, "provider_calls": 0, "publications": 0, "spend_aud": "0.00"},
        "binding": {"canonical_hash": evidence.binding.canonical_hash, "statuses": [{"ordinal": row.ordinal, "subject_id": row.subject_id, "scope_id": row.scope_id, "source_family": row.source_family, "source_record_id": row.source_record_id, "source_sha256": row.source_sha256, "representation_artifact_id": row.representation_artifact_id, "representation_sha256": row.representation_sha256, "acquisition_receipt_id": row.acquisition_receipt_id, "status": row.status, "reasons": list(row.reasons)} for row in evidence.binding.rows]},
        "factory": {"planned_tasks": len(plan.task_ids), "executed_tasks": first.completed_tasks, "attempts": first.attempt_count, "provider_send_tasks": [], "rights_distinct_from_provider_authority": True, "missing_provider_authority": "provider_call_authorized=false in every preserved exact rights decision"},
        "replay": {"first": first.__dict__, "second": second.__dict__, "stable": stable},
        "north_star_coverage": list(evidence.north_star_coverage), "source_silence_records": list(evidence.source_silence_records),
        "private_material_exclusion": {"metadata_only": True, "raw_source_bytes_in_artifact": False, "representation_bytes_in_artifact": False, "publisher_original_acnc_csv_claim": False, "representation_origin": "publicdata.au independent versioned API representation; not ACNC publisher original bytes"},
    }


def write_replay_artifact(path: str | Path, *, work_root: str | Path, evidence_root: str | Path = EVIDENCE_DIR, runtime_root: str | Path = RUNTIME_ROOT) -> dict[str, Any]:
    payload = replay_real_five_charity_factory(work_root=work_root, evidence_root=evidence_root, runtime_root=runtime_root)
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(canonical_json_bytes(payload) + b"\n")
    return payload


__all__ = [
    "AS_OF", "SCHEMA", "RealFiveCharityEvidence", "RealFiveCharityFactoryExecution", "RealFiveCharityFactoryPlan",
    "RealFiveCharityInputError", "build_real_five_charity_factory_plan", "execute_real_five_charity_factory",
    "load_real_five_charity_evidence", "preflight_real_five_charity_references", "replay_real_five_charity_factory",
    "write_replay_artifact",
]
