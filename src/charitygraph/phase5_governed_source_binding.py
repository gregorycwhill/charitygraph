"""Bounded, provider-free Gate 4 T3 source binding.

This module consumes only the ten previously retained ACNC objects named by
the T3 review.  It copies no source body into the emitted manifest.  The
temporary catalogue and private rights store are disposable verification
state; the committed v29 projection remains unchanged.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .contracts import (
    AcquisitionReceipt,
    ArtifactRef,
    ExternalIdentifier,
    PropositionAuthorityRole,
    ProducerRef,
    SchemaRef,
    ScopeRecord,
    SourceDefinition,
    SourceRecord,
    StructuredFieldLocator,
    SubjectRecord,
)
from .contracts.canonical import canonical_json_bytes
from .contracts.ids import deterministic_id
from .evidence_store import ContentAddressedArtifactStore
from .phase5_governed_rights_preflight import (
    RightsPreflightReference,
    preflight_governed_rights,
)
from .runtime import SQLiteCatalog
from .runtime.rights_governance_projection import RightsGovernanceProjection
from .runtime.rights_governance_record import (
    INTERNAL_PRIVATE_USE_POLICY,
    INTERNAL_PRIVATE_USE_POLICY_ID,
    INTERNAL_PRIVATE_USE_POLICY_VERSION,
    RightsAxis,
    RightsGovernanceEvent,
    RightsGovernanceRecord,
    RightsGovernanceStore,
)


SELECTED_MANIFEST_SHA256 = "41b4ce5f1c39afd31a28b1f819d2a9759c89880eb0ddb2d2b143662cf4dda7a9"
SOURCE_EVIDENCE_PROVENANCE_EPOCH = "v45"
SOURCE_EVIDENCE_PROVENANCE_REVISION = "61dd0cd1a89ed22118fc81bab89611eb1ddb2428"
AS_OF = date(2026, 10, 29)
RECORDED_AT = datetime(2026, 10, 29, tzinfo=timezone.utc)
_PRODUCER = ProducerRef(kind="code", producer_id="g4-t3-governed-source-binding", version="1")
_SOURCE_SCHEMA = SchemaRef(
    schema_id="urn:charitygraph:builder:schema:source-artefact:1.0", schema_version="1.0"
)
_REPRESENTATION_SCHEMA_ID = "urn:charitygraph:builder:schema:acnc-source-native-representation:1.0"


@dataclass(frozen=True)
class CandidateRow:
    ordinal: int
    abn: str
    subject_id: str
    source_family: str
    source_role: str
    source_definition_id: str
    source_record_id: str
    source_artifact_id: str
    source_sha256: str
    acquisition_receipt_id: str
    source_locator: str
    byte_size: int


@dataclass(frozen=True)
class ExclusionEvidence:
    material: str
    authority: str
    wording: str
    affected_operation: str


@dataclass(frozen=True)
class BindingBuildResult:
    manifest: dict[str, Any]
    manifest_bytes: bytes
    projection_snapshot_hash: str
    preflight_task_count: int
    downstream_task_count: int


def _row(
    ordinal: int,
    abn: str,
    subject_id: str,
    family: str,
    role: str,
    definition: str,
    source_record: str,
    source_hash: str,
    receipt: str,
    locator: str,
    byte_size: int,
) -> CandidateRow:
    return CandidateRow(
        ordinal=ordinal,
        abn=abn,
        subject_id=subject_id,
        source_family=family,
        source_role=role,
        source_definition_id=definition,
        source_record_id=source_record,
        source_artifact_id=f"srcblob:{source_hash}",
        source_sha256=source_hash,
        acquisition_receipt_id=receipt,
        source_locator=locator,
        byte_size=byte_size,
    )


# Exact rows from the retained T3 assessment.  These are identifiers and
# receipts only; source bodies are deliberately not represented here.
SELECTED_ROWS: tuple[CandidateRow, ...] = (
    _row(1, "52000399744", "subject:02649cdcb42049bb8dedd30f2333e150", "acnc_register", "register_identity", "srcdef:2463ab8e24d12fca25743d02ec3854a9d06e937cce166ba28800f35b575f92dc", "srcrec:4978c7ff7f9694d9d9d6db9ad871a8048cde5940c6e699a2dd4bd15360bcd28d", "f7b0522efbf6253cfa13713750a96100c601fd801fd209524f948dc134f0ada2", "acq:0b099288968c5ac89fc4bff0811f021787281fb38737565221c506123098b63e", "https://www.acnc.gov.au/api/dynamics/entity/9135e20f-39af-e811-a963-000d3ad24077", 45735),
    _row(2, "52000399744", "subject:02649cdcb42049bb8dedd30f2333e150", "acnc_ais_bundle", "annual_information_statement", "srcdef:4225a08bdf02ae76fcd25ef3495ecd56c961f43338fb2249d05876da4472502f", "srcrec:554fa9df1414f0096b9035fea5ac5eee7ffb59e46eb767d6306d40d8f326f08a", "70734f7c268aba097a37ab30c75640aca151583c2d616004cc90dffc0e878f1b", "acq:e094f723f29b2d0394805ee00d0c1f5cdce483d96c2dee14ca7ea4c1da69eac4", "https://www.acnc.gov.au/api/dynamics/entity/4bb2d097-69dc-f011-8544-6045bde73a73", 23515),
    _row(3, "26164251245", "subject:0889b4decb854e71ab4784479ca95c03", "acnc_register", "register_identity", "srcdef:2463ab8e24d12fca25743d02ec3854a9d06e937cce166ba28800f35b575f92dc", "srcrec:f05f137023221378d486eef96e0c4efe377bb4811ac63fbbbb9aa8f103c251d2", "8382a8ca22b00b71244664d85d6db3d0bdc1bafa40192ffb437e6227c4234773", "acq:fbb55f0fb70eecd14aa98017f1fc4b458c2522adde0c79a03237ac76e11ad05b", "https://www.acnc.gov.au/api/dynamics/entity/11f49bf3-39af-e811-a962-000d3ad24a0d", 32443),
    _row(4, "26164251245", "subject:0889b4decb854e71ab4784479ca95c03", "acnc_ais_bundle", "annual_information_statement", "srcdef:4225a08bdf02ae76fcd25ef3495ecd56c961f43338fb2249d05876da4472502f", "srcrec:045161751edf9950655698373906590d67abf2c35ba33dd804b61b3ac95237f8", "ea9b75510efe03a1ef829bb5e044988de371d133c3bedbedb060914be438ab33", "acq:c60f2a53e31086b4dfab8fbced7e1b0718a64e6694f8dcd6cd93eaffc2ef1c09", "https://www.acnc.gov.au/api/dynamics/entity/45964bd3-e7a1-f111-b8db-00224898b161", 11366),
    _row(5, "52404606134", "subject:16fba76fde2242d5870835b18b4e8b8d", "acnc_register", "register_identity", "srcdef:2463ab8e24d12fca25743d02ec3854a9d06e937cce166ba28800f35b575f92dc", "srcrec:188a391cee048ab2fa7720aeb2c58f5b1e025039ef674ef8a6fd6ea0ab91dd8a", "ead4a76bbbd9ad9aa29d79e82219b707d28f34d5232b00311544b8e6424f925c", "acq:8cbf097d3ca6a8a0282158d7980d965b9b715886d01d9146b41ebc57c4115637", "https://www.acnc.gov.au/api/dynamics/entity/5db14bda-0ca2-e911-a986-000d3ad02a61", 21192),
    _row(6, "52404606134", "subject:16fba76fde2242d5870835b18b4e8b8d", "acnc_ais_bundle", "annual_information_statement", "srcdef:4225a08bdf02ae76fcd25ef3495ecd56c961f43338fb2249d05876da4472502f", "srcrec:5cc396995aea23edbab90c78b47101651f3a085f34ab088417dc3e1caa6fda25", "9649487585e0267792c3b9c7ffa36261f0a5e93e69e87cac3e7f8154622e9678", "acq:0d954180bc7c8e26f48f1788164c9b2c900d7bcc43cff8d043944e68bd99bc18", "https://www.acnc.gov.au/api/dynamics/entity/c8bb832a-ced0-f011-bbd3-6045bde73edb", 14145),
    _row(7, "33107782196", "subject:1823309bdd06417c9928033603cb6e39", "acnc_register", "register_identity", "srcdef:2463ab8e24d12fca25743d02ec3854a9d06e937cce166ba28800f35b575f92dc", "srcrec:5e1c9ac1b0378a22557a9bf804697719133663123e7f603d76eb41fd2601adf4", "1ba64e644b28ff4528f6b075d42babb34ad5ee66fa9ce78110077ceef45170e6", "acq:fc6227ca5e16e8232088ef98cac3089927b208c3b35e236958dac9171a6bf960", "https://www.acnc.gov.au/api/dynamics/entity/643aab38-38af-e811-a960-000d3ad24282", 47729),
    _row(8, "33107782196", "subject:1823309bdd06417c9928033603cb6e39", "acnc_ais_bundle", "annual_information_statement", "srcdef:4225a08bdf02ae76fcd25ef3495ecd56c961f43338fb2249d05876da4472502f", "srcrec:e94d13fec302f9cefc42569b4d191dae5b360565c8c3d8b4e1cded8ece5c0c52", "692829d7188a787f2df3b91df982a2de34e6c86787b19d31d202737a072e07eb", "acq:64bd0dd82ff9fb56adf6ecf7f6f2612c3e0d27b358b7ffe74c453360ed6f1393", "https://www.acnc.gov.au/api/dynamics/entity/94eb5b28-42d9-f011-8544-6045bde61b96", 23859),
    _row(9, "82147006639", "subject:1a9ec5de3fc043ff9226fb95a6cae31b", "acnc_register", "register_identity", "srcdef:2463ab8e24d12fca25743d02ec3854a9d06e937cce166ba28800f35b575f92dc", "srcrec:e6529d39e4cf32248a4792142cdc5e5bfb5cb45c5055180f35662344c737544c", "a0f9c00f981fe7724262474f10212e08d3a775884055001181b06664c7eac74c", "acq:842d49f9b58861da7dd3882c6a6bb30859dbdfb16c37697b912abc338d1efed2", "https://www.acnc.gov.au/api/dynamics/entity/b0597a12-2caf-e811-a95e-000d3ad24c60", 42216),
    _row(10, "82147006639", "subject:1a9ec5de3fc043ff9226fb95a6cae31b", "acnc_ais_bundle", "annual_information_statement", "srcdef:4225a08bdf02ae76fcd25ef3495ecd56c961f43338fb2249d05876da4472502f", "srcrec:39443daa20d28eadd1164573c635a5c0aa2d89d3b7a8753b14f8321b90f4aea9", "b02a4079bd2ac8316123ad9ad7ff8cf9dfe3bf8832ac22bef6b2133d963f0b7f", "acq:e7f6a062e1f2e1f799a0e22fe186ba660421ffa32bb27387c5cf3efc9c075da13", "https://www.acnc.gov.au/api/dynamics/entity/7ef5b4ba-5068-f111-a826-6045bde523ce", 18373),
)


def _definition(row: CandidateRow) -> SourceDefinition:
    locator = (
        "https://www.acnc.gov.au/api/dynamics/entity"
        if row.source_family == "acnc_register"
        else "https://www.acnc.gov.au/api/dynamics/entity/{AISId}"
    )
    role = "registered entity identity" if row.source_family == "acnc_register" else "source-native annual information statement"
    return SourceDefinition(
        record_id=row.source_definition_id,
        created_at=RECORDED_AT,
        producer=_PRODUCER,
        definition_version="1",
        publisher="Australian Charities and Not-for-profits Commission",
        source_class=row.source_family,
        authority_roles=(PropositionAuthorityRole(proposition="registered entity", role=role),),
        acquisition_locator=locator,
        temporal_semantics="retrieved source material or source-native reporting period",
        publication_eligibility="private_review_only",
        steward="CharityGraph source governance",
        rights_policy_id=INTERNAL_PRIVATE_USE_POLICY_ID,
    )


def _scope_id(subject_id: str) -> str:
    return deterministic_id("scope:", {"subject_id": subject_id, "scope_kind": "registered_entity", "authority": "ACNC"})


def _subject_record(row: CandidateRow) -> SubjectRecord:
    return SubjectRecord(
        record_id=deterministic_id("subjectrecord:", {"subject_id": row.subject_id, "authority": "ACNC", "source_record_id": row.source_record_id}),
        created_at=RECORDED_AT,
        producer=_PRODUCER,
        subject_id=row.subject_id,
        subject_kind="legal_entity",
        lifecycle_status="active",
        display_name=None,
        external_identifiers=(ExternalIdentifier(scheme="ABN", value=row.abn, issuing_authority="Australian Business Register", source_record_ids=(row.source_record_id,)),),
        identity_authority_refs=(ArtifactRef(artifact_id=row.source_artifact_id, content_hash=row.source_sha256, schema=_SOURCE_SCHEMA),),
        identity_policy_id="acnc-registered-charity-bootstrap-v1",
    )


def _rights_record(row: CandidateRow, scope_id: str, representation_hash: str) -> RightsGovernanceRecord:
    return RightsGovernanceRecord(
        decision_id=f"rights:g4-t3:{row.ordinal:02d}",
        source_artifact_id=row.source_artifact_id,
        source_record_id=row.source_record_id,
        subject_id=row.subject_id,
        source_origin_url=row.source_locator,
        source_role=row.source_role,
        acquisition_lineage_ids=(row.acquisition_receipt_id,),
        representation_artifact_id=f"artifact:{representation_hash}",
        representation_sha256=representation_hash,
        rights_basis="public_source_private_processing",
        rights_policy_id=INTERNAL_PRIVATE_USE_POLICY_ID,
        rights_policy_version=INTERNAL_PRIVATE_USE_POLICY_VERSION,
        purpose="semantic_analysis",
        scope=scope_id,
        evidence_locator=row.source_locator,
        evidence_sha256=row.source_sha256,
        assessed_on=AS_OF,
        local_retention=RightsAxis(
            status="authorized",
            policy_id=INTERNAL_PRIVATE_USE_POLICY_ID,
            policy_version=INTERNAL_PRIVATE_USE_POLICY_VERSION,
            decision_id=f"rights:g4-t3:{row.ordinal:02d}:local-retention",
        ),
        provider_transmission=RightsAxis(status="blocked"),
        public_redistribution=RightsAxis(status="not_assessed"),
        status="authorized",
        review_status="current",
        actor_kind="human",
        actor_id="actor:gregory-product-owner-2026-10-29",
        actor_version="po-direction-2026-10-29",
        recorded_at=RECORDED_AT,
        attribution="Australian Charities and Not-for-profits Commission",
        restrictions=(
            "Private internal analysis only under Product Owner project authority; "
            "this is not a third-party licence; provider processing requires a "
            "separately bound provider contract; public redistribution was not assessed."
        ),
        assessment_notes=(
            f"{INTERNAL_PRIVATE_USE_POLICY.provenance}; "
            f"authority={INTERNAL_PRIVATE_USE_POLICY.authority_actor}; "
            f"basis={INTERNAL_PRIVATE_USE_POLICY.authority_basis}; "
            f"decision={INTERNAL_PRIVATE_USE_POLICY.decision_reference}; "
            "no concrete applicable explicit exclusion was supplied for this row."
        ),
        representation_class="structured_factual",
        factual_representation_only=True,
        publicly_accessible_without_circumvention=True,
        access_controls_bypassed=False,
        lawfully_acquired=True,
        lawful_access_confirmed=True,
        analytical_purpose="semantic_analysis",
        explicit_prohibition_found=False,
        provider_no_training_default=False,
        provider_data_sharing_opt_in=None,
        one_source_native_entity_record=True,
        circumvention_used=False,
        retention_lifecycle_status="active_until_review",
        retention_review_due_on=date(2027, 10, 29),
    )


def _canonical_manifest_bytes(manifest: dict[str, Any]) -> bytes:
    return (json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def build_selected_binding_manifest(
    *,
    source_archive_root: str | Path,
    work_root: str | Path,
    execution_context: Mapping[str, str],
    selected_manifest_sha256: str = SELECTED_MANIFEST_SHA256,
    as_of: date = AS_OF,
    exclusions: Mapping[int, ExclusionEvidence] | None = None,
) -> BindingBuildResult:
    """Bind the fixed ten-row cohort in disposable local state.

    ``source_archive_root`` must be an already retained content-addressed
    archive root.  No acquisition or provider seam is available here.  An
    exclusion is accepted only when its material, authority, exact wording,
    and affected operation are all supplied; it lowers that row to zero work.
    """

    if selected_manifest_sha256 != SELECTED_MANIFEST_SHA256:
        raise ValueError("selected manifest identity is outside the authorised T3 cohort")
    required_execution_keys = {"bridge_fence", "branch", "head"}
    if set(execution_context) != required_execution_keys or any(
        not isinstance(execution_context[key], str) or not execution_context[key].strip()
        for key in required_execution_keys
    ):
        raise ValueError("execution_context must contain nonblank bridge_fence, branch, and head")
    execution_context = {key: execution_context[key].strip() for key in required_execution_keys}
    work = Path(work_root).expanduser().resolve()
    if not work.is_absolute():
        raise ValueError("work_root must be absolute")
    work.mkdir(parents=True, exist_ok=True)
    archive = ContentAddressedArtifactStore(Path(source_archive_root).expanduser().resolve())
    catalog = SQLiteCatalog(work / "catalog.sqlite3").open(initialize=True)
    artifacts = ContentAddressedArtifactStore(work / "representations", catalog=catalog)
    rights_store = RightsGovernanceStore(work / "rights")
    projection: RightsGovernanceProjection | None = None
    rows_out: list[dict[str, Any]] = []
    references: list[RightsPreflightReference] = []
    rights_by_ordinal: dict[int, RightsGovernanceRecord] = {}
    scope_by_subject: dict[str, str] = {}
    source_by_subject: dict[str, CandidateRow] = {}

    try:
        for row in SELECTED_ROWS:
            if row.source_family == "acnc_register":
                source_by_subject[row.subject_id] = row

        for row in SELECTED_ROWS:
            if row.source_definition_id not in {item.source_definition_id for item in SELECTED_ROWS}:
                raise ValueError(f"unrecognised source definition for row {row.ordinal}")
            if row.subject_id not in scope_by_subject:
                register_row = source_by_subject[row.subject_id]
                body = archive.read(register_row.source_artifact_id)
                source_artifact = artifacts.put(body, created_at=RECORDED_AT)
                if source_artifact.artifact_id != register_row.source_artifact_id or source_artifact.content_hash != register_row.source_sha256:
                    raise ValueError(f"identity authority bytes do not match row {row.ordinal}")
                catalog.register_subject(_subject_record(register_row))
                scope = ScopeRecord(
                    record_id=_scope_id(row.subject_id),
                    created_at=RECORDED_AT,
                    producer=_PRODUCER,
                    subject_id=row.subject_id,
                    scope_kind="organisation",
                    label="ACNC registered legal entity",
                )
                catalog.register_scope(scope)
                scope_by_subject[row.subject_id] = scope.record_id

            definition = _definition(row)
            catalog.register_source_definition(definition)
            try:
                body = archive.read(row.source_artifact_id)
            except Exception as exc:
                rows_out.append(_blocked_row(row, scope_by_subject[row.subject_id], "mismatched", f"retained source bytes failed verification: {type(exc).__name__}"))
                continue
            if len(body) != row.byte_size or hashlib.sha256(body).hexdigest() != row.source_sha256:
                rows_out.append(_blocked_row(row, scope_by_subject[row.subject_id], "mismatched", "retained source bytes do not match the selected SHA-256 and byte size"))
                continue
            source_artifact = artifacts.put(body, created_at=RECORDED_AT)
            if source_artifact.artifact_id != row.source_artifact_id or source_artifact.content_hash != row.source_sha256:
                raise ValueError(f"source artifact identity does not match row {row.ordinal}")

            receipt = AcquisitionReceipt(
                record_id=row.acquisition_receipt_id,
                created_at=RECORDED_AT,
                producer=_PRODUCER,
                source_definition_id=row.source_definition_id,
                requested_locator=row.source_locator,
                resolved_locator=row.source_locator,
                retrieved_at=RECORDED_AT,
                outcome="available",
                media_type="application/json",
                content_hash=row.source_sha256,
                byte_size=row.byte_size,
                artifact_id=row.source_artifact_id,
            )
            catalog.record_acquisition_receipt(receipt)
            source_record = SourceRecord(
                record_id=row.source_record_id,
                created_at=RECORDED_AT,
                producer=_PRODUCER,
                about_subject_ids=(row.subject_id,),
                source_family=row.source_family,
                source_role=row.source_role,
                source_locator=row.source_locator,
                observed_at=RECORDED_AT,
                payload_ref=row.source_artifact_id,
                payload_hash=row.source_sha256,
                attribution="Australian Charities and Not-for-profits Commission",
            )
            catalog.register_source_record(source_record)
            representation = artifacts.put_derived(
                body,
                input_artifact_ids=(row.source_artifact_id,),
                schema_id=_REPRESENTATION_SCHEMA_ID,
                schema_version="1.0",
                created_at=RECORDED_AT,
            )
            if representation.artifact_id == row.source_artifact_id:
                raise ValueError("representation identity was relabelled from a source artifact")
            if representation.content_hash != row.source_sha256:
                raise ValueError("representation content hash changed during source-native materialisation")
            locator = catalog.register_evidence_locator(StructuredFieldLocator(
                artifact_id=representation.artifact_id,
                field_path="$",
            ))

            exclusion = (exclusions or {}).get(row.ordinal)
            if exclusion is not None:
                if not all((exclusion.material, exclusion.authority, exclusion.wording, exclusion.affected_operation)):
                    raise ValueError(f"row {row.ordinal} exclusion evidence is incomplete")
                rows_out.append({
                    **_row_identity(row, scope_by_subject[row.subject_id], representation.artifact_id, representation.content_hash, locator["evidence_locator_id"]),
                    "status": "excluded",
                    "provider_processing_status": "blocked",
                    "public_redistribution_status": "not_assessed",
                    "rights_record_id": None,
                    "downstream_tasks": 0,
                    "exclusion_evidence": {
                        "material": exclusion.material,
                        "authority": exclusion.authority,
                        "wording": exclusion.wording,
                        "affected_operation": exclusion.affected_operation,
                    },
                    "technical_gaps": (),
                })
                continue

            record = _rights_record(row, scope_by_subject[row.subject_id], representation.content_hash)
            rights_store.put_record(record)
            rights_store.put_event(RightsGovernanceEvent(
                record_id=record.content_hash,
                event_type="created",
                actor_kind="human",
                actor_id="actor:gregory-product-owner-2026-10-29",
                recorded_at=RECORDED_AT,
                note="private no-send T3 binding materialisation",
            ))
            rights_by_ordinal[row.ordinal] = record
            reference = RightsPreflightReference(
                reference_id=f"g4-t3-binding:{row.ordinal:02d}",
                rights_record_id=record.content_hash,
                source_family=row.source_family,
                source_definition_id=row.source_definition_id,
                evidence_locator_ids=(locator["evidence_locator_id"],),
                claim_family_id="g4-t3-source-binding-v1",
                task_profile="g4_t3_private_source_binding",
                task_profile_version="1",
                schema_version="1",
                difficulty="deterministic",
            )
            references.append(reference)
            rows_out.append({
                **_row_identity(row, scope_by_subject[row.subject_id], representation.artifact_id, representation.content_hash, locator["evidence_locator_id"]),
                "status": "bound_pending_preflight",
                "provider_processing_status": "blocked_provider_contract_not_bound",
                "public_redistribution_status": "not_assessed",
                "rights_record_id": record.content_hash,
                "rights_policy_id": record.rights_policy_id,
                "rights_policy_version": record.rights_policy_version,
                "downstream_tasks": 0,
                "exclusion_evidence": None,
                "technical_gaps": ("provider_contract_identity_and_version",),
            })

        projection = RightsGovernanceProjection(catalog.path).open()
        projection.rebuild_from_store(rights_store, as_of=as_of)
        first_projection_hash = projection.snapshot_hash()
        projection.close()
        projection = RightsGovernanceProjection(catalog.path).open()
        projection.rebuild_from_store(rights_store, as_of=as_of)
        projection_hash = projection.snapshot_hash()
        if projection_hash != first_projection_hash:
            raise ValueError("v29 projection reload was not deterministic")

        preflight_task_count = 0
        for reference in references:
            record = rights_by_ordinal[int(reference.reference_id.rsplit(":", 1)[1])]
            current = projection.current_record(
                record_id=record.content_hash,
                subject_id=record.subject_id,
                scope=record.scope,
                as_of=as_of,
            )
            if current is None:
                raise ValueError(f"v29 current row missing for {reference.reference_id}")
            result = preflight_governed_rights(
                (reference,),
                store=rights_store,
                projection=projection,
                catalog=catalog,
                as_of=as_of,
                retained_bytes=artifacts.read,
            )
            preflight_task_count += result.accepted_count
            row_result = next(item for item in rows_out if item["ordinal"] == int(reference.reference_id.rsplit(":", 1)[1]))
            if result.diagnostics:
                row_result["status"] = "bound_not_task_eligible"
                row_result["technical_gaps"] = tuple(row_result["technical_gaps"]) + tuple(
                    sorted({diagnostic.reason for diagnostic in result.diagnostics})
                )
            else:
                row_result["status"] = "eligible_private_local_retention"

        rows_out.sort(key=lambda item: item["ordinal"])
        manifest_core: dict[str, Any] = {
            "schema": "charitygraph.gate4.t3.selected-binding-manifest/v2",
            "selected_manifest_sha256": SELECTED_MANIFEST_SHA256,
            "as_of": as_of.isoformat(),
            "source_evidence_provenance": {
                "epoch": SOURCE_EVIDENCE_PROVENANCE_EPOCH,
                "producer_revision": SOURCE_EVIDENCE_PROVENANCE_REVISION,
                "target": "gate3-cg406-remediation@cef0e792d8826697db735216be9b3f918c7e44ff",
                "selected_manifest_sha256": SELECTED_MANIFEST_SHA256,
            },
            "bridge_execution_context": execution_context,
            "source_families": ["acnc_register", "acnc_ais_bundle"],
            "source_bytes_included": False,
            "rights_policy": {
                "id": INTERNAL_PRIVATE_USE_POLICY.policy_id,
                "version": INTERNAL_PRIVATE_USE_POLICY.version,
                "basis": INTERNAL_PRIVATE_USE_POLICY.authority_basis,
                "authority_actor": INTERNAL_PRIVATE_USE_POLICY.authority_actor,
                "applicable_operation": INTERNAL_PRIVATE_USE_POLICY.applicable_operation,
                "source_families": list(INTERNAL_PRIVATE_USE_POLICY.source_families),
                "provenance": INTERNAL_PRIVATE_USE_POLICY.provenance,
                "decision_reference": INTERNAL_PRIVATE_USE_POLICY.decision_reference,
            },
            "provider_processing": {"status": "blocked", "reason": "exact provider contract identity/version is not bound in the clean T1B authority"},
            "public_redistribution": {"status": "not_assessed", "reason": "outside this private no-send task"},
            "rows": rows_out,
            "summary": {
                "candidate_rows": len(SELECTED_ROWS),
                "bound_rows": sum(item["rights_record_id"] is not None for item in rows_out),
                "eligible_private_local_retention_rows": sum(item["status"] == "eligible_private_local_retention" for item in rows_out),
                "bound_not_task_eligible_rows": sum(item["status"] == "bound_not_task_eligible" for item in rows_out),
                "excluded_rows": sum(item["status"] == "excluded" for item in rows_out),
                "preflight_authority_tasks": preflight_task_count,
                "downstream_tasks": 0,
                "provider_requests": 0,
                "aud_spend": "0.00",
            },
        }
        manifest_hash = hashlib.sha256(canonical_json_bytes(manifest_core)).hexdigest()
        manifest = {**manifest_core, "manifest_identity_sha256": manifest_hash}
        return BindingBuildResult(
            manifest=manifest,
            manifest_bytes=_canonical_manifest_bytes(manifest),
            projection_snapshot_hash=projection_hash,
            preflight_task_count=preflight_task_count,
            downstream_task_count=0,
        )
    finally:
        if projection is not None:
            projection.close()
        catalog.close()


def _row_identity(row: CandidateRow, scope_id: str, representation_id: str, representation_hash: str, locator_id: str) -> dict[str, Any]:
    return {
        "ordinal": row.ordinal,
        "abn": row.abn,
        "subject_id": row.subject_id,
        "scope_id": scope_id,
        "source_family": row.source_family,
        "source_role": row.source_role,
        "source_definition_id": row.source_definition_id,
        "source_record_id": row.source_record_id,
        "source_artifact_id": row.source_artifact_id,
        "source_sha256": row.source_sha256,
        "acquisition_receipt_id": row.acquisition_receipt_id,
        "representation_artifact_id": representation_id,
        "representation_sha256": representation_hash,
        "evidence_locator_id": locator_id,
    }


def _blocked_row(row: CandidateRow, scope_id: str, status: str, reason: str) -> dict[str, Any]:
    return {
        "ordinal": row.ordinal,
        "abn": row.abn,
        "subject_id": row.subject_id,
        "scope_id": scope_id,
        "source_family": row.source_family,
        "source_role": row.source_role,
        "source_definition_id": row.source_definition_id,
        "source_record_id": row.source_record_id,
        "source_artifact_id": row.source_artifact_id,
        "source_sha256": row.source_sha256,
        "acquisition_receipt_id": row.acquisition_receipt_id,
        "representation_artifact_id": None,
        "representation_sha256": None,
        "evidence_locator_id": None,
        "status": status,
        "provider_processing_status": "blocked",
        "public_redistribution_status": "not_assessed",
        "rights_record_id": None,
        "downstream_tasks": 0,
        "exclusion_evidence": None,
        "technical_gaps": (reason,),
    }


def write_selected_binding_manifest(result: BindingBuildResult, path: str | Path) -> Path:
    destination = Path(path).expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(result.manifest_bytes)
    return destination


build_t3_binding = build_selected_binding_manifest


__all__ = [
    "AS_OF",
    "BindingBuildResult",
    "CandidateRow",
    "ExclusionEvidence",
    "SELECTED_MANIFEST_SHA256",
    "SELECTED_ROWS",
    "build_selected_binding_manifest",
    "build_t3_binding",
    "write_selected_binding_manifest",
]
