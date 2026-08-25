"""Append-only SQLite catalogue migrations."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass


CATALOGUE_SQL_V1 = """
CREATE TABLE cohorts (
    cohort_id TEXT PRIMARY KEY,
    cohort_code TEXT NOT NULL,
    definition_version TEXT NOT NULL,
    membership_hash TEXT NOT NULL,
    budget_cap_aud TEXT NOT NULL,
    created_at TEXT NOT NULL,
    material_hash TEXT NOT NULL
);
CREATE TABLE runs (
    run_id TEXT PRIMARY KEY,
    cohort_id TEXT REFERENCES cohorts(cohort_id),
    run_kind TEXT NOT NULL,
    status TEXT NOT NULL,
    configuration_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    updated_at TEXT NOT NULL,
    material_hash TEXT NOT NULL
);
CREATE TABLE tasks (
    model_task_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES runs(run_id),
    subject_id TEXT NOT NULL,
    scope_id TEXT,
    cohort_id TEXT REFERENCES cohorts(cohort_id),
    task_type TEXT NOT NULL,
    task_schema_id TEXT NOT NULL,
    cache_key TEXT NOT NULL,
    provider_id TEXT NOT NULL,
    model_snapshot TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('ready','leased','running','succeeded','failed_retryable','failed_terminal','held','cancelled')),
    attempt_count INTEGER NOT NULL DEFAULT 0 CHECK(attempt_count >= 0),
    lease_owner TEXT,
    lease_expires_at TEXT,
    next_eligible_at TEXT,
    result_artifact_id TEXT,
    error_class TEXT,
    error_message_redacted TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    material_hash TEXT NOT NULL
);
CREATE INDEX tasks_claim_idx ON tasks(status, next_eligible_at, lease_expires_at);
CREATE TABLE task_attempts (
    task_run_id TEXT PRIMARY KEY,
    model_task_id TEXT NOT NULL REFERENCES tasks(model_task_id),
    attempt_number INTEGER NOT NULL CHECK(attempt_number > 0),
    status TEXT NOT NULL,
    provider_request_id TEXT,
    provider_batch_id TEXT,
    submitted_at TEXT,
    started_at TEXT,
    completed_at TEXT,
    retryable INTEGER,
    pricing_snapshot_id TEXT,
    fx_snapshot_id TEXT,
    reservation_id TEXT,
    usage_json TEXT,
    result_artifact_id TEXT,
    error_class TEXT,
    error_message_redacted TEXT,
    UNIQUE(model_task_id, attempt_number)
);
CREATE UNIQUE INDEX task_attempts_one_running_idx
    ON task_attempts(model_task_id)
    WHERE status='running';
