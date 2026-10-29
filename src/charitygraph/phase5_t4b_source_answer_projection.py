"""Pure, source-native answer projection for the retained Gate 4 T3 cohort.

The projection reads an existing JSON manifest and its content-addressed JSON
representations.  It does not use the catalogue, acquire evidence, call a
provider, or interpret unrestricted prose.  The only transformations are
identity checks and selection of named source-native fields.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from .contracts.canonical import canonical_sha256


REPRESENTATION_SCHEMA = "urn:charitygraph:builder:schema:acnc-source-native-representation:1.0"
MANIFEST_SCHEMA_PREFIX = "charitygraph.gate4.t3.selected-binding-manifest/"
EXPECTED_SELECTED_MANIFEST_SHA256 = "41b4ce5f1c39afd31a28b1f819d2a9759c89880eb0ddb2d2b143662cf4dda7a9"
SUPPORTED_SOURCE_FAMILIES = ("acnc_register", "acnc_ais_bundle")
REPRESENTATION_OBJECTS_DIR = ("objects", "sha256")

QUESTION_ACTIVITY = "source_native_activity_and_footprint"
QUESTION_SCALE = "retained_reporting_period_scale"
QUESTION_CURRENTNESS = "current_giving_capacity_outcomes_governance_conduct"
QUESTION_IDS = (QUESTION_ACTIVITY, QUESTION_SCALE, QUESTION_CURRENTNESS)

MISSING_CURRENTNESS = (
    "current_giving_terms",
    "current_service_capacity",
    "outcomes_or_effectiveness",
    "governance",
    "conduct_or_adverse_history",
)

# These are the governed identities in the local T3 manifest, not test data.
# Keeping the immutable subject/ABN/scope binding here prevents a manifest row
# from silently moving a representation to another durable subject.
_EXPECTED_BINDINGS = {
    "52000399744": {
        "subject_id": "subject:02649cdcb42049bb8dedd30f2333e150",
        "scope_id": "scope:0a10077aee9363200199a815e8198f3807fef97737ad89bfd1e2e17f61d63248",
    },
    "26164251245": {
        "subject_id": "subject:0889b4decb854e71ab4784479ca95c03",
        "scope_id": "scope:be9c7fd3d0d859f542cafc07213313253f05e8824509b94b12e6ecc9ab640913",
    },
    "52404606134": {
        "subject_id": "subject:16fba76fde2242d5870835b18b4e8b8d",
        "scope_id": "scope:dd27dd2827c65677813405fdaac014be3d600fa0d9993ecf464b71b2a7dc6e81",
    },
    "33107782196": {
        "subject_id": "subject:1823309bdd06417c9928033603cb6e39",
        "scope_id": "scope:95767a26704b78a0c75411dbb3322b5076ed5874fc56e335e5a9e20ea4ac0d4a",
    },
    "82147006639": {
        "subject_id": "subject:1a9ec5de3fc043ff9226fb95a6cae31b",
        "scope_id": "scope:e71cd138c69b1727c7a7b5d909a66cb9bf9a3af87d1658bb97cd987333d46aa1",
    },
}

# Exact source-record and rights identities accepted by the governed T3
# binding.  These are identifiers only; the source bodies remain outside the
# repository.  The complete tuple is checked so a valid-looking srcrec value
# cannot move a representation across a source, subject, scope, or rights
# binding.
_EXPECTED_T3_SOURCE_BINDINGS = {
    1: {
        "subject_id": "subject:02649cdcb42049bb8dedd30f2333e150",
        "scope_id": "scope:0a10077aee9363200199a815e8198f3807fef97737ad89bfd1e2e17f61d63248",
        "source_family": "acnc_register",
        "source_record_id": "srcrec:4978c7ff7f9694d9d9d6db9ad871a8048cde5940c6e699a2dd4bd15360bcd28d",
        "representation_sha256": "f7b0522efbf6253cfa13713750a96100c601fd801fd209524f948dc134f0ada2",
        "rights_record_id": "1d887b9ddf909ade17236230de3c4f34d17e514202774d31925522770510067f",
    },
    2: {
        "subject_id": "subject:02649cdcb42049bb8dedd30f2333e150",
        "scope_id": "scope:0a10077aee9363200199a815e8198f3807fef97737ad89bfd1e2e17f61d63248",
        "source_family": "acnc_ais_bundle",
        "source_record_id": "srcrec:554fa9df1414f0096b9035fea5ac5eee7ffb59e46eb767d6306d40d8f326f08a",
        "representation_sha256": "70734f7c268aba097a37ab30c75640aca151583c2d616004cc90dffc0e878f1b",
        "rights_record_id": "f4a57c5d2d048b1a3b28ccb6d8d7e7247c1796ca2aa02c68fe7b89a5440ce20f",
    },
    3: {
        "subject_id": "subject:0889b4decb854e71ab4784479ca95c03",
        "scope_id": "scope:be9c7fd3d0d859f542cafc07213313253f05e8824509b94b12e6ecc9ab640913",
        "source_family": "acnc_register",
        "source_record_id": "srcrec:f05f137023221378d486eef96e0c4efe377bb4811ac63fbbbb9aa8f103c251d2",
        "representation_sha256": "8382a8ca22b00b71244664d85d6db3d0bdc1bafa40192ffb437e6227c4234773",
        "rights_record_id": "7f7cb0ad8032d685ff1be8c924f894aea1d085f6a70aca4ca895cf6ab32cb56d",
    },
    4: {
        "subject_id": "subject:0889b4decb854e71ab4784479ca95c03",
        "scope_id": "scope:be9c7fd3d0d859f542cafc07213313253f05e8824509b94b12e6ecc9ab640913",
        "source_family": "acnc_ais_bundle",
        "source_record_id": "srcrec:045161751edf9950655698373906590d67abf2c35ba33dd804b61b3ac95237f8",
        "representation_sha256": "ea9b75510efe03a1ef829bb5e044988de371d133c3bedbedb060914be438ab33",
        "rights_record_id": "f62cb8f9f6d6b841a9fa177c572eba45957b616618145b77020044e9c68fd308",
    },
    5: {
        "subject_id": "subject:16fba76fde2242d5870835b18b4e8b8d",
        "scope_id": "scope:dd27dd2827c65677813405fdaac014be3d600fa0d9993ecf464b71b2a7dc6e81",
        "source_family": "acnc_register",
        "source_record_id": "srcrec:188a391cee048ab2fa7720aeb2c58f5b1e025039ef674ef8a6fd6ea0ab91dd8a",
        "representation_sha256": "ead4a76bbbd9ad9aa29d79e82219b707d28f34d5232b00311544b8e6424f925c",
        "rights_record_id": "a7b671341df5d1f970789274577438d15c2258f4be0e0903e5682eb3818a26d6",
    },
    6: {
        "subject_id": "subject:16fba76fde2242d5870835b18b4e8b8d",
        "scope_id": "scope:dd27dd2827c65677813405fdaac014be3d600fa0d9993ecf464b71b2a7dc6e81",
        "source_family": "acnc_ais_bundle",
        "source_record_id": "srcrec:5cc396995aea23edbab90c78b47101651f3a085f34ab088417dc3e1caa6fda25",
        "representation_sha256": "9649487585e0267792c3b9c7ffa36261f0a5e93e69e87cac3e7f8154622e9678",
        "rights_record_id": "528bd93255f561419e3ef7e2ce418463548f347ef5daa0d74f66a864c91bf17c",
    },
    7: {
        "subject_id": "subject:1823309bdd06417c9928033603cb6e39",
        "scope_id": "scope:95767a26704b78a0c75411dbb3322b5076ed5874fc56e335e5a9e20ea4ac0d4a",
        "source_family": "acnc_register",
        "source_record_id": "srcrec:5e1c9ac1b0378a22557a9bf804697719133663123e7f603d76eb41fd2601adf4",
        "representation_sha256": "1ba64e644b28ff4528f6b075d42babb34ad5ee66fa9ce78110077ceef45170e6",
        "rights_record_id": "6c67f153b4da1c475f192b634dff98f1e5b0b294c65fda05b95a8d354f3171d8",
    },
    8: {
        "subject_id": "subject:1823309bdd06417c9928033603cb6e39",
        "scope_id": "scope:95767a26704b78a0c75411dbb3322b5076ed5874fc56e335e5a9e20ea4ac0d4a",
        "source_family": "acnc_ais_bundle",
        "source_record_id": "srcrec:e94d13fec302f9cefc42569b4d191dae5b360565c8c3d8b4e1cded8ece5c0c52",
        "representation_sha256": "692829d7188a787f2df3b91df982a2de34e6c86787b19d31d202737a072e07eb",
        "rights_record_id": "41b37a38584aba73baadff7659f9a252b55ebb2d0a9a7407aaa0c9e108db953d",
    },
    9: {
        "subject_id": "subject:1a9ec5de3fc043ff9226fb95a6cae31b",
        "scope_id": "scope:e71cd138c69b1727c7a7b5d909a66cb9bf9a3af87d1658bb97cd987333d46aa1",
        "source_family": "acnc_register",
        "source_record_id": "srcrec:e6529d39e4cf32248a4792142cdc5e5bfb5cb45c5055180f35662344c737544c",
        "representation_sha256": "a0f9c00f981fe7724262474f10212e08d3a775884055001181b06664c7eac74c",
        "rights_record_id": "a52cdeb042f46a9f4f96df6fa62c798ca83c4cd413839ec813889109b5f93fc1",
    },
    10: {
        "subject_id": "subject:1a9ec5de3fc043ff9226fb95a6cae31b",
        "scope_id": "scope:e71cd138c69b1727c7a7b5d909a66cb9bf9a3af87d1658bb97cd987333d46aa1",
        "source_family": "acnc_ais_bundle",
        "source_record_id": "srcrec:39443daa20d28eadd1164573c635a5c0aa2d89d3b7a8753b14f8321b90f4aea9",
        "representation_sha256": "b02a4079bd2ac8316123ad9ad7ff8cf9dfe3bf8832ac22bef6b2133d963f0b7f",
        "rights_record_id": "64aabd8a8fbbe14579c286d4ab73555c165960485264ac9dd0e505c7a53b979f",
    },
}


class ProjectionValidationError(ValueError):
    """Raised when a retained identity or representation integrity check fails."""


@dataclass(frozen=True)
class SourceCitation:
    subject_id: str
    scope_id: str
    source_family: str
    source_record_id: str
    representation_sha256: str
    representation_locator: str
    source_date: str | None
    reporting_period: Mapping[str, str] | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "subject_id": self.subject_id,
            "scope_id": self.scope_id,
            "source_family": self.source_family,
            "source_record_id": self.source_record_id,
            "representation_sha256": self.representation_sha256,
            "representation_locator": self.representation_locator,
            "source_date": self.source_date,
            "reporting_period": None if self.reporting_period is None else dict(self.reporting_period),
        }


@dataclass(frozen=True)
class AnswerRecord:
    subject_id: str
    scope_id: str
    question_id: str
    question: str
    answer_state: str
    answer: Mapping[str, Any] | None
    missingness: Mapping[str, Any] | None
    source_family: str
    source_record_id: str
    representation_sha256: str
    representation_locator: str
    source_date: str | None
    reporting_period: Mapping[str, str] | None
    fact_vs_source_statement_vs_inference: str
    field_basis: tuple[str, ...]
    source_references: tuple[SourceCitation, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "subject_id": self.subject_id,
            "scope_id": self.scope_id,
            "question_id": self.question_id,
            "question": self.question,
            "answer_state": self.answer_state,
            "answer": None if self.answer is None else dict(self.answer),
            "missingness": None if self.missingness is None else dict(self.missingness),
            "source_family": self.source_family,
            "source_record_id": self.source_record_id,
            "representation_sha256": self.representation_sha256,
            "representation_locator": self.representation_locator,
            "source_date": self.source_date,
            "reporting_period": None if self.reporting_period is None else dict(self.reporting_period),
            "fact_vs_source_statement_vs_inference": self.fact_vs_source_statement_vs_inference,
            "field_basis": list(self.field_basis),
            "source_references": [citation.as_dict() for citation in self.source_references],
        }


@dataclass(frozen=True)
class AnswerProjection:
    records: tuple[AnswerRecord, ...]
    representation_hashes: tuple[str, ...]
    side_effects: Mapping[str, int]

    @property
    def document(self) -> dict[str, Any]:
        return {
            "schema": "charitygraph.gate4.t4b.source-native-answer-projection/v1",
            "answer_state_vocabulary": ["supported", "unanswered"],
            "records": [record.as_dict() for record in self.records],
            "representation_hashes": list(self.representation_hashes),
            "side_effects": dict(self.side_effects),
        }


_MISSING = object()


def _read_json(path: Path) -> Mapping[str, Any]:
    try:
        return json.loads(path.read_bytes())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProjectionValidationError(f"cannot read JSON representation: {path}") from exc


def _required(row: Mapping[str, Any], key: str) -> Any:
    value = row.get(key, _MISSING)
    if value is _MISSING or value is None:
        raise ProjectionValidationError(f"manifest row is missing {key}")
    return value


def _source_field(body: Mapping[str, Any], key: str) -> Any:
    """Read a named native field from either observed body layout."""
    if key in body:
        return body[key]
    nested = body.get("data")
    if isinstance(nested, Mapping) and key in nested:
        return nested[key]
    return _MISSING


def _source_field_path(body: Mapping[str, Any], key: str) -> str:
    return f"$.{key}" if key in body else f"$.data.{key}"


def _citation(row: Mapping[str, Any], path: Path, body: Mapping[str, Any]) -> SourceCitation:
    family = str(_required(row, "source_family"))
    period = None
    source_date = None
    if family == "acnc_register":
        source_date = _source_field(body, "LastReported")
    elif family == "acnc_ais_bundle":
        start = _source_field(body, "FinReportFrom")
        end = _source_field(body, "FinReportTo")
        if start is not _MISSING and end is not _MISSING and start is not None and end is not None:
            period = {"from": str(start), "to": str(end)}
    return SourceCitation(
        subject_id=str(_required(row, "subject_id")),
        scope_id=str(_required(row, "scope_id")),
        source_family=family,
        source_record_id=str(_required(row, "source_record_id")),
        representation_sha256=str(_required(row, "representation_sha256")),
        representation_locator=str(path),
        source_date=None if source_date is None else str(source_date),
        reporting_period=period,
    )


def _validate_rows(manifest: Mapping[str, Any]) -> list[dict[str, Any]]:
    if not str(manifest.get("schema", "")).startswith(MANIFEST_SCHEMA_PREFIX):
        raise ProjectionValidationError("unsupported T3 manifest schema")
    if manifest.get("selected_manifest_sha256") != EXPECTED_SELECTED_MANIFEST_SHA256:
        raise ProjectionValidationError("selected T3 manifest identity mismatch")
    manifest_identity = manifest.get("manifest_identity_sha256")
    if not isinstance(manifest_identity, str):
        raise ProjectionValidationError("manifest identity is missing")
    manifest_core = {key: value for key, value in manifest.items() if key != "manifest_identity_sha256"}
    if canonical_sha256(manifest_core) != manifest_identity:
        raise ProjectionValidationError("canonical T3 manifest identity mismatch")
    rows = manifest.get("rows")
    if not isinstance(rows, list) or len(rows) != 10:
        raise ProjectionValidationError("the projection requires exactly ten retained T3 rows")

    seen_ordinals: set[int] = set()
    seen_subjects: set[str] = set()
    per_subject: dict[str, list[dict[str, Any]]] = {}
    for raw in rows:
        if not isinstance(raw, dict):
            raise ProjectionValidationError("manifest row is not an object")
        row = dict(raw)
        ordinal = int(_required(row, "ordinal"))
        if ordinal in seen_ordinals:
            raise ProjectionValidationError("manifest ordinals are not unique")
        seen_ordinals.add(ordinal)
        family = str(_required(row, "source_family"))
        if family not in SUPPORTED_SOURCE_FAMILIES:
            raise ProjectionValidationError("manifest contains a non-admitted source family")
        subject_id = str(_required(row, "subject_id"))
        scope_id = str(_required(row, "scope_id"))
        abn = str(_required(row, "abn"))
        expected = _EXPECTED_BINDINGS.get(abn)
        if expected is None or subject_id != expected["subject_id"] or scope_id != expected["scope_id"]:
            raise ProjectionValidationError("manifest subject/scope/ABN binding mismatch")
        source_hash = str(_required(row, "source_sha256"))
        representation_hash = str(_required(row, "representation_sha256"))
        if source_hash != representation_hash or len(representation_hash) != 64:
            raise ProjectionValidationError("source and representation hashes do not match")
        if row.get("representation_artifact_id") != f"artifact:{representation_hash}":
            raise ProjectionValidationError("representation artifact identity mismatch")
        if row.get("source_artifact_id") != f"srcblob:{source_hash}":
            raise ProjectionValidationError("source artifact identity mismatch")
        expected_source = _EXPECTED_T3_SOURCE_BINDINGS.get(ordinal)
        if expected_source is None or any(row.get(key) != value for key, value in expected_source.items()):
            raise ProjectionValidationError("manifest source-record/rights binding mismatch")
        per_subject.setdefault(subject_id, []).append(row)
        seen_subjects.add(subject_id)

    if seen_subjects != {item["subject_id"] for item in _EXPECTED_BINDINGS.values()}:
        raise ProjectionValidationError("manifest does not contain the governed five-subject cohort")
    for subject_id, subject_rows in per_subject.items():
        if len(subject_rows) != 2 or {item["source_family"] for item in subject_rows} != set(SUPPORTED_SOURCE_FAMILIES):
            raise ProjectionValidationError("each subject must have one register and one AIS row")
    return sorted(per_subject.values(), key=lambda group: min(int(item["ordinal"]) for item in group))


def _representation_path(root: Path, digest: str) -> Path:
    # The path is intentionally constructed from the exact digest; no archive
    # enumeration or discovery is performed.
    return root.joinpath(*REPRESENTATION_OBJECTS_DIR, digest[:2], digest)


def _load_rows(manifest_path: Path, representation_root: Path) -> list[tuple[dict[str, Any], Path, Mapping[str, Any], SourceCitation]]:
    manifest = _read_json(manifest_path)
    groups = _validate_rows(manifest)
    loaded: list[tuple[dict[str, Any], Path, Mapping[str, Any], SourceCitation]] = []
    for group in groups:
        for raw in sorted(group, key=lambda item: int(item["ordinal"])):
            digest = str(raw["representation_sha256"])
            path = _representation_path(representation_root, digest)
            try:
                payload = path.read_bytes()
            except OSError as exc:
                raise ProjectionValidationError(f"representation is unavailable: {path}") from exc
            if hashlib.sha256(payload).hexdigest() != digest:
                raise ProjectionValidationError(f"representation hash mismatch: {path}")
            try:
                body = json.loads(payload)
            except json.JSONDecodeError as exc:
                raise ProjectionValidationError(f"representation is not JSON: {path}") from exc
            if not isinstance(body, dict):
                raise ProjectionValidationError(f"representation is not a JSON object: {path}")
            body_abn = _source_field(body, "Abn")
            if body_abn is not _MISSING and body_abn not in (None, "") and str(body_abn) != str(raw["abn"]):
                raise ProjectionValidationError("representation ABN does not match its governed row")
            expected_type = "charity" if raw["source_family"] == "acnc_register" else "annual_information_statement"
            if body.get("type") != expected_type:
                raise ProjectionValidationError("representation type does not match source family")
            citation = _citation(raw, path, body)
            loaded.append((raw, path, body, citation))
    return loaded


def _unanswered(
    *,
    subject_id: str,
    scope_id: str,
    primary: SourceCitation,
    references: Sequence[SourceCitation],
    reason: str,
    fields: Sequence[str] = (),
    question_id: str = QUESTION_CURRENTNESS,
    question: str = "What current giving terms, service capacity, outcomes, governance or conduct does the retained evidence establish?",
) -> AnswerRecord:
    return AnswerRecord(
        subject_id=subject_id,
        scope_id=scope_id,
        question_id=question_id,
        question=question,
        answer_state="unanswered",
        answer=None,
        missingness={
            "status": "not_established",
            "reason": reason,
            "dimensions": list(MISSING_CURRENTNESS),
            "source_silence_is_not_absence": True,
        },
        source_family=primary.source_family,
        source_record_id=primary.source_record_id,
        representation_sha256=primary.representation_sha256,
        representation_locator=primary.representation_locator,
        source_date=primary.source_date,
        reporting_period=primary.reporting_period,
        fact_vs_source_statement_vs_inference="not_applicable",
        field_basis=tuple(fields),
        source_references=tuple(references),
    )


def _activity_record(register: tuple[Mapping[str, Any], SourceCitation]) -> AnswerRecord:
    body, citation = register
    required_fields = ("Programs", "OperatingInStates", "Countries", "Beneficiaries")
    if any(_source_field(body, field) is _MISSING or _source_field(body, field) is None for field in required_fields):
        return _unanswered(
            subject_id=citation.subject_id,
            scope_id=citation.scope_id,
            primary=citation,
            references=(citation,),
            reason="required source-native activity or footprint field is unavailable",
            fields=tuple(_source_field_path(body, field) for field in required_fields),
            question_id=QUESTION_ACTIVITY,
            question="Which source-native programs, named footprint and beneficiary fields are retained?",
        )
    programs = []
    for item in _source_field(body, "Programs"):
        if not isinstance(item, dict):
            return _unanswered(
                subject_id=citation.subject_id,
                scope_id=citation.scope_id,
                primary=citation,
                references=(citation,),
                reason="source-native program structure is unavailable",
                fields=(_source_field_path(body, "Programs"),),
                question_id=QUESTION_ACTIVITY,
                question="Which source-native programs, named footprint and beneficiary fields are retained?",
            )
        programs.append({"Name": item.get("Name"), "ProgramClassification": item.get("ProgramClassification")})
    answer = {
        "programs": programs,
        "operating_in_states": [item.get("Name") for item in _source_field(body, "OperatingInStates") if isinstance(item, dict)],
        "countries": [item.get("Name") for item in _source_field(body, "Countries") if isinstance(item, dict)],
        "beneficiaries": [item.get("Name") for item in _source_field(body, "Beneficiaries") if isinstance(item, dict)],
    }
    return AnswerRecord(
        subject_id=citation.subject_id,
        scope_id=citation.scope_id,
        question_id=QUESTION_ACTIVITY,
        question="Which source-native programs, named footprint and beneficiary fields are retained?",
        answer_state="supported",
        answer=answer,
        missingness=None,
        source_family=citation.source_family,
        source_record_id=citation.source_record_id,
        representation_sha256=citation.representation_sha256,
        representation_locator=citation.representation_locator,
        source_date=citation.source_date,
        reporting_period=citation.reporting_period,
        fact_vs_source_statement_vs_inference="fact",
        field_basis=tuple(
            f"{_source_field_path(body, field)}[].{suffix}"
            for field, suffix in (("Programs", "Name"), ("Programs", "ProgramClassification"), ("OperatingInStates", "Name"), ("Countries", "Name"), ("Beneficiaries", "Name"))
        ),
        source_references=(citation,),
    )


def _scale_record(ais: tuple[Mapping[str, Any], SourceCitation]) -> AnswerRecord:
    body, citation = ais
    fields = (
        "FinReportFrom", "FinReportTo", "FinReportingType", "IncomeTotalReceipts",
        "ExpenseTotal", "NetSurplusDeficit", "HrFullTimeEmployees", "HrPartTimeEmployees",
        "HrCasualEmployees", "HrUnpainVolunteers",
    )
    if any(_source_field(body, field) is _MISSING or _source_field(body, field) is None for field in fields):
        return _unanswered(
            subject_id=citation.subject_id,
            scope_id=citation.scope_id,
            primary=citation,
            references=(citation,),
            reason="required source-native reporting-period field is unavailable",
            fields=tuple(_source_field_path(body, field) for field in fields),
            question_id=QUESTION_SCALE,
            question="What source-native financial and workforce scale is reported for the retained period?",
        )
    period = {"from": str(_source_field(body, "FinReportFrom")), "to": str(_source_field(body, "FinReportTo"))}
    answer = {
        "reporting_period": period,
        "accounting_basis": _source_field(body, "FinReportingType"),
        "financial_measures": {
            "receipts": _source_field(body, "IncomeTotalReceipts"),
            "expenses": _source_field(body, "ExpenseTotal"),
            "net_surplus_deficit": _source_field(body, "NetSurplusDeficit"),
        },
        "workforce": {
            "full_time_employees": _source_field(body, "HrFullTimeEmployees"),
            "part_time_employees": _source_field(body, "HrPartTimeEmployees"),
            "casual_employees": _source_field(body, "HrCasualEmployees"),
            "unpaid_volunteers": _source_field(body, "HrUnpainVolunteers"),
        },
    }
    return AnswerRecord(
        subject_id=citation.subject_id,
        scope_id=citation.scope_id,
        question_id=QUESTION_SCALE,
        question="What source-native financial and workforce scale is reported for the retained period?",
        answer_state="supported",
        answer=answer,
        missingness=None,
        source_family=citation.source_family,
        source_record_id=citation.source_record_id,
        representation_sha256=citation.representation_sha256,
        representation_locator=citation.representation_locator,
        source_date=citation.source_date,
        reporting_period=period,
        fact_vs_source_statement_vs_inference="fact",
        field_basis=tuple(_source_field_path(body, field) for field in fields),
        source_references=(citation,),
    )


def build_source_answer_projection(
    *,
    manifest_path: str | Path,
    representation_root: str | Path,
) -> AnswerProjection:
    """Read the retained five-subject cohort and compile fifteen answer slots.

    This function is deliberately read-only.  It opens only the supplied JSON
    manifest and the ten exact content-addressed representation files.
    """
    loaded = _load_rows(Path(manifest_path), Path(representation_root))
    by_subject: dict[str, dict[str, tuple[Mapping[str, Any], SourceCitation]]] = {}
    for row, _path, body, citation in loaded:
        by_subject.setdefault(citation.subject_id, {})[str(row["source_family"])] = (body, citation)
    records: list[AnswerRecord] = []
    for subject_id in sorted(by_subject):
        sources = by_subject[subject_id]
        register = sources["acnc_register"]
        ais = sources["acnc_ais_bundle"]
        if register[1].scope_id != ais[1].scope_id:
            raise ProjectionValidationError("cross-source scope mismatch")
        records.append(_activity_record(register))
        records.append(_scale_record(ais))
        records.append(
            _unanswered(
                subject_id=subject_id,
                scope_id=ais[1].scope_id,
                primary=ais[1],
                references=(register[1], ais[1]),
                reason="the retained ACNC bodies do not establish current terms, capacity, outcomes, governance or conduct",
            )
        )
    if len(records) != 15:
        raise ProjectionValidationError("projection did not produce exactly fifteen answer slots")
    return AnswerProjection(
        records=tuple(records),
        representation_hashes=tuple(citation.representation_sha256 for _row, _path, _body, citation in loaded),
        side_effects={
            "provider_calls": 0,
            "transport_requests": 0,
            "budget_reservations": 0,
            "source_acquisitions": 0,
            "publications": 0,
            "sqlite_opens": 0,
        },
    )


__all__ = [
    "AnswerProjection",
    "AnswerRecord",
    "ProjectionValidationError",
    "QUESTION_ACTIVITY",
    "QUESTION_CURRENTNESS",
    "QUESTION_SCALE",
    "QUESTION_IDS",
    "SourceCitation",
    "build_source_answer_projection",
]
