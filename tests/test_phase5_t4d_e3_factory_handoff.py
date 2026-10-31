from __future__ import annotations

import json
from dataclasses import replace
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from charitygraph.contracts import (
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
from charitygraph.contracts.canonical import canonical_sha256
from charitygraph.contracts.ids import deterministic_id
from charitygraph.evidence_store import ContentAddressedArtifactStore
from charitygraph.phase5_factory import ReferenceFactory
from charitygraph.phase5_governed_cohort_rehearsal import CountingFakeProvider
from charitygraph.phase5_t4b_source_answer_projection import build_source_answer_projection
from charitygraph.phase5_t4c_private_answer_brief import compose_private_answer_brief
from charitygraph.phase5_t4d_e3_factory_handoff import (
    BUILD_ID,
    ROUTE_POLICY_VERSION,
    TASK_IDENTITY,
    preflight_e3_private_answer_brief,
)
from charitygraph.runtime import SQLiteCatalog
from charitygraph.runtime.rights_governance_projection import RightsGovernanceProjection
from charitygraph.runtime.rights_governance_record import (
    INTERNAL_PRIVATE_USE_POLICY_ID,
    RightsAxis,
    RightsGovernanceRecord,
    RightsGovernanceStore,
    RightsStorageError,
)


NOW = datetime(2026, 10, 31, tzinfo=timezone.utc)
MANIFEST_PATH = Path(__file__).parents[1] / "evidence" / "gate4-t3-five-subject-v1" / "selected-binding-manifest.json"
REPRESENTATION_ROOT = Path(r"C:\CharityGraph-runtime\g4-t4a-single-subject-report-probe\representations")
PRODUCER = ProducerRef(kind="code", producer_id="g4-t4d-test-fixture", version="1")
SCHEMA = SchemaRef(schema_id="urn:charitygraph:builder:schema:g4-t4d-test-fixture:1", schema_version="1")


def _read_manifest() -> dict[str, Any]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def _representation_bytes(digest: str) -> bytes:
    return (REPRESENTATION_ROOT / "objects" / "sha256" / digest[:2] / digest).read_bytes()


def _rewrite_brief_rights(brief: Any, rights_ids: dict[str, str], policy_id: str) -> Any:
    comparison_fields = (
        "program_count", "operating_in_states", "countries", "beneficiaries",
        "reporting_period", "accounting_basis", "receipts", "expenses",
        "net_surplus_deficit", "full_time_employees", "part_time_employees",
        "casual_employees", "unpaid_volunteers",
    )

    def rewrite_record(record: Any) -> Any:
        citations = tuple(
            replace(
                citation,
                rights_record_id=rights_ids[citation.rights_record_id],
                rights_policy_id=policy_id,
                rights_policy_version="1.0.0",
            )
            for citation in record.source_references
        )
        return replace(
            record,
            rights_record_id=rights_ids[record.rights_record_id],
            rights_policy_id=policy_id,
            rights_policy_version="1.0.0",
            source_references=citations,
        )

    subjects = []
    for subject in brief.subjects:
        comparison = subject.comparison
        comparison = replace(
            comparison,
            **{
                field: replace(
                    getattr(comparison, field),
                    rights_record_id=rights_ids[getattr(comparison, field).rights_record_id],
                    rights_policy_id=policy_id,
                    rights_policy_version="1.0.0",
                )
                for field in comparison_fields
            },
        )
        subjects.append(replace(
            subject,
            activity=rewrite_record(subject.activity),
            scale=rewrite_record(subject.scale),
            currentness=rewrite_record(subject.currentness),
            comparison=comparison,
        ))
    return replace(
        brief,
        subjects=tuple(subjects),
        answer_slots=tuple(
            rewrite_record(record) for record in brief.answer_slots
        ),
        source_rights_bindings=tuple(
            (source_record_id, digest, rights_ids[rights_id])
            for source_record_id, digest, rights_id in brief.source_rights_bindings
        ),
    )


class _DelegatingCatalog:
    def __init__(
        self,
        catalog: SQLiteCatalog,
        missing: str | None = None,
        lineage_mismatch: bool = False,
        source_mismatch: bool = False,
    ):
        self._catalog = catalog
        self._missing = missing
        self._lineage_mismatch = lineage_mismatch
        self._source_mismatch = source_mismatch

    def __getattr__(self, name: str) -> Any:
        if name == self._missing:
            return lambda _identifier: None
        if name == "get_artifact_lineage" and self._lineage_mismatch:
            return lambda _identifier: []
        if name == "get_source_record" and self._source_mismatch:
            def tampered_source(identifier: str) -> Any:
                row = self._catalog.get_source_record(identifier)
                return None if row is None else {**row, "source_role": "tampered"}
            return tampered_source
        return getattr(self._catalog, name)


class _MissingRightsStore:
    def __init__(self, store: RightsGovernanceStore, missing_id: str):
        self._store = store
        self._missing_id = missing_id

    def load_record(self, record_id: str) -> Any:
        if record_id == self._missing_id:
            raise RightsStorageError("deterministic test fixture omitted the current rights record")
        return self._store.load_record(record_id)


class _Fixture:
    def __init__(self, root: Path, rights_mode: str = "current"):
        self.catalog = SQLiteCatalog(root / "catalog.sqlite3").open(initialize=True)
        self.objects = ContentAddressedArtifactStore(root / "objects", catalog=self.catalog)
        self.rights_store = RightsGovernanceStore(root / "rights")
        self.manifest = _read_manifest()
        for row in self.manifest["rows"]:
            row["rights_policy_id"] = INTERNAL_PRIVATE_USE_POLICY_ID
            row["rights_policy_version"] = "1.0.0"
        self._register_material(rights_mode)
        self.projection = RightsGovernanceProjection(self.catalog.path).open()
        self.projection.rebuild_from_store(self.rights_store, as_of=NOW.date())
        self.brief = _rewrite_brief_rights(
            self._real_brief(), self.rights_ids, INTERNAL_PRIVATE_USE_POLICY_ID
        )

    def _real_brief(self) -> Any:
        projection = build_source_answer_projection(
            manifest_path=MANIFEST_PATH,
            representation_root=REPRESENTATION_ROOT,
        )
        return compose_private_answer_brief(projection)

    def _register_material(self, rights_mode: str) -> None:
        rows = [dict(row) for row in self.manifest["rows"]]
        self.rights_ids: dict[str, str] = {}
        self.representation_bytes: dict[str, bytes] = {}
        subjects: set[str] = set()
        scopes: set[str] = set()
        definitions: set[str] = set()
        for row in rows:
            subject_id = row["subject_id"]
            scope_id = row["scope_id"]
            source_hash = row["representation_sha256"]
            source_url = f"https://example.invalid/g4-t4d/{row['source_record_id']}"
            subjects.add(subject_id)
            scopes.add(scope_id)
            definitions.add(row["source_definition_id"])
            if self.catalog.get_subject(subject_id) is None:
                self.catalog.register_subject(SubjectRecord(
                    record_id=deterministic_id("subjectrecord:", f"g4-t4d:{subject_id}"),
                    created_at=NOW,
                    producer=PRODUCER,
                    subject_id=subject_id,
                    subject_kind="organisation",
                    lifecycle_status="active",
                    identity_authority_refs=(ArtifactRef(
                        artifact_id=f"authority:g4-t4d-{subject_id.split(':', 1)[1]}",
                        content_hash="a" * 64,
                        schema=SCHEMA,
                    ),),
                    identity_policy_id="g4-t4d-test-identity-v1",
                    display_name=f"TEST E3 subject {subject_id}",
                ))
            if self.catalog.get_scope(scope_id) is None:
                self.catalog.register_scope(ScopeRecord(
                    record_id=scope_id,
                    created_at=NOW,
                    producer=PRODUCER,
                    subject_id=subject_id,
                    scope_kind="organisation",
                    label=f"TEST E3 scope {scope_id}",
                ))
            if self.catalog.get_source_definition(row["source_definition_id"]) is None:
                self.catalog.register_source_definition(SourceDefinition(
                    record_id=row["source_definition_id"],
                    created_at=NOW,
                    producer=PRODUCER,
                    publisher="TEST T3 fixture",
                    source_class=row["source_family"],
                    authority_roles=(PropositionAuthorityRole(proposition="source", role="source-native"),),
                    acquisition_locator=source_url,
                    temporal_semantics="retrieval snapshot",
                    publication_eligibility="private review only",
                    steward="builder",
                    rights_policy_id=row["rights_policy_id"],
                ))
            payload = _representation_bytes(source_hash)
            self.representation_bytes[f"artifact:{source_hash}"] = payload
            source_artifact = self.objects.put(payload, created_at=NOW)
            source_artifact_id = source_artifact.artifact_id
            representation_artifact = self.objects.put_derived(
                payload,
                input_artifact_ids=(source_artifact_id,),
                created_at=NOW,
            )
            self.catalog.record_acquisition_receipt(AcquisitionReceipt(
                record_id=row["acquisition_receipt_id"],
                created_at=NOW,
                producer=PRODUCER,
                source_definition_id=row["source_definition_id"],
                requested_locator=source_url,
                resolved_locator=source_url,
                retrieved_at=NOW,
                outcome="available",
                content_hash=source_hash,
                byte_size=len(payload),
                artifact_id=source_artifact_id,
            ))
            self.catalog.register_source_record(SourceRecord.model_construct(
                record_id=row["source_record_id"],
                created_at=NOW,
                producer=PRODUCER,
                about_subject_ids=(subject_id,),
                source_family=row["source_family"],
                source_role=row["source_role"],
                source_locator=source_url,
                observed_at=NOW,
                payload_ref=source_artifact_id,
                payload_hash=source_hash,
                rights_policy_id=row["rights_policy_id"],
            ))
            self.catalog.register_evidence_locator(
                StructuredFieldLocator(artifact_id=representation_artifact.artifact_id, field_path="g4_t4d.fixture"),
                evidence_locator_id=row["evidence_locator_id"],
                now=NOW,
            )
            expires_on = date(2026, 10, 1) if rights_mode == "expired" else None
            if rights_mode in {"denied", "superseded"}:
                status = "blocked" if rights_mode == "denied" else "superseded"
                review_status = "blocked" if rights_mode == "denied" else "superseded"
                local_axis = RightsAxis(status="blocked")
            else:
                status = "authorized"
                review_status = "current"
                local_axis = RightsAxis(
                    status="authorized",
                    policy_id=INTERNAL_PRIVATE_USE_POLICY_ID,
                    policy_version="1.0.0",
                    decision_id=f"rights:g4-t4d:{row['ordinal']}:retention",
                )
            rights_record = RightsGovernanceRecord(
                decision_id=f"rights:g4-t4d:{row['ordinal']}",
                source_artifact_id=source_artifact_id,
                source_record_id=row["source_record_id"],
                subject_id=subject_id,
                source_origin_url=source_url,
                source_role=row["source_role"],
                acquisition_lineage_ids=(row["acquisition_receipt_id"],),
                representation_artifact_id=representation_artifact.artifact_id,
                representation_sha256=source_hash,
                rights_basis="public_source_private_processing",
                rights_policy_id=row["rights_policy_id"],
                rights_policy_version=row["rights_policy_version"],
                purpose="semantic_analysis",
                scope=scope_id,
                evidence_locator=source_url,
                evidence_sha256=source_hash,
                assessed_on=NOW.date(),
                local_retention=local_axis,
                provider_transmission=RightsAxis(status="blocked"),
                public_redistribution=RightsAxis(status="not_assessed"),
                status=status,
                review_status=review_status,
                expires_on=expires_on,
                actor_kind="human",
                actor_id="actor:g4-t4d-test",
                actor_version="1",
                recorded_at=NOW,
                representation_class="structured_factual",
                factual_representation_only=True,
                publicly_accessible_without_circumvention=True,
                lawfully_acquired=True,
                lawful_access_confirmed=True,
                circumvention_used=False,
                one_source_native_entity_record=True,
                retention_lifecycle_status="active_until_review" if status == "authorized" else "blocked",
                retention_review_due_on=date(2027, 10, 31),
            )
            self.rights_store.put_record(rights_record)
            self.rights_ids[row["rights_record_id"]] = rights_record.content_hash

        self.synthetic_rows = [
            {**row, "rights_record_id": self.rights_ids[row["rights_record_id"]]}
            for row in rows
        ]
        self.manifest["rows"] = self.synthetic_rows
        self.manifest["manifest_identity_sha256"] = canonical_sha256({
            key: value for key, value in self.manifest.items() if key != "manifest_identity_sha256"
        })

    def close(self) -> None:
        self.projection.close()
        self.catalog.close()


def _register_run(catalog: SQLiteCatalog) -> tuple[str, str]:
    cohort_id = "cohort:g4-t4d-test"
    run_id = "run:g4-t4d-test"
    catalog.register_cohort({
        "record_id": cohort_id,
        "cohort_code": "G4-T4D-TEST",
        "definition_version": "1",
        "membership_hash": "b" * 64,
        "budget_cap": {"amount": "0", "currency": "AUD"},
        "created_at": NOW,
    })
    catalog.register_run({
        "record_id": run_id,
        "cohort_id": cohort_id,
        "run_kind": "g4_t4d_provider_free_test",
        "status": "planned",
        "configuration_hash": "c" * 64,
        "created_at": NOW,
    })
    return cohort_id, run_id


def _counts(catalog: SQLiteCatalog) -> dict[str, int]:
    with catalog._connection() as conn:
        return {
            table: int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            for table in ("tasks", "task_attempts", "provider_receipts", "budget_reservations", "cost_entries")
        }


def _preflight(fixture: _Fixture, **kwargs: Any) -> Any:
    return preflight_e3_private_answer_brief(
        fixture.brief,
        fixture.manifest,
        fixture.rights_store,
        fixture.projection,
        fixture.catalog,
        NOW.date(),
        fixture.representation_bytes.__getitem__,
        **kwargs,
    )


def test_accepted_e3_lowers_to_ten_deterministic_factory_children_and_replays(tmp_path: Path):
    fixture = _Fixture(tmp_path)
    try:
        first = _preflight(fixture)
        second = _preflight(fixture)
        assert not first.diagnostics
        assert first.accepted_count == 10
        assert first.summary["subjects"] == 5
        assert first.summary["answer_slots"] == 15
        assert first.summary["coverage_entries"] == 20
        assert first.summary["source_hashes"] == 10
        assert first.summary["rights_bindings"] == 10
        assert first.summary["build_id"] == BUILD_ID
        assert first.summary["route_policy_version"] == ROUTE_POLICY_VERSION
        assert first.summary["difficulty"] == "deterministic"
        assert first.summary["bundle_key"] is None
        assert first.factory_plan.manifest_hash == second.factory_plan.manifest_hash
        assert first.summary["logical_task_ids"] == second.summary["logical_task_ids"]

        cohort_id, run_id = _register_run(fixture.catalog)
        provider = CountingFakeProvider()
        runner = ReferenceFactory(
            fixture.catalog,
            first.factory_plan,
            cohort_id=cohort_id,
            run_id=run_id,
            provider=provider,
        )
        seeded = runner.seed(NOW)
        assert len(seeded) == 10
        assert runner.run(NOW) == 10
        assert runner.run(NOW) == 0
        assert provider.send_calls == 0
        assert _counts(fixture.catalog) == {
            "tasks": 10,
            "task_attempts": 10,
            "provider_receipts": 0,
            "budget_reservations": 0,
            "cost_entries": 0,
        }
        assert all(
            fixture.catalog.get_task(task["record_id"])["status"] == "succeeded"
            for task in seeded
        )
    finally:
        fixture.close()


@pytest.mark.parametrize(
    "field",
    [
        "subject_id", "scope_id", "source_family", "source_record_id",
        "representation_sha256", "rights_record_id", "rights_policy_id",
        "rights_policy_version", "provider_processing_status",
        "public_redistribution_status", "status", "source_definition_id",
        "acquisition_receipt_id", "evidence_locator_id",
    ],
)
def test_t3_tamper_is_cohort_level_zero_work(tmp_path: Path, field: str):
    fixture = _Fixture(tmp_path)
    try:
        row = dict(fixture.manifest["rows"][0])
        row[field] = "tampered" if field not in {"representation_sha256"} else "0" * 64
        fixture.manifest["rows"][0] = row
        fixture.manifest["manifest_identity_sha256"] = canonical_sha256({
            key: value for key, value in fixture.manifest.items() if key != "manifest_identity_sha256"
        })
        result = _preflight(fixture)
        assert result.accepted_count == 0
        assert result.factory_plan.logical_tasks == ()
        assert result.diagnostics
    finally:
        fixture.close()


def test_e3_envelope_tamper_is_zero_work(tmp_path: Path):
    fixture = _Fixture(tmp_path)
    try:
        fixture.brief = replace(
            fixture.brief,
            answer_slots=(replace(fixture.brief.answer_slots[0], source_role="tampered"),) + fixture.brief.answer_slots[1:],
        )
        result = _preflight(fixture)
        assert result.accepted_count == 0
        assert result.diagnostics[0].state == "mismatched"
    finally:
        fixture.close()


def test_duplicate_t3_tuple_is_zero_work(tmp_path: Path):
    fixture = _Fixture(tmp_path)
    try:
        fixture.manifest["rows"][1] = dict(fixture.manifest["rows"][0])
        fixture.manifest["manifest_identity_sha256"] = canonical_sha256({
            key: value for key, value in fixture.manifest.items() if key != "manifest_identity_sha256"
        })
        result = _preflight(fixture)
        assert result.accepted_count == 0
        assert result.diagnostics
    finally:
        fixture.close()


@pytest.mark.parametrize("rights_mode", ["expired", "denied", "superseded"])
def test_non_current_rights_record_is_zero_work(tmp_path: Path, rights_mode: str):
    fixture = _Fixture(tmp_path, rights_mode=rights_mode)
    try:
        result = _preflight(fixture)
        assert result.accepted_count == 0
        assert result.diagnostics
    finally:
        fixture.close()


def test_missing_rights_record_is_fail_closed_with_bounded_diagnostic(tmp_path: Path):
    fixture = _Fixture(tmp_path)
    try:
        missing = fixture.synthetic_rows[0]["rights_record_id"]
        result = preflight_e3_private_answer_brief(
            fixture.brief,
            fixture.manifest,
            _MissingRightsStore(fixture.rights_store, missing),
            fixture.projection,
            fixture.catalog,
            NOW.date(),
            fixture.representation_bytes.__getitem__,
        )
        assert result.accepted_count == 0
        assert any("unavailable" in diagnostic.reason for diagnostic in result.diagnostics)
    finally:
        fixture.close()


def test_current_projection_mismatch_is_zero_work(tmp_path: Path):
    fixture = _Fixture(tmp_path)
    try:
        record_id = fixture.synthetic_rows[0]["rights_record_id"]
        with fixture.projection._catalog._connection(immediate=True) as conn:
            conn.execute(
                "UPDATE rights_projection_records SET source_role=? WHERE record_id=?",
                ("tampered", record_id),
            )
            fixture.projection._catalog._commit(conn)
        result = _preflight(fixture)
        assert result.accepted_count == 0
        assert result.diagnostics
    finally:
        fixture.close()


@pytest.mark.parametrize("missing", ["get_source_definition", "get_acquisition_receipt", "get_evidence_locator"])
def test_missing_durable_lineage_is_zero_work(tmp_path: Path, missing: str):
    fixture = _Fixture(tmp_path)
    try:
        result = preflight_e3_private_answer_brief(
            fixture.brief,
            fixture.manifest,
            fixture.rights_store,
            fixture.projection,
            _DelegatingCatalog(fixture.catalog, missing=missing),
            NOW.date(),
            fixture.representation_bytes.__getitem__,
        )
        assert result.accepted_count == 0
        assert result.diagnostics
    finally:
        fixture.close()


def test_representation_lineage_mismatch_is_zero_work(tmp_path: Path):
    fixture = _Fixture(tmp_path)
    try:
        result = preflight_e3_private_answer_brief(
            fixture.brief,
            fixture.manifest,
            fixture.rights_store,
            fixture.projection,
            _DelegatingCatalog(fixture.catalog, lineage_mismatch=True),
            NOW.date(),
            fixture.representation_bytes.__getitem__,
        )
        assert result.accepted_count == 0
        assert result.diagnostics
    finally:
        fixture.close()


def test_source_lineage_mismatch_is_zero_work(tmp_path: Path):
    fixture = _Fixture(tmp_path)
    try:
        result = preflight_e3_private_answer_brief(
            fixture.brief,
            fixture.manifest,
            fixture.rights_store,
            fixture.projection,
            _DelegatingCatalog(fixture.catalog, source_mismatch=True),
            NOW.date(),
            fixture.representation_bytes.__getitem__,
        )
        assert result.accepted_count == 0
        assert result.diagnostics
    finally:
        fixture.close()


def test_provider_or_non_deterministic_route_is_blocked_before_factory_work(tmp_path: Path):
    fixture = _Fixture(tmp_path)
    try:
        result = _preflight(fixture, difficulty="lower_cost_constrained_semantic")
        assert result.accepted_count == 0
        assert result.diagnostics[0].state == "blocked"
        assert "provider" in result.diagnostics[0].reason
        result = _preflight(fixture, route_policy_version="provider-route-v1")
        assert result.accepted_count == 0
        assert result.diagnostics[0].state == "blocked"
    finally:
        fixture.close()