CREATE TABLE operation_receipts (
    operation_key TEXT PRIMARY KEY,
    operation_type TEXT NOT NULL,
    request_hash TEXT NOT NULL,
    state TEXT NOT NULL CHECK(state IN ('started','completed','failed')),
    result_ref TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE budget_reservations (
    reservation_id TEXT PRIMARY KEY,
    cohort_id TEXT NOT NULL REFERENCES cohorts(cohort_id),
    run_id TEXT NOT NULL REFERENCES runs(run_id),
    reserved_aud TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('active','partially_consumed','consumed','released','expired')),
    reserved_at TEXT NOT NULL,
    expires_at TEXT,
    updated_at TEXT NOT NULL,
    material_hash TEXT NOT NULL
);
CREATE TABLE reservation_tasks (
    reservation_id TEXT NOT NULL REFERENCES budget_reservations(reservation_id),
    model_task_id TEXT NOT NULL REFERENCES tasks(model_task_id),
    PRIMARY KEY(reservation_id, model_task_id)
);
CREATE TABLE cost_entries (
    entry_key TEXT PRIMARY KEY,
    entry_hash TEXT NOT NULL,
    cohort_id TEXT NOT NULL REFERENCES cohorts(cohort_id),
    run_id TEXT NOT NULL REFERENCES runs(run_id),
    task_run_id TEXT,
    reservation_id TEXT NOT NULL,
    entry_type TEXT NOT NULL CHECK(entry_type IN ('reservation','reservation_release','actual','credit','adjustment')),
    paid_output_category TEXT,
    provider_amount TEXT,
    provider_currency TEXT,
    aud_amount TEXT NOT NULL,
    adjustment_direction TEXT CHECK(adjustment_direction IN ('debit','credit') OR adjustment_direction IS NULL),
    pricing_snapshot_id TEXT,
    fx_snapshot_id TEXT,
    usage_json TEXT,
    provider_invoice_ref TEXT,
    recorded_at TEXT NOT NULL
);
CREATE INDEX cost_entries_cohort_idx ON cost_entries(cohort_id, entry_type, reservation_id);
CREATE TABLE cache_entries (
    cache_key TEXT PRIMARY KEY,
    model_task_id TEXT NOT NULL REFERENCES tasks(model_task_id),
    result_artifact_id TEXT NOT NULL,
    result_content_hash TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('valid','invalidated')),
    created_at TEXT NOT NULL,
    invalidated_at TEXT,
    invalidation_reason TEXT
);
CREATE TABLE cache_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    cache_key TEXT NOT NULL,
    event_type TEXT NOT NULL CHECK(event_type IN ('created','invalidated','replaced')),
    event_at TEXT NOT NULL,
    result_artifact_id TEXT,
    result_content_hash TEXT,
    reason TEXT
);
CREATE INDEX cache_events_key_idx ON cache_events(cache_key, event_id);

