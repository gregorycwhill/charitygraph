"""Private deterministic Phase 1 pre-run engine.

The engine accepts only synthetic or already-recorded evidence.  It performs
mechanical joins and task construction, while semantic interpretation remains
inside typed task outputs and the injected provider.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Iterable, Mapping

from pydantic import BaseModel

from .contracts import (
    ArtifactRef, EvidenceInput, ModelTask, ProgramCandidate, ProgramCandidateOutput,
    RelationshipStatement, SchemaRef, SemanticEvidence, SubjectRecord, TaxonomyAssignment,
    TaxonomyAssignmentOutput, TaxonomyConcept, TaxonomyScheme, TaxonomySelection, TaxonomyVersion,
)
from .contracts.ids import deterministic_id
from .contracts.canonical import canonical_sha256
from .contracts.semantic import SEMANTIC_OUTPUT_MODELS, TASK_OUTPUT_SCHEMAS
from .contracts.tasks import ModelResult, model_task_cache_key
from .providers.fake import DeterministicFakeProvider
from .providers.base import ProviderExecution
from .runtime import SQLiteCatalog

DETERMINISTIC_CREATED_AT = datetime(2000, 1, 1, tzinfo=timezone.utc)


def validate_abn(abn: str) -> bool:
    """Validate an Australian Business Number using the official modulo-89 rule."""

    digits = "".join(ch for ch in str(abn) if ch.isdigit())
    if len(digits) != 11:
        return False
    values = [int(ch) for ch in digits]
    values[0] -= 1
    return sum(value * weight for value, weight in zip(values, (10, 1, 3, 5, 7, 9, 11, 13, 15, 17, 19))) % 89 == 0


def normalise_abn(abn: str) -> str:
    digits = "".join(ch for ch in str(abn) if ch.isdigit())
    if not validate_abn(digits):
        raise ValueError("invalid ABN")
    return digits


def exact_identifier_join(
    source_identifiers: Mapping[str, str],
    governed_identifiers: Iterable[Mapping[str, str]],
) -> dict[str, str] | None:
    """Return one exact governed-identifier match, never a name/domain match.

    Inputs may use the compact {"ABN": "..."} fixture form or the canonical
    external_identifiers list. Only recognised identity schemes participate,
    and all schemes shared by both records must agree.
    """
    identity_schemes = {
        "abn", "acn", "acnc", "ato-dgr", "dgr", "charity-registration",
        "charity_id", "charity-id", "lei", "ein", "registration",
    }

    def pairs(record: Mapping[str, Any]) -> dict[str, str]:
        values: dict[str, str] = {}
        listed = record.get("external_identifiers", ())
        if isinstance(listed, Mapping):
            listed = (listed,)
        for item in listed or ():
            if not isinstance(item, Mapping):
                continue
            scheme = str(item.get("scheme", "")).strip().casefold()
            value = item.get("value")
            if scheme in identity_schemes and value not in (None, ""):
                values[scheme] = str(value)
        for key, value in record.items():
            scheme = str(key).strip().casefold()
            if scheme in identity_schemes and value not in (None, ""):
                values[scheme] = str(value)
        normalised: dict[str, str] = {}
        for scheme, value in values.items():
            if scheme == "abn":
                try:
                    normalised[scheme] = normalise_abn(value)
                except ValueError:
                    continue
            else:
                normalised[scheme] = value.strip().casefold()
        return normalised

    source_pairs = pairs(source_identifiers)
    if not source_pairs:
        return None
    matches: list[dict[str, str]] = []
    for item in governed_identifiers:
        candidate = dict(item)
        candidate_pairs = pairs(candidate)
        comparable = set(source_pairs) & set(candidate_pairs)
        if comparable and all(source_pairs[scheme] == candidate_pairs[scheme] for scheme in comparable):
            matches.append(candidate)
    if len(matches) != 1:
        return None
    return matches[0]


def deterministic_subject_id(*, identifier_scheme: str, identifier_value: str, identity_policy: str = "exact-v1") -> str:
    return deterministic_id("subject:", {
        "identifier_scheme": identifier_scheme,
        "identifier_value": identifier_value,
        "identity_policy": identity_policy,
    })


def seed_phase1_taxonomies(
    catalog: SQLiteCatalog,
    *,
    classie_concepts: Iterable[Mapping[str, Any]] = (),
) -> dict[str, list[dict[str, Any]]]:
    """Register separated classification/regulatory profiles for private fixtures.

    ACNC Registration facets, ATO DGR, ACNC AIS CLASSIE and Our Community
    CLASSIE are distinct versioned profiles. No label equality creates a
    mapping between profiles.
    """
    now = datetime(2026, 8, 1, tzinfo=timezone.utc)
    definitions = (
        ("acnc-registration-purpose", "Australian Charities and Not-for-profits Commission", "charitable purpose and subtype regulatory facet", "Australia", "adopted", "ACNC source terms", "preserve source attribution", "2026-fixture"),
        ("acnc-registration-beneficiary", "Australian Charities and Not-for-profits Commission", "beneficiary classification regulatory facet", "Australia", "adopted", "ACNC source terms", "preserve source attribution", "2026-fixture"),
        ("ato-dgr", "Australian Taxation Office", "DGR entitlement, item and scoped endorsement profile", "Australia", "adopted", "ATO source terms", "preserve source attribution", "2026-fixture"),
        ("acnc-ais-classie", "Australian Charities and Not-for-profits Commission", "AIS-year/profile-specific source-reported program classification", "Australia", "adopted", "ACNC source terms", "preserve source attribution", "AIS-2025"),
        ("classie", "Our Community", "independent CharityGraph CLASSIE assessment profile", "Australia and New Zealand", "incorporated", "Modified Creative Commons; Our Community terms of use", "private processing; publication permission required", "4.2"),
        ("sdg", "United Nations", "program/service alignment reference", "global", "reference_only", "UN terms", "attribution; no endorsement implied", "2026-goals"),
        ("charitygraph-activity", "CharityGraph", "bounded native operational activity profile", "Australia", "adapted", "CharityGraph private fixture", "internal fixture until vocabulary is frozen", "2026-fixture"),
    )
    result: dict[str, list[dict[str, Any]]] = {}
    for key, owner, purpose, jurisdiction, disposition, licence, reuse, version_label in definitions:
        scheme = TaxonomyScheme(
            record_id=deterministic_id("scheme:", {"scheme_id": key}),
            created_at=now,
            producer={"kind": "code", "producer_id": "phase1-seed", "version": "2"},
            scheme_id=key, owner=owner, purpose=purpose, jurisdiction=jurisdiction,
            disposition=disposition, licence=licence, reuse_policy=reuse,
            attribution=owner, steward="CharityGraph taxonomy steward",
            review_status="frozen-fixture",
        )
        catalog.register_taxonomy_scheme(scheme)
        version = TaxonomyVersion(
            record_id=deterministic_id("schemever:", {"scheme_id": key, "version": version_label}),
            created_at=now,
            producer={"kind": "code", "producer_id": "phase1-seed", "version": "2"},
            scheme_id=key, version=version_label,
            release_date=date(2022, 11, 16) if key == "classie" else date(2026, 1, 1),
            jurisdiction_scope=jurisdiction,
            source_locator="https://www.ourcommunity.com.au/classie" if key == "classie" else None,
            status="frozen", licence=licence, reuse_policy=reuse, attribution=owner,
        )
        catalog.register_taxonomy_version(version)
        rows: list[dict[str, Any]] = [{"kind": "scheme", "id": scheme.record_id}, {"kind": "version", "id": version.record_id}]
        if key == "acnc-registration-purpose":
            concepts = (("Advancing religion", "Advancing religion"), ("Advancing education", "Advancing education"))
        elif key == "acnc-registration-beneficiary":
            concepts = (("Youth 15-under 25", "Youth 15-under 25"), ("Older people", "Older people"))
        elif key == "ato-dgr":
            concepts = (("DGR-Item-1", "DGR Item 1"),)
        elif key == "acnc-ais-classie":
            concepts = (("AIS-PROGRAM-EXAMPLE", "AIS program classification example"),)
        elif key == "classie":
            concepts = tuple((str(item["external_concept_id"]), str(item["preferred_label"])) for item in classie_concepts)
        elif key == "charitygraph-activity":
            concepts = (("ACT-SERVICE", "Direct service delivery"), ("ACT-ADVOCACY", "Advocacy"), ("ACT-RESEARCH", "Research"))
        elif key == "sdg":
            sdg_titles = (
                "No Poverty", "Zero Hunger", "Good Health and Well-being",
                "Quality Education", "Gender Equality", "Clean Water and Sanitation",
                "Affordable and Clean Energy", "Decent Work and Economic Growth",
                "Industry, Innovation and Infrastructure", "Reduced Inequalities",
                "Sustainable Cities and Communities", "Responsible Consumption and Production",
                "Climate Action", "Life Below Water", "Life on Land",
                "Peace, Justice and Strong Institutions", "Partnerships for the Goals",
            )
            concepts = tuple((f"SDG-{i}", title) for i, title in enumerate(sdg_titles, 1))
        else:
            concepts = ()
        for external_id, label in concepts:
            concept = TaxonomyConcept(
                record_id=deterministic_id("concept:", {"scheme_version_id": version.record_id, "external_id": external_id}),
                created_at=now,
                producer={"kind": "code", "producer_id": "phase1-seed", "version": "2"},
                scheme_version_id=version.record_id, external_concept_id=external_id,
                preferred_label=label,
            )
            catalog.register_taxonomy_concept(concept)
            rows.append({"kind": "concept", "id": concept.record_id, "external_id": external_id})
        result[key] = rows
    return result


class Phase1PreRunEngine:
    """Small vertical seam from recorded evidence to validated assignments."""

    def __init__(self, catalog: SQLiteCatalog, *, provider: DeterministicFakeProvider | None = None) -> None:
        self.catalog = catalog
        self.provider = provider or DeterministicFakeProvider(
            id_factory=lambda prefix, task, _sequence: deterministic_id(
                prefix, {"task_cache_key": task.cache_key, "record_kind": prefix}
            )
        )
        self._registered_fixtures: dict[str, str] = {}

    def register_subject(self, subject: SubjectRecord | Mapping[str, Any]) -> dict[str, Any]:
        return self.catalog.register_subject(subject)

    def ingest_source_record(self, source_record: Any) -> dict[str, Any]:
        return self.catalog.register_source_record(source_record)

    def create_structured_program_candidate(
        self,
        *,
        subject_id: str,
        source_record_id: str,
        evidence_ids: tuple[str, ...],
        label: str,
        candidate_kind: str = "explicit_program",
        source_locator: str | None = None,
    ) -> ProgramCandidate:
        candidate_id = deterministic_id("programcandidate:", {
            "subject_id": subject_id, "source_record_id": source_record_id,
            "evidence_ids": evidence_ids, "label": label, "candidate_kind": candidate_kind,
        })
        candidate = ProgramCandidate(
            record_id=candidate_id,
            created_at=DETERMINISTIC_CREATED_AT,
            producer={"kind": "code", "producer_id": "phase1-engine", "version": "1"},
            subject_id=subject_id,
            source_record_id=source_record_id,
            evidence_ids=evidence_ids,
            label=label,
            candidate_kind=candidate_kind,
            extraction_method="structured",
            source_locator=source_locator,
        )
        self.catalog.register_program_candidate(candidate)
        return candidate

    def create_task(
        self,
        *,
        subject_id: str,
        evidence: tuple[EvidenceInput, ...],
        task_kind: str,
        provider_id: str = "fake",
        model_snapshot: str = "deterministic-fixture-v1",
        parameters: dict[str, Any] | None = None,
    ) -> ModelTask:
        if task_kind not in TASK_OUTPUT_SCHEMAS:
            raise ValueError(f"unsupported Phase 1 task kind: {task_kind}")
        output_schema = TASK_OUTPUT_SCHEMAS[task_kind]
        task_schema = SchemaRef(
            schema_id="urn:charitygraph:builder:schema:phase1-semantic-task:1.0",
            schema_version="1.0",
        )
        task_parameters = parameters or {"task_kind": task_kind}
        cache_key = model_task_cache_key(
            task_type="semantic_interpretation", task_schema=task_schema, output_schema=output_schema,
            evidence_inputs=evidence, prompt_template_id=f"phase1:{task_kind}", prompt_template_version="1",
            policy_refs=(), provider_id=provider_id, model_snapshot=model_snapshot,
            parameters=task_parameters, material_tool_versions=(),
        )
        record_id = deterministic_id("modeltask:", {
            "subject_id": subject_id, "scope_id": None, "task_type": "semantic_interpretation",
            "cache_key": cache_key, "output_schema": output_schema,
        })
        return ModelTask(
            record_id=record_id,
            created_at=DETERMINISTIC_CREATED_AT,
            producer={"kind": "code", "producer_id": "phase1-engine", "version": "1"},
            subject_id=subject_id,
            task_type="semantic_interpretation",
            task_schema=task_schema,
            output_schema=output_schema,
            evidence_inputs=evidence,
            prompt_template_id=f"phase1:{task_kind}",
            prompt_template_version="1",
            provider_id=provider_id,
            model_snapshot=model_snapshot,
            parameters=task_parameters,
            paid_output_categories=("semantic_judgement",),
        )

    def execute_task(self, task: ModelTask, output: BaseModel) -> tuple[ProviderExecution, BaseModel]:
        if task.cache_key is None:
            raise ValueError("task cache key is required")
        expected_model = SEMANTIC_OUTPUT_MODELS.get(task.parameters.get("task_kind", ""))
        if expected_model is None:
            raise ValueError("task parameters must include a supported task_kind")
        if not isinstance(output, expected_model):
            output = expected_model.model_validate(output)
        output_hash = canonical_sha256(output)
        previous_hash = self._registered_fixtures.get(task.cache_key)
        if previous_hash is None:
            self.provider.register(task.cache_key, lambda _: output)
            self._registered_fixtures[task.cache_key] = output_hash
        elif previous_hash != output_hash:
            raise ValueError("replayed task cache key has different semantic output")
        execution = self.provider.execute(task)
        if execution.logical_result.validation_status != "valid":
            raise ValueError("fake provider returned an invalid result")
        return execution, output

    def persist_taxonomy_output(
        self,
        *,
        subject_id: str,
        scheme_version_id: str,
        output: TaxonomyAssignmentOutput,
        evidence_ids: tuple[str, ...],
    ) -> list[dict[str, Any]]:
        rows = []
        for selection in output.selections:
            assignment = TaxonomyAssignment(
                record_id=deterministic_id("assignment:", {
                    "subject_id": subject_id, "scheme_version_id": scheme_version_id,
                    "concept_id": selection.concept_id, "role": selection.role,
                    "evidence_ids": evidence_ids,
                }),
                created_at=DETERMINISTIC_CREATED_AT,
                producer={"kind": "model", "producer_id": "phase1-fake", "version": "1"},
                subject_id=subject_id,
                scheme_version_id=scheme_version_id,
                concept_id=selection.concept_id,
                role=selection.role,
                assignment_method="model-assessed",
                evidence_ids=evidence_ids,
                rationale=selection.rationale,
                confidence=selection.confidence,
                outcome_state="supported",
                lifecycle_status="candidate",
            )
            rows.append(self.catalog.register_taxonomy_assignment(assignment))
        return rows

    def create_program_relationship(
        self, *, organisation_id: str, program_id: str, evidence_ids: tuple[str, ...] = (),
    ) -> dict[str, Any]:
        relationship = RelationshipStatement(
            record_id=deterministic_id("relationship:", {
                "source": organisation_id, "target": program_id, "type": "has_program",
                "evidence_ids": evidence_ids,
            }),
            created_at=DETERMINISTIC_CREATED_AT,
            producer={"kind": "code", "producer_id": "phase1-engine", "version": "1"},
            source_subject_id=organisation_id,
            target_subject_id=program_id,
            relationship_type="has_program",
            evidence_locator_ids=evidence_ids,
            status="candidate",
        )
        return self.catalog.record_relationship(relationship)
