from datetime import datetime, timedelta, timezone
import sqlite3

import pytest
from pydantic import ValidationError

from charitygraph.contracts import EvidenceInput, EvidenceLocator, ModelResult, ModelTask, ProgramCandidate, ProgramCandidateOutput, SchemaRef, SemanticConclusion, SemanticEvidence, model_task_cache_key
from charitygraph.runtime import CatalogError, ConflictError, SQLiteCatalog
from .test_budget_ledger import BASE_COHORT, BASE_RUN, COHORT_ID, NOW
from .test_knowledge_persistence import subject
from charitygraph.contracts.ids import deterministic_id

OUTPUT_SCHEMA = SchemaRef(schema_id="urn:charitygraph:builder:schema:program-decomposition-output:1.0", schema_version="1.0")
EVIDENCE_ID = "evidence:" + "e" * 32
TASK_ID = "modeltask:" + "1" * 32
TASK_RUN_ID = "taskrun:" + "2" * 32
SUBJECT_ID = "subject:" + "1" * 32


def setup(tmp_path):
    catalog = SQLiteCatalog(tmp_path / "state.sqlite3").open(initialize=True)
    catalog.register_cohort(BASE_COHORT)
    catalog.register_run(BASE_RUN)
    catalog.register_subject(subject(SUBJECT_ID))
    catalog.register_evidence_locator({"kind": "document", "source_record_id": "srcrec:" + "f" * 32, "locator": "fixture:evidence"}, evidence_locator_id=EVIDENCE_ID, now=NOW)
    task = {"record_id": TASK_ID, "subject_id": SUBJECT_ID, "cohort_id": COHORT_ID, "task_type": "structured_extraction", "task_schema": {"schema_id": "urn:charitygraph:builder:schema:test-task:1.0"}, "cache_key": "a" * 64, "provider_id": "fake", "model_snapshot": "fake"}
    catalog.register_task(task, run_id=BASE_RUN["record_id"], now=NOW)
    catalog.claim_task(TASK_ID, owner="worker", lease_expires_at=NOW + timedelta(minutes=5), now=NOW)
    catalog.begin_task_attempt(TASK_ID, owner="worker", task_run_id=TASK_RUN_ID, now=NOW)
    return catalog, task


def output(decision, evidence_id=EVIDENCE_ID):
    return ProgramCandidateOutput(label="Clean Water Service", decision=decision, subject_kind="service" if decision == "material_service" else "program", duplicate_of_candidate_id=("programcandidate:" + "d" * 32 if decision == "duplicate_or_alias" else None), parent_candidate_id=("programcandidate:" + "a" * 32 if decision == "parent_child_proposal" else None), conclusion=SemanticConclusion(outcome="supported", evidence=(SemanticEvidence(evidence_id=evidence_id, role="supporting"),), rationale="Explicit synthetic evidence", confidence="high"))


def result(decision="material_program", *, result_id="modelresult:" + "3" * 32, task_id=TASK_ID, task_run_id=TASK_RUN_ID, validation_status="valid", output_schema=OUTPUT_SCHEMA, provider_id="fake", model_snapshot="fake-v1", evidence_id=EVIDENCE_ID):
    return ModelResult(record_id=result_id, created_at=NOW, producer={"kind": "model", "producer_id": "fake-provider"}, model_task_id=task_id, task_run_id=task_run_id, output_schema=output_schema, output=output(decision, evidence_id), validation_status=validation_status, validation_errors=("invalid output",) if validation_status == "invalid" else (), raw_response_ref="response:synthetic", completed_at=NOW, provider_id=provider_id, model_snapshot=model_snapshot)


def test_model_result_persists_exact_output_and_is_idempotent(tmp_path):
    catalog, _ = setup(tmp_path)
    first = catalog.register_model_result(result())
    second = catalog.register_model_result(result())
    assert first["model_result_id"] == second["model_result_id"]
    assert catalog.get_model_result(first["model_result_id"])["output"]["label"] == "Clean Water Service"
    with pytest.raises(ConflictError):
        catalog.register_model_result(result(result_id=first["model_result_id"], decision="material_service"))


def test_model_result_rejects_unknown_task_run_or_wrong_task(tmp_path):
    catalog, _ = setup(tmp_path)
    with pytest.raises(ConflictError):
        catalog.register_model_result(result(task_run_id="taskrun:" + "4" * 32))
    with pytest.raises(CatalogError):
        catalog.register_model_result(result(task_id="modeltask:" + "5" * 32))


