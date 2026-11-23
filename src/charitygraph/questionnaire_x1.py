"""Private offline questionnaire experiment; no acquisition or provider transport."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Representation(Strict):
    representation_id: str = Field(min_length=1)
    source_family: str = Field(min_length=1)
    snapshot_id: str = Field(min_length=1)
    representation_sha256: str | None = Field(pattern=r"^[0-9a-f]{64}$")
    reference: str | None
    reporting_period: str | None
    state: Literal["available", "unavailable", "missing"]
    provenance: str = Field(min_length=1)

    @model_validator(mode="after")
    def available_has_location(self):
        if self.state == "available" and (not self.reference or not self.representation_sha256):
            raise ValueError("available representation requires reference and hash")
        return self


class ProgramSourceContext(Strict):
    representation_id: str = Field(min_length=1)
    locator: str = Field(pattern=r"^/")


class Program(Strict):
    program_id: str = Field(min_length=1)
    source_scoped_id: str = Field(min_length=1)
    source_representations: list[Representation]
    source_context: list[ProgramSourceContext] = []


class SourcePack(Strict):
    schema_version: Literal["x1-source-pack-1"]
    pack_id: str = Field(min_length=1)
    snapshot_id: str = Field(min_length=1)
    charitygraph_id: str = Field(min_length=1)
    acnc_uuid: str | None
    external_identifiers: dict[str, str]
    source_representations: list[Representation]
    programs: list[Program]
    program_inventory_state: Literal["available", "missing", "unavailable"]

    @model_validator(mode="after")
    def unique_ids(self):
        if len({p.program_id for p in self.programs}) != len(self.programs):
            raise ValueError("duplicate program identifier")
        if len({p.source_scoped_id for p in self.programs}) != len(self.programs):
            raise ValueError("duplicate source-scoped program identifier")
        if self.program_inventory_state != "available" and self.programs:
            raise ValueError("unavailable inventory cannot contain programs")
        reps = self.source_representations + [r for p in self.programs for r in p.source_representations]
        if len({r.representation_id for r in reps}) != len(reps):
            raise ValueError("duplicate representation identifier")
        shared = {r.representation_id for r in self.source_representations if r.state == "available"}
        for program in self.programs:
            allowed = shared | {r.representation_id for r in program.source_representations if r.state == "available"}
            if any(item.representation_id not in allowed for item in program.source_context):
                raise ValueError("program source context must reference an available scoped representation")
        return self


class Choice(Strict):
    value: str = Field(min_length=1)
    description: str = Field(min_length=1)


class Question(Strict):
    question_id: str = Field(min_length=1)
    north_star_contract: str = Field(min_length=1)
    section: str = Field(min_length=1)
    scope: Literal["charity", "program"]
    wording: str = Field(min_length=1)
    answer_type: Literal["categorical", "boolean", "ordinal", "numeric"]
    choices: list[Choice] = []
    taxonomy_ref: str | None = None
    rubric: str = Field(min_length=1)
    unknown_semantics: str = Field(min_length=1)
    depends_on: list[str] = []

    @model_validator(mode="after")
    def independent_and_typed(self):
        if self.depends_on:
            raise ValueError("questions must be independently answerable")
        values = [c.value for c in self.choices]
        if len(values) != len(set(values)):
            raise ValueError("duplicate choice")
        if self.answer_type == "numeric" and (values or self.taxonomy_ref):
            raise ValueError("numeric questions have no choice taxonomy")
        if self.answer_type != "numeric" and not values:
            raise ValueError("resolved permitted choices required")
        if self.answer_type != "numeric" and "unknown" not in values:
            raise ValueError("choice questions require an explicit unknown")
        return self


class Questionnaire(Strict):
    schema_version: Literal["x1-questionnaire-1"]
    questionnaire_id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    questions: list[Question] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_ids(self):
        if len({q.question_id for q in self.questions}) != len(self.questions):
            raise ValueError("duplicate question identifier")
        return self


class NumericValue(Strict):
    amount: int | float
    currency: str = Field(min_length=1)
    reporting_period: str = Field(min_length=1)
    source_reference: str = Field(min_length=1)
    basis: Literal["reported", "calculated"]


class CapturedAnswer(Strict):
    question_id: str
    subject_id: str
    questionnaire_id: str
    questionnaire_version: str
    source_snapshot_id: str
    status: Literal["answered", "unknown", "not_applicable", "conflict", "insufficient_evidence", "processing_failure"]
    method: Literal["fixture", "captured_decisions", "source_native"]
    value: str | bool | NumericValue | None = None
    probabilities: dict[str, float] | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    source_references: list[str] = []


def load_pack(path: Path) -> SourcePack:
    return SourcePack.model_validate_json(path.read_text(encoding="utf-8"))


def load_questionnaire(path: Path) -> Questionnaire:
    return Questionnaire.model_validate_json(path.read_text(encoding="utf-8"))


def prepare(pack: SourcePack, questionnaire: Questionnaire) -> list[dict]:
    """Produce independent requests referencing existing representations only."""
    requests = []
    for q in questionnaire.questions:
        subjects = [(pack.charitygraph_id, pack.source_representations, [])] if q.scope == "charity" else [
            (p.program_id, pack.source_representations + p.source_representations, p.source_context) for p in pack.programs
        ]
        for subject, sources, context in subjects:
            requests.append({"questionnaire_id": questionnaire.questionnaire_id,
                "questionnaire_version": questionnaire.version, "question": q.model_dump(),
                "subject_id": subject, "charitygraph_id": pack.charitygraph_id,
                "snapshot_id": pack.snapshot_id, "program_source_context": [c.model_dump() for c in context],
                "source_representations": [s.model_dump() for s in sources]})
    return requests


def batch_choices(requests: list[dict], max_questions: int) -> list[list[dict]]:
    """Batch independent choice questions only when subject and source scope agree."""
    if max_questions < 1:
        raise ValueError("batch size must be positive")
    groups: dict[tuple, list[dict]] = {}
    for request in requests:
        if request["question"]["answer_type"] == "numeric":
            continue
        key = (request["questionnaire_id"], request["questionnaire_version"], request["snapshot_id"],
               request["subject_id"], json.dumps(request["source_representations"], sort_keys=True))
        groups.setdefault(key, []).append(request)
    return [group[i:i + max_questions] for group in groups.values() for i in range(0, len(group), max_questions)]


def answer(pack: SourcePack, questionnaire: Questionnaire, records: list[dict]) -> dict:
    """Validate captured/fixture answers without interpreting evidence or contacting a model."""
    requests = prepare(pack, questionnaire)
    expected = {(r["question"]["question_id"], r["subject_id"]): r for r in requests}
    seen = set()
    output = []
    for raw in records:
        record = CapturedAnswer.model_validate(raw)
        if (record.questionnaire_id != questionnaire.questionnaire_id or
                record.questionnaire_version != questionnaire.version or record.source_snapshot_id != pack.snapshot_id):
            raise ValueError("response version or source snapshot does not match")
        key = (record.question_id, record.subject_id)
        if key not in expected or key in seen:
            raise ValueError("unexpected or duplicate question/subject response")
        seen.add(key)
        q = expected[key]["question"]
        values = {c["value"] for c in q["choices"]}
        value = record.value
        if record.method == "captured_decisions" and record.status in {"unknown", "not_applicable", "conflict", "insufficient_evidence"} and record.status not in values:
            raise ValueError("captured non-answer status is not an allowed choice")
        if record.status == "answered":
            if q["answer_type"] == "numeric":
                if not isinstance(value, NumericValue):
                    raise ValueError("numeric answer requires a numeric result record")
                if value.source_reference not in record.source_references:
                    raise ValueError("numeric source reference must be retained")
            elif type(value) is not str or value not in values or value == "unknown":
                raise ValueError("answer is not an allowed non-unknown choice")
        elif record.status == "unknown":
            if value is not None and value != "unknown":
                raise ValueError("unknown cannot assert a value")
        elif value is not None:
            raise ValueError("not-applicable/failure cannot assert a value")
        if record.probabilities is not None:
            if q["answer_type"] == "numeric" or set(record.probabilities) - values:
                raise ValueError("probabilities must refer to permitted choices")
            if any(not 0 <= p <= 1 for p in record.probabilities.values()):
                raise ValueError("probability outside [0,1]")
        allowed_refs = {s["reference"] for s in expected[key]["source_representations"] if s["state"] == "available"}
        if set(record.source_references) - allowed_refs:
            raise ValueError("answer cites source outside its prepared scope")
        output.append({"question_id": record.question_id, "subject_id": record.subject_id,
            "charitygraph_id": pack.charitygraph_id, "source_snapshot_id": pack.snapshot_id,
            "questionnaire_id": questionnaire.questionnaire_id, "questionnaire_version": questionnaire.version,
            "answer_type": q["answer_type"], "status": record.status, "answering_method": record.method,
            "value": value.model_dump() if isinstance(value, NumericValue) else value,
            "probabilities": record.probabilities, "confidence": record.confidence,
            "source_references": record.source_references,
            "promotion_status": "experimental_not_promoted"})
    if seen != set(expected):
        raise ValueError("missing response; provide explicit failure or unknown")
    return {"schema_version": "x1-answer-set-1", "source_pack_id": pack.pack_id,
        "source_snapshot_id": pack.snapshot_id, "questionnaire_id": questionnaire.questionnaire_id,
        "questionnaire_version": questionnaire.version, "program_inventory_state": pack.program_inventory_state,
        "program_questions_without_subjects": [q.question_id for q in questionnaire.questions if q.scope == "program"] if not pack.programs else [],
        "answers": output}


def adapt_decisions_choice(raw: dict, *, question_id: str, subject_id: str,
                           questionnaire_id: str, questionnaire_version: str, source_snapshot_id: str,
                           source_references: list[str]) -> dict:
    """Normalize one captured native choice; caller supplies independently verified bindings."""
    if raw.get("type") != "choice" or raw.get("name") != question_id:
        raise ValueError("captured response does not match the bound choice question")
    choice = raw.get("choice")
    if not isinstance(choice, str):
        raise ValueError("captured choice is missing")
    probabilities = raw.get("probabilities")
    if probabilities is not None:
        if not isinstance(probabilities, list):
            raise ValueError("native probabilities must be a list")
        values = [p["value"] for p in probabilities]
        if len(values) != len(set(values)):
            raise ValueError("duplicate native probability choice")
        probabilities = {p["value"]: p["probability"] for p in probabilities}
    special = {"unknown", "not_applicable", "conflict", "insufficient_evidence"}
    return {"question_id": question_id, "subject_id": subject_id,
        "questionnaire_id": questionnaire_id, "questionnaire_version": questionnaire_version, "source_snapshot_id": source_snapshot_id,
        "status": choice if choice in special else "answered", "method": "captured_decisions",
        "value": None if choice in special and choice != "unknown" else choice, "probabilities": probabilities, "confidence": raw.get("confidence"),
        "source_references": source_references}


def write_json(path: Path, value: dict | list) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
