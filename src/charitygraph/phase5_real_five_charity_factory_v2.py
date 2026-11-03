"""Provider-free, metadata-only replay of the preserved Gate 4 five-charity slice."""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from .contracts import ArtifactRef, ProducerRef, SchemaRef, ScopeRecord, SubjectRecord
from .contracts.canonical import canonical_json_bytes, canonical_sha256
from .contracts.ids import deterministic_id
from .phase5_factory import FactoryPlan, ReferenceFactory
from .phase5_governed_factory_integration import (
    GovernedFactoryPreflight,
    GovernedReference,
    preflight_governed_references,
)
from .phase5_t3_source_evidence_binding import SourceEvidenceBindingResult, bind_acnc_source_evidence
from .runtime import SQLiteCatalog
from .source_rights import ArtifactRightsDecision


SCHEMA = "charitygraph.gate4.o1c.real-five-charity-factory-replay/v2"
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
_PRODUCER = ProducerRef(kind="code", producer_id="g4-o1c-real-five-charity-factory-v2", version="1")
_SCHEMA = SchemaRef(schema_id="urn:charitygraph:builder:schema:source-artefact:1.0", schema_version="1.0")


class RealFiveCharityInputError(ValueError):
    """Preserved evidence cannot be safely composed for replay."""


@dataclass(frozen=True)
class RealFiveCharityEvidence:
    binding: SourceEvidenceBindingResult
    references: tuple[GovernedReference, ...]
    materials: tuple[dict[str, Any], ...]
    retained_bytes: Mapping[str, bytes]
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
class ReplayExecution:
    cohort_id: str
    run_id: str
    task_count: int
    completed_tasks: int
    attempt_count: int
    provider_calls: int
    aud_actual: str
    aud_released: str
    diagnostic_sha256: str


def _json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RealFiveCharityInputError(f"cannot read preserved JSON: {path}") from exc
    if not isinstance(value, dict):
        raise RealFiveCharityInputError(f"preserved JSON root is not an object: {path}")
    return value


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _assert_hash(path: Path, expected: str) -> str:
    try:
        actual = _sha(path.read_bytes())
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
    if _sha(value) != expected:
        raise RealFiveCharityInputError(f"retained runtime bytes hash mismatch: {path}")
    return value


def _row_map(rows: Iterable[Mapping[str, Any]]) -> dict[int, dict[str, Any]]:
    result = {int(row["ordinal"]): dict(row) for row in rows}
    if tuple(sorted(result)) != tuple(range(1, 11)):
        raise RealFiveCharityInputError("the preserved cohort must contain ordinals 1 through 10")
    return result