@pytest.mark.parametrize(("decision", "kind"), [("material_program", "explicit_program"), ("material_service", "explicit_service")])
def test_valid_model_result_projects_positive_candidate(tmp_path, decision, kind):
    catalog, _ = setup(tmp_path)
    stored = catalog.register_model_result(result(decision))
    candidate = catalog.project_program_candidate(stored["model_result_id"], now=NOW)
    assert candidate["candidate_kind"] == kind
    assert candidate["extraction_method"] == "model_task"
    assert candidate["model_result_id"] == stored["model_result_id"]
    assert candidate["source_record_id"] is None
    assert candidate["evidence_ids"] == [EVIDENCE_ID]


@pytest.mark.parametrize("decision", ["non_program", "insufficient_evidence", "duplicate_or_alias", "parent_child_proposal"])
def test_non_positive_model_decisions_do_not_project_candidate(tmp_path, decision):
    catalog, _ = setup(tmp_path)
    stored = catalog.register_model_result(result(decision))
    assert catalog.project_program_candidate(stored["model_result_id"], now=NOW) is None


def test_invalid_model_result_does_not_project_candidate(tmp_path):
    catalog, _ = setup(tmp_path)
    stored = catalog.register_model_result(result("material_program", validation_status="invalid"))
    assert catalog.project_program_candidate(stored["model_result_id"], now=NOW) is None


def test_model_task_candidate_contract_requires_model_result_and_structured_requires_source_record():
    common = dict(record_id="programcandidate:" + "6" * 32, created_at=NOW, producer={"kind": "code", "producer_id": "test"}, subject_id=SUBJECT_ID, evidence_ids=(EVIDENCE_ID,), label="x", candidate_kind="explicit_program", status="candidate")
    with pytest.raises(ValidationError):
        ProgramCandidate(**common, extraction_method="model_task")
    with pytest.raises(ValidationError):
        ProgramCandidate(**common, extraction_method="structured", model_result_id="modelresult:" + "7" * 32)
    with pytest.raises(ValidationError):
        ProgramCandidate(**common, extraction_method="structured")


def test_model_task_candidate_cannot_mismatch_result_kind_or_evidence(tmp_path):
    catalog, _ = setup(tmp_path)
    stored = catalog.register_model_result(result("material_program"))
    bad_kind = ProgramCandidate(record_id="programcandidate:" + "8" * 32, created_at=NOW, producer={"kind": "model", "producer_id": "test"}, subject_id=SUBJECT_ID, model_result_id=stored["model_result_id"], evidence_ids=(EVIDENCE_ID,), label="Clean Water Service", candidate_kind="explicit_service", extraction_method="model_task")
    with pytest.raises(ConflictError):
        catalog.register_program_candidate(bad_kind)
    bad_evidence = ProgramCandidate(record_id="programcandidate:" + "9" * 32, created_at=NOW, producer={"kind": "model", "producer_id": "test"}, subject_id=SUBJECT_ID, model_result_id=stored["model_result_id"], evidence_ids=("evidence:" + "a" * 32,), label="Clean Water Service", candidate_kind="explicit_program", extraction_method="model_task")
    with pytest.raises(CatalogError):
        catalog.register_program_candidate(bad_evidence)


def test_model_result_and_candidate_subject_are_bound_to_task(tmp_path):
    catalog, _ = setup(tmp_path)
    other = "subject:" + "a" * 32
    catalog.register_subject(subject(other))
    stored = catalog.register_model_result(result())
    candidate = ProgramCandidate(record_id="programcandidate:" + "b" * 32, created_at=NOW, producer={"kind": "model", "producer_id": "test"}, subject_id=other, model_result_id=stored["model_result_id"], evidence_ids=(EVIDENCE_ID,), label="Clean Water Service", candidate_kind="explicit_program", extraction_method="model_task")
    with pytest.raises(ConflictError):
        catalog.register_program_candidate(candidate)