CREATE TABLE artifact_index (
    artifact_id TEXT PRIMARY KEY,
    content_hash TEXT NOT NULL,
    schema_id TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    storage_path TEXT NOT NULL,
    availability TEXT NOT NULL CHECK(availability IN ('available','missing','quarantined')),
    created_at TEXT NOT NULL,
    indexed_at TEXT NOT NULL
);
""".strip() + "\n"


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    sql: str

    @property
    def checksum(self) -> str:
        return hashlib.sha256(self.sql.encode("utf-8")).hexdigest()



CATALOGUE_SQL_V2 = """
CREATE TABLE source_definitions (
    source_definition_id TEXT PRIMARY KEY,
    definition_version TEXT NOT NULL,
    publisher TEXT NOT NULL,
    source_class TEXT NOT NULL,
    authority_roles_json TEXT NOT NULL,
    material_json TEXT NOT NULL,
    material_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE acquisition_receipts (
    acquisition_id TEXT PRIMARY KEY,
    source_definition_id TEXT NOT NULL REFERENCES source_definitions(source_definition_id),
    requested_locator TEXT NOT NULL,
    resolved_locator TEXT,
    retrieved_at TEXT,
    effective_at TEXT,
    outcome TEXT NOT NULL CHECK(outcome IN ('available','not_modified','absent','blocked','failed','partial','unavailable')),
    response_status INTEGER,
    media_type TEXT,
    content_hash TEXT,
    byte_size INTEGER CHECK(byte_size IS NULL OR byte_size >= 0),
    artifact_id TEXT,
    tool_id TEXT,
    tool_version TEXT,
    material_parameters_json TEXT NOT NULL,
    retry_of TEXT,
    replaces_receipt_id TEXT,
    error_class TEXT,
    material_json TEXT NOT NULL,
    material_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX acquisition_receipts_source_idx ON acquisition_receipts(source_definition_id, retrieved_at);
CREATE TABLE artifact_lineage (
    artifact_id TEXT NOT NULL,
    input_artifact_id TEXT NOT NULL,
    edge_type TEXT NOT NULL CHECK(edge_type IN ('derived_from','acquired_as','parsed_from','excerpted_from')),
    PRIMARY KEY(artifact_id, input_artifact_id)
);
CREATE INDEX artifact_lineage_input_idx ON artifact_lineage(input_artifact_id);
CREATE TABLE evidence_locators (
    evidence_locator_id TEXT PRIMARY KEY,
    artifact_id TEXT,
    source_record_id TEXT,
    kind TEXT NOT NULL CHECK(kind IN ('structured_field','text_span','document')),
    locator_json TEXT NOT NULL,
    material_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    CHECK(artifact_id IS NOT NULL OR source_record_id IS NOT NULL)
);
CREATE INDEX evidence_locator_artifact_idx ON evidence_locators(artifact_id);
CREATE INDEX evidence_locator_source_idx ON evidence_locators(source_record_id);
CREATE INDEX artifact_index_content_idx ON artifact_index(content_hash);
""".strip() + "\n"

CATALOGUE_SQL_V3 = """
CREATE TABLE subjects (
    subject_id TEXT PRIMARY KEY,
    subject_kind TEXT NOT NULL,
    lifecycle_status TEXT NOT NULL,
    material_json TEXT NOT NULL,
    material_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE external_identifiers (
    external_identifier_id TEXT PRIMARY KEY,
    subject_id TEXT NOT NULL REFERENCES subjects(subject_id),
    scheme TEXT NOT NULL,
    identifier_value TEXT NOT NULL,
    issuing_authority TEXT NOT NULL DEFAULT '',
    valid_from TEXT,
    valid_to TEXT,
    status TEXT NOT NULL CHECK(status IN ('active','inactive','superseded','withdrawn')),
    material_json TEXT NOT NULL,
    material_hash TEXT NOT NULL,
    UNIQUE(scheme, identifier_value, issuing_authority)
);
CREATE INDEX external_identifiers_subject_idx ON external_identifiers(subject_id);
CREATE TABLE subject_scopes (
    scope_id TEXT PRIMARY KEY,
    subject_id TEXT NOT NULL REFERENCES subjects(subject_id),
    scope_kind TEXT NOT NULL,
    label TEXT,
    parent_scope_id TEXT REFERENCES subject_scopes(scope_id),
    valid_from TEXT,
    valid_to TEXT,
    lifecycle_status TEXT NOT NULL CHECK(lifecycle_status IN ('active','inactive','superseded','withdrawn')),
    material_json TEXT NOT NULL,
    material_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX subject_scopes_subject_idx ON subject_scopes(subject_id);
CREATE TABLE party_roles (
    party_role_id TEXT PRIMARY KEY,
    party_id TEXT NOT NULL,
    role TEXT NOT NULL,
    context_record_id TEXT,
    scope_id TEXT REFERENCES subject_scopes(scope_id),
    valid_from TEXT,
    valid_to TEXT,
    status TEXT NOT NULL CHECK(status IN ('active','inactive','withdrawn')),
    material_json TEXT NOT NULL,
    material_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX party_roles_party_idx ON party_roles(party_id, role);
CREATE TABLE knowledge_observations (
    observation_id TEXT PRIMARY KEY,
    subject_id TEXT NOT NULL REFERENCES subjects(subject_id),
    scope_id TEXT REFERENCES subject_scopes(scope_id),
    predicate TEXT NOT NULL,
    value_json TEXT,
    outcome_state TEXT NOT NULL CHECK(outcome_state IN ('resolved','supported','contradicted','unknown','insufficient_evidence','not_applicable','not_attempted','withheld','acquisition_failure','extraction_failure','model_failure')),
    evidence_locator_ids_json TEXT NOT NULL,
    source_record_ids_json TEXT NOT NULL,
    observation_time_json TEXT NOT NULL,
    method TEXT NOT NULL,
    lifecycle_status TEXT NOT NULL CHECK(lifecycle_status IN ('candidate','accepted','edited','rejected','superseded','contradicted','withdrawn','held','unresolved')),
    supersedes_observation_id TEXT REFERENCES knowledge_observations(observation_id),
    material_json TEXT NOT NULL,
    material_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX knowledge_observations_subject_idx ON knowledge_observations(subject_id, scope_id);
CREATE INDEX knowledge_observations_predicate_idx ON knowledge_observations(predicate, lifecycle_status);
CREATE TABLE knowledge_assertions (
    assertion_id TEXT PRIMARY KEY,
    subject_id TEXT NOT NULL REFERENCES subjects(subject_id),
    scope_id TEXT REFERENCES subject_scopes(scope_id),
    predicate TEXT NOT NULL,
    value_json TEXT,
    outcome_state TEXT NOT NULL CHECK(outcome_state IN ('resolved','supported','contradicted','unknown','insufficient_evidence','not_applicable','not_attempted','withheld','acquisition_failure','extraction_failure','model_failure')),
    observation_ids_json TEXT NOT NULL,
    evidence_locator_ids_json TEXT NOT NULL,
    assertion_time_json TEXT NOT NULL,
    method TEXT NOT NULL,
    lifecycle_status TEXT NOT NULL CHECK(lifecycle_status IN ('candidate','accepted','edited','rejected','superseded','contradicted','withdrawn','held','unresolved')),
    publication_eligibility TEXT NOT NULL CHECK(publication_eligibility IN ('eligible','ineligible','review_required','withheld')),
    supersedes_assertion_id TEXT REFERENCES knowledge_assertions(assertion_id),
    material_json TEXT NOT NULL,
    material_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX knowledge_assertions_subject_idx ON knowledge_assertions(subject_id, scope_id);
CREATE INDEX knowledge_assertions_predicate_idx ON knowledge_assertions(predicate, lifecycle_status);
CREATE TABLE relationship_statements (
    relationship_id TEXT PRIMARY KEY,
    source_subject_id TEXT NOT NULL REFERENCES subjects(subject_id),
    target_subject_id TEXT NOT NULL REFERENCES subjects(subject_id),
    relationship_type TEXT NOT NULL,
    scope_id TEXT REFERENCES subject_scopes(scope_id),
    source_role TEXT,
    target_role TEXT,
    evidence_locator_ids_json TEXT NOT NULL,
    observation_ids_json TEXT NOT NULL,
    valid_from TEXT,
    valid_to TEXT,
    status TEXT NOT NULL CHECK(status IN ('candidate','accepted','rejected','withdrawn','superseded')),
    material_json TEXT NOT NULL,
    material_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    CHECK(source_subject_id <> target_subject_id)
);
CREATE INDEX relationship_statements_source_idx ON relationship_statements(source_subject_id, relationship_type);
CREATE INDEX relationship_statements_target_idx ON relationship_statements(target_subject_id, relationship_type);
CREATE TABLE adjudication_decisions (
    adjudication_id TEXT PRIMARY KEY,
    input_record_ids_json TEXT NOT NULL,
    outcome TEXT NOT NULL CHECK(outcome IN ('accepted','edited','rejected','insufficient','withheld','identity_blocked','scope_blocked','deferred')),
    rationale TEXT NOT NULL,
    reviewer_id TEXT NOT NULL,
    result_record_id TEXT,
    decision_time TEXT NOT NULL,
    review_policy_id TEXT NOT NULL,
    material_json TEXT NOT NULL,
    material_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX adjudication_result_idx ON adjudication_decisions(result_record_id);
CREATE TABLE knowledge_lineage (
    source_record_id TEXT NOT NULL,
    target_record_id TEXT NOT NULL,
    edge_type TEXT NOT NULL CHECK(edge_type IN ('proposed_from','reviewed_by','promoted_as','derived_from','supersedes','invalidates','contradicts','withdraws','adjudicates')),
    material_json TEXT NOT NULL,
    material_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY(source_record_id, target_record_id, edge_type),
    CHECK(source_record_id <> target_record_id)
);
CREATE INDEX knowledge_lineage_target_idx ON knowledge_lineage(target_record_id, edge_type);
CREATE INDEX knowledge_lineage_source_idx ON knowledge_lineage(source_record_id, edge_type);
""".strip() + "\n"

MIGRATIONS: tuple[Migration, ...] = (
    Migration(1, "initial_operational_catalogue", CATALOGUE_SQL_V1),
    Migration(2, "source_evidence_foundation", CATALOGUE_SQL_V2),
    Migration(3, "governed_knowledge_primitives", CATALOGUE_SQL_V3),
)

SUPPORTED_VERSION = MIGRATIONS[-1].version