def _provider_decision(axis: Mapping[str, Any], *, source_url: str, source_sha: str, receipt_id: str) -> ArtifactRightsDecision:
    return ArtifactRightsDecision.model_validate({
        "decision_id": axis["decision_id"],
        "source_artifact_id": axis["source_artifact_id"],
        "source_record_id": axis["source_record_id"],
        "source_origin_url": source_url,
        "source_role": "register_identity",
        "acquisition_lineage_ids": tuple(axis.get("acquisition_lineage_ids") or (receipt_id,)),
        "transmitted_representation_sha256": axis["representation_sha256"],
        "rights_policy_id": axis["policy_id"],
        "provider_processing_policy_id": axis["provider_policy_id"],
        "rights_basis": axis["rights_basis"],
        "evidence_locator": source_url,
        "evidence_sha256": source_sha,
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


def _coverage() -> tuple[dict[str, Any], ...]:
    titles = (
        "Identity / regulatory", "Purpose / cause", "Programs / services", "Activities / SDGs",
        "Geography / beneficiaries", "Participation", "Direct service / capacity", "Fundraising",
        "Governance / leadership", "People / workforce", "Scale / capability", "Relationships",
        "Finances", "Funding / dependencies", "Ethos / values", "Conduct / adverse",
        "Notable history", "Evaluation / outcomes", "Classification / search / AI discovery",
        "Evidence / coverage / freshness / corrections",
    )
    return tuple({
        "section_id": index, "title": title,
        "code": "P" if index == 1 else "S" if index == 20 else "M",
        "status": "partial" if index == 1 else "supported" if index == 20 else "unassessed",
        "basis": "observed_present" if index in {1, 20} else "not_reviewed",
    } for index, title in enumerate(titles, 1))


def _silence(subjects: Iterable[str], scopes: Mapping[str, str]) -> tuple[dict[str, Any], ...]:
    return tuple({
        "subject_id": subject_id, "scope_id": scopes[subject_id], "section_id": 20,
        "status": "source_silent",
        "assessment_basis": {"contract": "north-star-v0.3", "kind": "reviewed_source_silence"},
        "source_silence_is_not_absence": True,
    } for subject_id in sorted(subjects))


def load_real_five_charity_evidence(*, evidence_root: str | Path = EVIDENCE_DIR, runtime_root: str | Path = RUNTIME_ROOT) -> RealFiveCharityEvidence:
    root = Path(evidence_root)
    for name, expected in PRESERVED_INPUT_SHA256.items():
        _assert_hash(root / name, expected)
    manifest_path = root / "selected-binding-manifest.json"
    _assert_hash(manifest_path, SELECTED_MANIFEST_FILE_SHA256)
    manifest = _json(manifest_path)
    if manifest.get("selected_manifest_sha256") != SELECTED_MANIFEST_ID:
        raise RealFiveCharityInputError("selected-binding manifest identity is invalid")
    selected = _row_map(manifest.get("rows", ()))
    if len({row["subject_id"] for row in selected.values()}) != 5:
        raise RealFiveCharityInputError("selected-binding manifest does not preserve five subjects")

    first_binding = _json(root / "first-charity-publicdata-api-binding-20261026.json")
    first_rights = _json(root / "first-charity-publicdata-provider-rights-20261103.json")
    first_retention = _json(root / "first-charity-official-acnc-source-retention-v1.json")
    four_bindings = _json(root / "publicdata-20261026-four-charity-bindings.json")
    four_receipts = _json(root / "publicdata-20261026-four-charity-acquisition-receipts.json")
    four_rights = _json(root / "publicdata-20261026-four-charity-rights-decisions.json")
    expected_cohort = {"denominator": 10, "bound_count": 5, "bound_register_ordinals": list(BOUND_ORDINALS), "missing_count": 5, "missing_ais_ordinals": list(MISSING_AIS_ORDINALS), "blocked_count": 0, "provider_calls": 0, "publications": 0, "spend_aud": "0.00"}
    if four_bindings.get("cohort") != expected_cohort:
        raise RealFiveCharityInputError("preserved four-charity artifact does not carry five BOUND/five MISSING")

    first_rows = _row_map(first_binding["binding_result"]["rows"])
    four_binding_rows = {int(row["ordinal"]): dict(row) for row in four_bindings["binding_result"]["rows"]}
    four_receipt_rows = {int(row["ordinal"]): dict(row) for row in four_receipts["rows"]}
    four_right_rows = {int(row["ordinal"]): dict(row) for row in four_rights["rows"]}
    retained: dict[str, bytes] = {}
    materials: list[dict[str, Any]] = []
    runtime = Path(runtime_root)
    for ordinal in BOUND_ORDINALS:
        if ordinal == 1:
            retention = first_retention["retention"]
            source, acquisition, representation = retention["source_record"], retention["acquisition_receipt"], retention["representation"]
            rights_axis = first_rights["rights_decision"]
            binding_row = first_rows[1]
            abn, name = first_rights["target"]["abn"], first_rights["target"]["name"]
            raw_path = runtime / "g4-o1c-publicdata-acnc-register-20261103" / "raw-response.json"
            rep_path = runtime / "g4-o1c-publicdata-acnc-register-20261103" / "normalized-representation.json"
            source_definition_id, acquired_at = first_rights["source"]["definition_id"], acquisition["received_at_utc"]
            local_rights = retention["local_retention_decision"]
        else:
            receipt_row = four_receipt_rows[ordinal]
            source, acquisition, representation = receipt_row["source_record"], receipt_row["acquisition_receipt"], receipt_row["representation"]
            rights_axis = four_right_rows[ordinal]["private_provider_processing"]
            binding_row = four_binding_rows[ordinal]
            abn, name = receipt_row["abn"], receipt_row["name"]
            raw_path, rep_path = Path(receipt_row["raw_runtime_path"]), Path(receipt_row["representation_runtime_path"])
            source_definition_id, acquired_at = receipt_row["source_definition_id"], receipt_row["acquired_at_utc"]
            local_rights = receipt_row["local_retention_decision"]
        subject_id, scope_id = selected[ordinal]["subject_id"], selected[ordinal]["scope_id"]
        if binding_row["subject_id"] != subject_id or binding_row["scope_id"] != scope_id:
            raise RealFiveCharityInputError(f"ordinal {ordinal} moved subject or scope")
        source_sha = str(source.get("payload_hash", source.get("sha256")))
        representation_sha = str(representation.get("content_hash", representation.get("sha256")))
        raw, rep = _runtime_bytes(raw_path, source_sha), _runtime_bytes(rep_path, representation_sha)
        if source["id"] != binding_row["source_record_id"] or representation["artifact_id"] != binding_row["representation_artifact_id"]:
            raise RealFiveCharityInputError(f"ordinal {ordinal} source/representation identity mismatch")
        if representation.get("source_artifact_id") != source.get("payload_ref") or representation.get("source_record_id") != source["id"]:
            raise RealFiveCharityInputError(f"ordinal {ordinal} representation lineage mismatch")
        if rights_axis["source_record_id"] != source["id"] or rights_axis["representation_artifact_id"] != representation["artifact_id"] or rights_axis["representation_sha256"] != representation_sha or rights_axis.get("provider_call_authorized") is not False:
            raise RealFiveCharityInputError(f"ordinal {ordinal} invalid exact rights decision")
        receipt_id = acquisition.get("id", acquisition.get("acquisition_receipt_id"))
        if receipt_id != binding_row["acquisition_receipt_id"] or acquisition.get("content_hash") != source_sha or acquisition.get("artifact_id") != source.get("payload_ref") or acquisition.get("outcome") != "available":
            raise RealFiveCharityInputError(f"ordinal {ordinal} acquisition receipt mismatch")
        origin = str(representation.get("representation_origin", representation.get("origin", ""))).lower()
        publisher_original = (representation.get("source_provenance") or {}).get("publisher_original_bytes")
        if publisher_original is not False and not any(token in origin for token in ("not acnc publisher original", "not_acnc_publisher", "third_party_api_representation", "independent republication")):
            raise RealFiveCharityInputError(f"ordinal {ordinal} publisher-original representation claim was not excluded")
        retained[source["payload_ref"]], retained[representation["artifact_id"]] = raw, rep
        materials.append({
            "ordinal": ordinal, "abn": abn, "name": name, "subject_id": subject_id, "scope_id": scope_id,
            "source_definition_id": source_definition_id, "source_record": dict(source), "acquisition_receipt": dict(acquisition),
            "representation": dict(representation), "local_retention_decision": dict(local_rights), "provider_rights_decision": dict(rights_axis),
            "source_url": source["source_locator"], "source_sha256": source_sha, "representation_sha256": representation_sha,
            "source_artifact_id": source["payload_ref"], "representation_artifact_id": representation["artifact_id"],
            "receipt_id": receipt_id, "evidence_locator_id": binding_row.get("evidence_locator_id") or representation.get("evidence_locator_ids", [None])[0],
        })

    binder_rows = [first_rows[1], first_rows[2]] + [four_binding_rows[ordinal] for ordinal in range(3, 11)]
    existing = {key: [] for key in ("subjects", "scopes", "source_definitions", "source_records", "acquisition_receipts", "representations", "rights_decisions")}
    subjects, scopes, definitions = set(), set(), set()
    for material in materials:
        if material["subject_id"] not in subjects:
            existing["subjects"].append({"id": material["subject_id"], "subject_id": material["subject_id"]})
            subjects.add(material["subject_id"])
        if material["scope_id"] not in scopes:
            existing["scopes"].append({"id": material["scope_id"], "scope_id": material["scope_id"], "subject_id": material["subject_id"]})
            scopes.add(material["scope_id"])
        if material["source_definition_id"] not in definitions:
            existing["source_definitions"].append({"id": material["source_definition_id"], "source_definition_id": material["source_definition_id"]})
            definitions.add(material["source_definition_id"])
        existing["source_records"].append(material["source_record"])
        existing["acquisition_receipts"].append(material["acquisition_receipt"])
        existing["representations"].append(material["representation"])
        existing["rights_decisions"].extend((material["local_retention_decision"], material["provider_rights_decision"]))
    binding = bind_acnc_source_evidence({"schema": manifest["schema"], "source_universe_version": "v1", "selected_manifest_sha256": SELECTED_MANIFEST_ID, "rows": binder_rows}, existing=existing, retained_bytes=retained, as_of=AS_OF, require_five_subject_ten_rows=True)
    if binding.bound_count != 5 or binding.missing_count != 5 or [row.ordinal for row in binding.rows if row.status == "BOUND"] != list(BOUND_ORDINALS):
        raise RealFiveCharityInputError("T3 binder did not reproduce five BOUND and five MISSING rows")
    references = tuple(row.governed_reference.model_copy(update={"provider_processing_policy_id": None, "provider_processing_policy_version": None}) for row in binding.rows if row.governed_reference is not None)
    if len(references) != 5:
        raise RealFiveCharityInputError("T3 binder did not lower all five bound rows")
    scopes_by_subject = {item["subject_id"]: item["scope_id"] for item in materials}
    return RealFiveCharityEvidence(binding, references, tuple(materials), retained, {**PRESERVED_INPUT_SHA256, "selected-binding-manifest.json": SELECTED_MANIFEST_FILE_SHA256}, _coverage(), _silence(subjects, scopes_by_subject))


def _subject(material: Mapping[str, Any]) -> SubjectRecord:
    return SubjectRecord(record_id=deterministic_id("subjectrecord:", {"subject_id": material["subject_id"], "source_artifact_id": material["source_artifact_id"]}), created_at=NOW, producer=_PRODUCER, subject_id=material["subject_id"], subject_kind="legal_entity", lifecycle_status="active", display_name=material["name"], external_identifiers=({"scheme": "ABN", "value": material["abn"], "issuing_authority": "Australian Business Register"},), identity_authority_refs=(ArtifactRef(artifact_id=material["source_artifact_id"], content_hash=material["source_sha256"], schema=_SCHEMA),), identity_policy_id="acnc-registered-charity-bootstrap-v1")


def _metadata_catalog(evidence: RealFiveCharityEvidence) -> dict[str, Any]:
    catalog = {key: {} for key in ("subjects", "scopes", "source_definitions", "receipts", "sources", "artifacts", "lineage", "locators", "rights")}
    for material in evidence.materials:
        catalog["subjects"][material["subject_id"]] = _subject(material).model_dump(mode="json")
        catalog["scopes"][material["scope_id"]] = {"scope_id": material["scope_id"], "subject_id": material["subject_id"]}
        catalog["source_definitions"][material["source_definition_id"]] = {"source_definition_id": material["source_definition_id"]}
        catalog["receipts"][material["receipt_id"]] = {"id": material["receipt_id"], "source_definition_id": material["source_definition_id"], "artifact_id": material["source_artifact_id"], "content_hash": material["source_sha256"], "outcome": "available"}
        source = material["source_record"]
        catalog["sources"][source["id"]] = {**source, "material": source}
        catalog["artifacts"][material["source_artifact_id"]] = {"artifact_id": material["source_artifact_id"], "content_hash": material["source_sha256"], "availability": "available"}
        catalog["artifacts"][material["representation_artifact_id"]] = {"artifact_id": material["representation_artifact_id"], "content_hash": material["representation_sha256"], "availability": "available"}
        catalog["lineage"][material["representation_artifact_id"]] = [{"input_artifact_id": material["source_artifact_id"]}]
        catalog["locators"][material["evidence_locator_id"]] = {"artifact_id": material["representation_artifact_id"], "material_hash": material["representation_sha256"]}
        decision = _provider_decision(material["provider_rights_decision"], source_url=material["source_url"], source_sha=material["source_sha256"], receipt_id=material["receipt_id"])
        catalog["rights"][material["representation_artifact_id"]] = [{"decision_id": decision.decision_id, "rights_policy_id": decision.rights_policy_id, "rights_policy_version": decision.rights_policy_version, "material_json": json.dumps({"decision": decision.model_dump(mode="json")}, sort_keys=True)}]
    return catalog


class _MetadataCatalog:
    def __init__(self, values: Mapping[str, Any]): self.values, self.diagnostics = values, []
    def get_subject(self, key: str): return self.values["subjects"].get(key)
    def get_scope(self, key: str): return self.values["scopes"].get(key)
    def get_source_definition(self, key: str): return self.values["source_definitions"].get(key)
    def get_acquisition_receipt(self, key: str): return self.values["receipts"].get(key)
    def get_source_record(self, key: str): return self.values["sources"].get(key)
    def get_artifact(self, key: str): return self.values["artifacts"].get(key)
    def get_artifact_lineage(self, key: str): return self.values["lineage"].get(key, [])
    def get_evidence_locator(self, key: str): return self.values["locators"].get(key)
    def get_artifact_rights_decisions(self, keys): return [row for rows in self.values["rights"].values() for row in rows if row["decision_id"] in set(keys)]
    def list_artifact_rights_decisions(self, *, representation_artifact_id: str): return self.values["rights"].get(representation_artifact_id, [])
    def record_provider_rights_diagnostic(self, **kwargs): self.diagnostics.append(kwargs)


def preflight_real_five_charity_references(evidence: RealFiveCharityEvidence, references: Iterable[GovernedReference] | None = None) -> GovernedFactoryPreflight:
    catalog = _MetadataCatalog(_metadata_catalog(evidence))
    return preflight_governed_references(tuple(evidence.references if references is None else references), catalog=catalog, retained_bytes=lambda artifact_id: evidence.retained_bytes[artifact_id], build_id="g4-o1c-real-five-charity-factory-v2", route_policy_version="g4-o1c-real-five-charity-factory-route-v2", planned_processing_at=NOW)


def build_real_five_charity_factory_plan(evidence: RealFiveCharityEvidence) -> RealFiveCharityFactoryPlan:
    preflight = preflight_real_five_charity_references(evidence)
    if preflight.diagnostics or preflight.accepted_count != 5:
        raise RealFiveCharityInputError("governed preflight did not accept exactly five local tasks")
    if any(task["difficulty"] != "deterministic" for task in preflight.tasks):
        raise RealFiveCharityInputError("provider authority is missing; non-deterministic send task was proposed")
    # Keep governed identities, but omit typed evidence payloads from the Factory
    # runtime registration.  The replay is metadata-only and local.
    tasks = [{key: value for key, value in task.items() if key != "_model_task"} for task in preflight.tasks]
    factory_plan = FactoryPlan.from_manifest(tasks)
    plan_payload = {"schema": SCHEMA, "selected_manifest_sha256": evidence.input_hashes["selected-binding-manifest.json"], "task_ids": list(factory_plan.logical_tasks), "coverage": list(evidence.north_star_coverage), "source_silence_records": list(evidence.source_silence_records)}
    plan_sha = canonical_sha256(plan_payload)
    return RealFiveCharityFactoryPlan(evidence, preflight, factory_plan, deterministic_id("cohort:", {"plan_sha256": plan_sha}), plan_sha)


class _NoSendProvider:
    tariffs = {"standard": "0.000000", "batch": "0.000000", "flex": "0.000000"}
    def execute(self, *args, **kwargs): raise AssertionError("provider transmission is forbidden in this replay")
    def execute_package(self, *args, **kwargs): raise AssertionError("provider transmission is forbidden in this replay")
    def receipt_for_package(self, *args, **kwargs): raise AssertionError("provider reconciliation is forbidden in this replay")


def _diagnostic(catalog: SQLiteCatalog, run_id: str) -> str:
    with catalog._connection() as conn:
        tasks = [dict(row) for row in conn.execute("SELECT model_task_id, subject_id, scope_id, status, attempt_count FROM tasks WHERE run_id=? ORDER BY model_task_id", (run_id,))]
        attempts = [dict(row) for row in conn.execute("SELECT task_run_id, model_task_id, status FROM task_attempts WHERE model_task_id IN (SELECT model_task_id FROM tasks WHERE run_id=?) ORDER BY task_run_id", (run_id,))]
        receipts = int(conn.execute("SELECT COUNT(*) FROM provider_receipts pr JOIN physical_attempts pa ON pa.physical_attempt_id=pr.physical_attempt_id WHERE pa.run_id=?", (run_id,)).fetchone()[0])
    return canonical_sha256({"run_id": run_id, "tasks": tasks, "attempts": attempts, "provider_receipts": receipts})


def execute_real_five_charity_factory(plan: RealFiveCharityFactoryPlan, *, work_root: str | Path, now: datetime = NOW) -> ReplayExecution:
    catalog = SQLiteCatalog(Path(work_root) / "catalog.sqlite3").open(initialize=True)
    try:
        run_id = deterministic_id("run:", {"cohort_id": plan.cohort_id, "plan_sha256": plan.plan_sha256})
        seen_subjects, seen_scopes = set(), set()
        for material in plan.evidence.materials:
            if material["subject_id"] not in seen_subjects:
                catalog.register_subject(_subject(material)); seen_subjects.add(material["subject_id"])
            if material["scope_id"] not in seen_scopes:
                catalog.register_scope(ScopeRecord(record_id=material["scope_id"], created_at=NOW, producer=_PRODUCER, subject_id=material["subject_id"], scope_kind="organisation", label="registered entity")); seen_scopes.add(material["scope_id"])
        catalog.register_cohort({"record_id": plan.cohort_id, "cohort_code": "G4-O1C-REAL-FIVE-V2", "definition_version": "1", "membership_hash": plan.plan_sha256, "budget_cap": {"amount": "0", "currency": "AUD"}, "created_at": now})
        catalog.register_run({"record_id": run_id, "cohort_id": plan.cohort_id, "run_kind": "g4_o1c_real_five_charity_provider_free_replay_v2", "status": "planned", "configuration_hash": plan.plan_sha256, "created_at": now})
        runner = ReferenceFactory(catalog, plan.factory_plan, cohort_id=plan.cohort_id, run_id=run_id, provider=_NoSendProvider(), delivery_mode="standard")
        tasks = runner.seed(now)
        completed = runner.run(now)
        diagnostic = _diagnostic(catalog, run_id)
        with catalog._connection() as conn:
            attempts = int(conn.execute("SELECT COUNT(*) FROM task_attempts WHERE model_task_id IN (SELECT model_task_id FROM tasks WHERE run_id=?)", (run_id,)).fetchone()[0])
            receipts = int(conn.execute("SELECT COUNT(*) FROM provider_receipts pr JOIN physical_attempts pa ON pa.physical_attempt_id=pr.physical_attempt_id WHERE pa.run_id=?", (run_id,)).fetchone()[0])
        return ReplayExecution(plan.cohort_id, run_id, len(tasks), completed, attempts, receipts, "0.00", "0.00", diagnostic)
    finally:
        catalog.close()


def replay_real_five_charity_factory_v2(*, work_root: str | Path, evidence_root: str | Path = EVIDENCE_DIR, runtime_root: str | Path = RUNTIME_ROOT) -> dict[str, Any]:
    evidence = load_real_five_charity_evidence(evidence_root=evidence_root, runtime_root=runtime_root)
    plan = build_real_five_charity_factory_plan(evidence)
    first, second = execute_real_five_charity_factory(plan, work_root=work_root), execute_real_five_charity_factory(plan, work_root=work_root)
    stable = {"cohort_id": first.cohort_id, "run_id": first.run_id, "plan_sha256": plan.plan_sha256, "task_ids": list(plan.task_ids), "first_diagnostic_sha256": first.diagnostic_sha256, "second_diagnostic_sha256": second.diagnostic_sha256, "identities_and_diagnostics_stable": first.cohort_id == second.cohort_id and first.run_id == second.run_id and first.diagnostic_sha256 == second.diagnostic_sha256 and first.attempt_count == second.attempt_count and first.provider_calls == second.provider_calls}
    statuses = [{"ordinal": row.ordinal, "subject_id": row.subject_id, "scope_id": row.scope_id, "status": row.status, "source_identity": {"source_record_id": row.source_record_id, "source_artifact_id": row.source_artifact_id, "source_sha256": row.source_sha256, "acquisition_receipt_id": row.acquisition_receipt_id}, "representation_identity": {"representation_artifact_id": row.representation_artifact_id, "representation_sha256": row.representation_sha256}, "reasons": list(row.reasons)} for row in evidence.binding.rows]
    return {"schema": SCHEMA, "created_on": "2026-11-03", "selected_manifest_sha256": SELECTED_MANIFEST_ID, "preserved_input_sha256": dict(sorted(evidence.input_hashes.items())), "cohort": {"denominator": 10, "bound_count": evidence.binding.bound_count, "bound_register_ordinals": list(BOUND_ORDINALS), "missing_count": evidence.binding.missing_count, "missing_ais_ordinals": list(MISSING_AIS_ORDINALS), "blocked_count": 0, "provider_calls": 0, "publications": 0, "spend_aud": "0.00"}, "binding": {"canonical_hash": evidence.binding.canonical_hash, "statuses": statuses}, "factory": {"planned_tasks": first.task_count, "executed_tasks": first.completed_tasks, "second_run_executed_tasks": second.completed_tasks, "attempts": second.attempt_count, "provider_send_tasks": [], "provider_calls": 0, "rights_distinct_from_provider_authority": True, "missing_provider_authority": "provider_call_authorized=false in every preserved exact rights decision"}, "replay": {"first": asdict(first), "second": asdict(second), "stable": stable}, "north_star_coverage": list(evidence.north_star_coverage), "source_silence_records": list(evidence.source_silence_records), "private_material_exclusion": {"metadata_only": True, "raw_source_bytes_in_artifact": False, "representation_bytes_in_artifact": False, "publisher_original_acnc_csv_claim": False}}


def write_replay_artifact(path: str | Path, *, work_root: str | Path, evidence_root: str | Path = EVIDENCE_DIR, runtime_root: str | Path = RUNTIME_ROOT) -> dict[str, Any]:
    payload = replay_real_five_charity_factory_v2(work_root=work_root, evidence_root=evidence_root, runtime_root=runtime_root)
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(canonical_json_bytes(payload) + b"\n")
    return payload


replay_real_five_charity_factory = replay_real_five_charity_factory_v2


__all__ = ["AS_OF", "SCHEMA", "RealFiveCharityEvidence", "RealFiveCharityFactoryPlan", "RealFiveCharityInputError", "build_real_five_charity_factory_plan", "execute_real_five_charity_factory", "load_real_five_charity_evidence", "preflight_real_five_charity_references", "replay_real_five_charity_factory", "replay_real_five_charity_factory_v2", "write_replay_artifact"]