def test_schema_upgrade_contains_model_result_fk_and_candidate_lineage_columns(tmp_path):
    catalog, _ = setup(tmp_path)
    with sqlite3.connect(tmp_path / "state.sqlite3") as conn:
        result_columns = {row[1] for row in conn.execute("PRAGMA table_info(model_results)")}
        candidate_columns = {row[1] for row in conn.execute("PRAGMA table_info(program_candidates)")}
        assert {"model_result_id", "output_json", "output_hash", "validation_status"} <= result_columns
        assert {"source_record_id", "model_result_id"} <= candidate_columns
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []



def typed_setup(tmp_path):
    catalog = SQLiteCatalog(tmp_path / "typed.sqlite3").open(initialize=True)
    catalog.register_cohort(BASE_COHORT)
    catalog.register_run(BASE_RUN)
    catalog.register_subject(subject(SUBJECT_ID))
    artifact_id = "artifact:" + "a" * 32
    catalog.index_artifact(artifact_id=artifact_id, content_hash="a" * 64, schema_id="urn:test:artifact", schema_version="1", storage_path="private/test", availability="available", created_at=NOW, indexed_at=NOW)
    locator = catalog.register_evidence_locator(EvidenceLocator(kind="document", artifact_id=artifact_id, locator="fixture://doc"), evidence_locator_id=EVIDENCE_ID, now=NOW)
    evidence = EvidenceInput(evidence_id=EVIDENCE_ID, content_hash="a" * 64, selection_hash=locator["material_hash"])
    task_schema = SchemaRef(schema_id="urn:charitygraph:builder:schema:typed-task:1.0", schema_version="1.0")
    cache_key = model_task_cache_key(task_type="semantic_interpretation", task_schema=task_schema, output_schema=OUTPUT_SCHEMA, evidence_inputs=(evidence,), prompt_template_id="typed-test", prompt_template_version="1", policy_refs=(), provider_id="fake", model_snapshot="fake-v1", parameters={"temperature": "0"}, material_tool_versions=())
    typed = ModelTask(record_id=deterministic_id("modeltask:", {"subject_id": SUBJECT_ID, "scope_id": None, "task_type": "semantic_interpretation", "cache_key": cache_key, "output_schema": OUTPUT_SCHEMA}), created_at=NOW, producer={"kind": "code", "producer_id": "typed-test", "version": "1"}, subject_id=SUBJECT_ID, task_type="semantic_interpretation", task_schema=task_schema, output_schema=OUTPUT_SCHEMA, evidence_inputs=(evidence,), prompt_template_id="typed-test", prompt_template_version="1", provider_id="fake", model_snapshot="fake-v1", parameters={"temperature": "0"}, paid_output_categories=("semantic_judgement",), cache_key=cache_key)
    row = catalog.register_task(typed, run_id=BASE_RUN["record_id"], now=NOW)
    catalog.claim_task(typed.record_id, owner="worker", lease_expires_at=NOW + timedelta(minutes=5), now=NOW)
    catalog.begin_task_attempt(typed.record_id, owner="worker", task_run_id=TASK_RUN_ID, now=NOW)
    return catalog, typed, evidence, row


def test_typed_model_task_persists_ordered_evidence_schema_and_material(tmp_path):
    catalog, typed, evidence, row = typed_setup(tmp_path)
    assert row["output_schema_id"] == OUTPUT_SCHEMA.schema_id
    assert row["output_schema_version"] == OUTPUT_SCHEMA.schema_version
    assert row["task_material_json"]
    with sqlite3.connect(tmp_path / "typed.sqlite3") as conn:
        persisted = conn.execute("SELECT ordinal, evidence_id, content_hash, selection_hash FROM model_task_evidence WHERE model_task_id=?", (typed.record_id,)).fetchall()
    assert persisted == [(0, evidence.evidence_id, evidence.content_hash, evidence.selection_hash)]


@pytest.mark.parametrize("field", ["content_hash", "selection_hash"])
def test_typed_model_task_rejects_wrong_evidence_hash(tmp_path, field):
    catalog = SQLiteCatalog(tmp_path / "wrong.sqlite3").open(initialize=True)
    catalog.register_cohort(BASE_COHORT)
    catalog.register_run(BASE_RUN)
    catalog.register_subject(subject(SUBJECT_ID))
    artifact_id = "artifact:" + "b" * 32
    catalog.index_artifact(artifact_id=artifact_id, content_hash="b" * 64, schema_id="urn:test:artifact", schema_version="1", storage_path="private/test", availability="available", created_at=NOW, indexed_at=NOW)
    locator = catalog.register_evidence_locator(EvidenceLocator(kind="document", artifact_id=artifact_id, locator="fixture://doc"), evidence_locator_id=EVIDENCE_ID, now=NOW)
    good = EvidenceInput(evidence_id=EVIDENCE_ID, content_hash="b" * 64, selection_hash=locator["material_hash"])
    bad = good.model_copy(update={field: "c" * 64})
    task_schema = SchemaRef(schema_id="urn:charitygraph:builder:schema:typed-task:1.0", schema_version="1.0")
    evidence = (bad,)
    cache_key = model_task_cache_key(task_type="semantic_interpretation", task_schema=task_schema, output_schema=OUTPUT_SCHEMA, evidence_inputs=evidence, prompt_template_id="typed-test", prompt_template_version="1", policy_refs=(), provider_id="fake", model_snapshot="fake-v1", parameters={"temperature": "0"}, material_tool_versions=())
    typed = ModelTask(record_id=deterministic_id("modeltask:", {"subject_id": SUBJECT_ID, "scope_id": None, "task_type": "semantic_interpretation", "cache_key": cache_key, "output_schema": OUTPUT_SCHEMA}), created_at=NOW, producer={"kind": "code", "producer_id": "typed-test", "version": "1"}, subject_id=SUBJECT_ID, task_type="semantic_interpretation", task_schema=task_schema, output_schema=OUTPUT_SCHEMA, evidence_inputs=evidence, prompt_template_id="typed-test", prompt_template_version="1", provider_id="fake", model_snapshot="fake-v1", parameters={"temperature": "0"}, paid_output_categories=("semantic_judgement",), cache_key=cache_key)
    with pytest.raises(ConflictError):
        catalog.register_task(typed, run_id=BASE_RUN["record_id"], now=NOW)


@pytest.mark.parametrize(("attribute", "value"), [("provider_id", "other"), ("model_snapshot", "other-v1")])
def test_bound_result_requires_task_provider_and_model(tmp_path, attribute, value):
    catalog, typed, _, _ = typed_setup(tmp_path)
    kwargs = {attribute: value}
    with pytest.raises(ConflictError):
        catalog.register_model_result(result(**kwargs, task_id=typed.record_id, task_run_id=TASK_RUN_ID))


def test_bound_result_requires_output_schema(tmp_path):
    catalog, typed, _, _ = typed_setup(tmp_path)
    other_schema = SchemaRef(schema_id="urn:charitygraph:builder:schema:other:1.0", schema_version="1.0")
    with pytest.raises(ConflictError):
        catalog.register_model_result(result(task_id=typed.record_id, task_run_id=TASK_RUN_ID, output_schema=other_schema))


def test_bound_result_rejects_catalogue_evidence_not_task_bound(tmp_path):
    catalog, typed, _, _ = typed_setup(tmp_path)
    other_id = "evidence:" + "d" * 32
    artifact_id = "artifact:" + "d" * 32
    catalog.index_artifact(artifact_id=artifact_id, content_hash="d" * 64, schema_id="urn:test:artifact", schema_version="1", storage_path="private/test", availability="available", created_at=NOW, indexed_at=NOW)
    catalog.register_evidence_locator(EvidenceLocator(kind="document", artifact_id=artifact_id, locator="fixture://other"), evidence_locator_id=other_id, now=NOW)
    with pytest.raises(ConflictError):
        catalog.register_model_result(result(task_id=typed.record_id, task_run_id=TASK_RUN_ID, evidence_id=other_id))


def test_bound_result_projects_through_typed_task(tmp_path):
    catalog, typed, _, _ = typed_setup(tmp_path)
    stored = catalog.register_model_result(result(task_id=typed.record_id, task_run_id=TASK_RUN_ID))
    candidate = catalog.project_program_candidate(stored["model_result_id"], now=NOW)
    assert candidate["model_result_id"] == stored["model_result_id"]
    assert candidate["evidence_ids"] == [EVIDENCE_ID]


def test_typed_model_task_rejects_duplicate_evidence_ids(tmp_path):
    catalog, typed, evidence, _ = typed_setup(tmp_path)
    duplicate = typed.model_copy(update={"evidence_inputs": (evidence, evidence)})
    with pytest.raises(ConflictError):
        catalog.register_task(duplicate, run_id=BASE_RUN["record_id"], now=NOW)
